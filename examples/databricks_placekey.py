# Databricks notebook source
# MAGIC %md
# MAGIC # Placekey crosswalk
# MAGIC
# MAGIC Generates a [Placekey](https://www.placekey.io) for every address in a source table and
# MAGIC records the result in a **crosswalk table** that points back at the source record.
# MAGIC
# MAGIC | Table | One row per | Purpose |
# MAGIC |---|---|---|
# MAGIC | `address_crosswalk` | source record (`source_table` + `source_id`) | Lineage: which table, which id, which columns, which placekey |
# MAGIC | `address_placekey_cache` | distinct normalised address | Every address is sent to the API once, however many records or tables share it |
# MAGIC
# MAGIC Re-running is cheap: addresses already in the cache are not looked up again, and a run that
# MAGIC dies part-way keeps what it finished. Point it at another table by changing the widgets; all
# MAGIC tables land in the same crosswalk, told apart by `source_table`.
# MAGIC
# MAGIC **Setup:** store the Placekey API key in a secret scope
# MAGIC (`databricks secrets put-secret placekey api_key`), then fill in the widgets above.
# MAGIC Off Databricks (a Job's Python task, a laptop) the same names are read from upper-case
# MAGIC environment variables, e.g. `SOURCE_TABLE`, and the key from `PLACEKEY_API_KEY`.

# COMMAND ----------

# MAGIC %pip install requests
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Configuration
import os
import re

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()


def param(name, default=""):
    """A notebook widget on Databricks, an upper-case environment variable elsewhere."""
    try:
        dbutils.widgets.text(name, default)  # noqa: F821  (provided by Databricks)
        return dbutils.widgets.get(name).strip()  # noqa: F821
    except NameError:
        return os.environ.get(name.upper(), default).strip()


# What to read ---------------------------------------------------------------
SOURCE_TABLE = param("source_table")        # catalog.schema.table
ID_FIELD = param("id_field")                # unique id of the source record
# Which columns make up the address. Leave optional ones blank if you don't have them.
STREET_FIELD = param("street_field")        # required
CITY_FIELD = param("city_field")
REGION_FIELD = param("region_field")        # state / province
POSTAL_FIELD = param("postal_field")
COUNTRY_FIELD = param("country_field")      # blank = use DEFAULT_COUNTRY for every row
DEFAULT_COUNTRY = param("default_country", "US")

# Placekey API key ------------------------------------------------------------
SECRET_SCOPE = param("secret_scope", "placekey")
SECRET_KEY = param("secret_key", "api_key")

# Where results go ------------------------------------------------------------
# Blank = "<current catalog>.placekey". The schema is created if it doesn't exist.
TARGET_SCHEMA = param("target_schema")
RETRY_ERRORS = param("retry_errors", "false").lower() == "true"  # re-look-up addresses the API rejected
WORKERS = int(param("workers", "4"))                              # parallel API requests

# COMMAND ----------

# DBTITLE 1,Validate configuration and resolve names
_NAME = re.compile(r"^[\w\-]+$")


def quote(name):
    """Backtick-quote a dotted table name or a column name, rejecting anything odd."""
    parts = name.split(".")
    if not all(_NAME.match(p) for p in parts):
        raise ValueError(f"Not a valid identifier: {name!r}")
    return ".".join(f"`{p}`" for p in parts)


missing = [n for n, v in [("source_table", SOURCE_TABLE), ("id_field", ID_FIELD),
                          ("street_field", STREET_FIELD)] if not v]
if missing:
    raise ValueError(f"Set the widget(s): {', '.join(missing)}")
if not (POSTAL_FIELD or (CITY_FIELD and REGION_FIELD)):
    raise ValueError("Placekey needs either postal_field, or city_field and region_field")

if not TARGET_SCHEMA:
    catalog = spark.sql("SELECT current_catalog()").first()[0]
    TARGET_SCHEMA = f"{catalog}.placekey"
CROSSWALK = f"{TARGET_SCHEMA}.address_crosswalk"
CACHE = f"{TARGET_SCHEMA}.address_placekey_cache"

# The table name stored as lineage: always the fully qualified three-part name.
_parts = SOURCE_TABLE.replace("`", "").split(".")
_defaults = spark.sql("SELECT current_catalog(), current_schema()").first()
SOURCE_FQN = ".".join((list(_defaults)[: 3 - len(_parts)] + _parts))
print(f"Source:    {SOURCE_FQN}  (id: {ID_FIELD})")
print(f"Crosswalk: {CROSSWALK}")
print(f"Cache:     {CACHE}")

# COMMAND ----------

# DBTITLE 1,Create output tables
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {quote(TARGET_SCHEMA)}")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {quote(CACHE)} (
        address_hash    STRING NOT NULL COMMENT 'sha2 of the normalised address; the key',
        street_address  STRING,
        city            STRING,
        region          STRING,
        postal_code     STRING,
        iso_country_code STRING,
        placekey        STRING,
        status          STRING COMMENT 'ok | error',
        error           STRING,
        looked_up_at    TIMESTAMP
    ) COMMENT 'One row per distinct address sent to the Placekey API'
""")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {quote(CROSSWALK)} (
        source_table    STRING NOT NULL COMMENT 'Fully qualified table the record came from',
        source_id_field STRING COMMENT 'Column in source_table that source_id was read from',
        source_id       STRING NOT NULL COMMENT 'Value of that column, cast to string',
        address_fields  STRING COMMENT 'Which source columns formed the address',
        address_hash    STRING COMMENT 'Join to the cache; null when the address was incomplete',
        placekey        STRING,
        status          STRING COMMENT 'ok | error | incomplete',
        error           STRING,
        generated_at    TIMESTAMP
    ) COMMENT 'Placekey per source record, with lineage back to the source table'
""")

# COMMAND ----------

# DBTITLE 1,Read and normalise the source addresses
from pyspark.sql import functions as F


def clean(column):
    """Trimmed string, with blanks as NULL."""
    c = F.trim(F.col(column).cast("string"))
    return F.when(c == "", None).otherwise(c)


def optional(column):
    return clean(column) if column else F.lit(None).cast("string")


src = spark.table(quote(SOURCE_TABLE)).select(
    F.col(quote(ID_FIELD)).cast("string").alias("source_id"),
    *[
        expr.alias(alias)
        for alias, expr in [
            ("street_address", clean(quote(STREET_FIELD))),
            ("city", optional(quote(CITY_FIELD) if CITY_FIELD else "")),
            ("region", optional(quote(REGION_FIELD) if REGION_FIELD else "")),
            ("postal_code", optional(quote(POSTAL_FIELD) if POSTAL_FIELD else "")),
        ]
    ],
    (F.upper(clean(quote(COUNTRY_FIELD))) if COUNTRY_FIELD else F.lit(None).cast("string")).alias("country"),
).withColumn("iso_country_code", F.coalesce(F.col("country"), F.lit(DEFAULT_COUNTRY.upper()))).drop("country")

if src.filter(F.col("source_id").isNull()).limit(1).count():
    raise ValueError(f"{ID_FIELD} has NULLs; it must identify every record")

# Placekey needs a street plus either a postal code or city + region.
complete = F.col("street_address").isNotNull() & (
    F.col("postal_code").isNotNull() | (F.col("city").isNotNull() & F.col("region").isNotNull())
)
SEP = "\u001f"  # unit separator: can't appear in an address, so fields can't run together
normalised = F.concat_ws(
    SEP,
    *[F.lower(F.coalesce(F.col(c), F.lit(""))) for c in
      ("street_address", "city", "region", "postal_code", "iso_country_code")],
)
src = src.withColumn("address_hash", F.when(complete, F.sha2(normalised, 256))).cache()
print(f"{src.count():,} source record(s), {src.filter(~complete).count():,} with an incomplete address")

# COMMAND ----------

# DBTITLE 1,Find addresses that still need a placekey
done_statuses = ["ok"] if RETRY_ERRORS else ["ok", "error"]
already = spark.table(quote(CACHE)).filter(F.col("status").isin(done_statuses)).select("address_hash")

todo = (
    src.filter(F.col("address_hash").isNotNull())
    .select("address_hash", "street_address", "city", "region", "postal_code", "iso_country_code")
    .dropDuplicates(["address_hash"])
    .join(already, "address_hash", "left_anti")
)
todo_count = todo.count()
print(f"{todo_count:,} address(es) to look up")

# COMMAND ----------

# DBTITLE 1,Call the Placekey API
import time
from concurrent.futures import ThreadPoolExecutor

import requests

API_URL = "https://api.placekey.io/v1/placekeys"
BATCH_SIZE = 100       # the bulk endpoint's maximum
CHUNK_SIZE = 5000      # addresses per write to the cache, so a failed run keeps its progress


def api_key():
    if os.environ.get("PLACEKEY_API_KEY"):
        return os.environ["PLACEKEY_API_KEY"]
    return dbutils.secrets.get(SECRET_SCOPE, SECRET_KEY)  # noqa: F821


def lookup_batch(rows, key, session=requests, sleep=time.sleep):
    """Look up up to 100 addresses; returns (address_hash, placekey, error) per row."""
    queries = []
    for i, r in enumerate(rows):
        q = {"query_id": str(i), "street_address": r["street_address"],
             "iso_country_code": r["iso_country_code"]}
        for field in ("city", "region", "postal_code"):
            if r[field]:
                q[field] = r[field]
        queries.append(q)

    for attempt in range(6):
        resp = session.post(API_URL, json={"queries": queries},
                            headers={"apikey": key, "Content-Type": "application/json"}, timeout=60)
        if resp.status_code == 429 or resp.status_code >= 500:
            sleep(min(2 ** attempt, 30))  # rate limited or server trouble: back off and retry
            continue
        if resp.status_code in (401, 403):
            raise PermissionError(f"Placekey rejected the API key (HTTP {resp.status_code})")
        resp.raise_for_status()
        break
    else:
        raise RuntimeError(f"Placekey API still failing after retries (HTTP {resp.status_code})")

    by_id = {str(item.get("query_id")): item for item in resp.json()}
    out = []
    for i, r in enumerate(rows):
        item = by_id.get(str(i), {})
        placekey = item.get("placekey")
        error = None if placekey else (item.get("error") or "No result returned")
        out.append((r["address_hash"], placekey, error))
    return out


CACHE_SCHEMA = "address_hash string, placekey string, error string"


def save_to_cache(results, addresses):
    """Merge one chunk of results into the cache."""
    df = spark.createDataFrame(results, CACHE_SCHEMA).join(addresses, "address_hash")
    df = df.select(
        "address_hash", "street_address", "city", "region", "postal_code", "iso_country_code",
        "placekey",
        F.when(F.col("placekey").isNotNull(), "ok").otherwise("error").alias("status"),
        "error",
        F.current_timestamp().alias("looked_up_at"),
    )
    df.createOrReplaceTempView("_pk_cache_new")
    spark.sql(f"""
        MERGE INTO {quote(CACHE)} t USING _pk_cache_new s ON t.address_hash = s.address_hash
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)


if todo_count:
    key = api_key()
    rows = [r.asDict() for r in todo.toLocalIterator()]
    looked_up = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for start in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[start:start + CHUNK_SIZE]
            batches = [chunk[i:i + BATCH_SIZE] for i in range(0, len(chunk), BATCH_SIZE)]
            results = [res for batch in pool.map(lambda b: lookup_batch(b, key), batches) for res in batch]
            save_to_cache(results, spark.createDataFrame(chunk, todo.schema))
            looked_up += len(chunk)
            print(f"  {looked_up:,}/{len(rows):,}")

# COMMAND ----------

# DBTITLE 1,Write the crosswalk
cache = spark.table(quote(CACHE)).select("address_hash", "placekey", "status", "error")
address_fields = "; ".join(
    f"{label}={col}" for label, col in [
        ("street", STREET_FIELD), ("city", CITY_FIELD), ("region", REGION_FIELD),
        ("postal", POSTAL_FIELD), ("country", COUNTRY_FIELD or f"'{DEFAULT_COUNTRY.upper()}'"),
    ] if col
)

crosswalk_new = (
    src.join(cache, "address_hash", "left")
    .select(
        F.lit(SOURCE_FQN).alias("source_table"),
        F.lit(ID_FIELD).alias("source_id_field"),
        "source_id",
        F.lit(address_fields).alias("address_fields"),
        "address_hash",
        "placekey",
        F.coalesce(F.col("status"), F.lit("incomplete")).alias("status"),
        "error",
        F.current_timestamp().alias("generated_at"),
    )
)
crosswalk_new.createOrReplaceTempView("_pk_crosswalk_new")

spark.sql(f"""
    MERGE INTO {quote(CROSSWALK)} t USING _pk_crosswalk_new s
      ON t.source_table = s.source_table AND t.source_id = s.source_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")
src.unpersist()

display(  # noqa: F821
    spark.table(quote(CROSSWALK)).filter(F.col("source_table") == SOURCE_FQN)
    .groupBy("status").count().orderBy("status")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Using the crosswalk
# MAGIC
# MAGIC Join back to the source on the lineage columns. Because every source table shares the one
# MAGIC crosswalk, **filter on `source_table`** (and `source_id_field`, if a table was ever run with a
# MAGIC different id column):
# MAGIC
# MAGIC ```sql
# MAGIC SELECT s.*, x.placekey
# MAGIC FROM   main.crm.accounts AS s            -- your source table
# MAGIC JOIN   main.placekey.address_crosswalk AS x
# MAGIC   ON   x.source_table = 'main.crm.accounts'
# MAGIC  AND   x.source_id     = CAST(s.account_id AS STRING)
# MAGIC WHERE  x.status = 'ok';
# MAGIC ```
# MAGIC
# MAGIC Two records at the same placekey are the same place, which is the basis for matching across
# MAGIC tables:
# MAGIC
# MAGIC ```sql
# MAGIC SELECT placekey, collect_set(struct(source_table, source_id)) AS records
# MAGIC FROM   main.placekey.address_crosswalk
# MAGIC WHERE  status = 'ok'
# MAGIC GROUP  BY placekey HAVING count(*) > 1;
# MAGIC ```
# MAGIC
# MAGIC Rows deleted from the source stay in the crosswalk; remove them with a `DELETE` against
# MAGIC `source_table` if that matters to you.
