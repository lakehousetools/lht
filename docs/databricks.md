# Databricks: reverse ETL from the lakehouse

Databricks ingests Salesforce well — Lakeflow Connect pulls objects into Unity Catalog with no code. What it has no answer for is the other direction: getting a model output, a lead score or a cleaned address back *into* Salesforce.

That's what lht does here. Reverse ETL runs on your Databricks compute, reading a Unity Catalog table with Spark SQL and writing to Salesforce through Bulk API 2.0 ingest jobs. No hosted connector, no data leaving your workspace except the rows you're pushing to Salesforce.

!!! note "What runs on Databricks"
    Reverse ETL (`upsert`, `insert`, `update`, `delete`) and record `merge`. Salesforce → warehouse **sync** is Snowflake-only; on Databricks, use Lakeflow Connect for ingestion and lht for the write-back.

## Install

```python
%pip install lht
dbutils.library.restartPython()
```

That's the whole install on a cluster. lht's core has no warehouse client in it — `pandas`, `requests`, `cryptography` and `tabulate` — so nothing gets installed over the pandas and pyarrow your runtime ships. The Spark session you already have is the warehouse connection.

For a job, pin it as a library on the task instead: `lht==3.0.0`.

## Find your catalog

Unity Catalog names have three parts, `catalog.schema.table`. **The catalog in this page's examples — `main`, as in `main.analytics.account_scores` — is a placeholder for yours.** Not every workspace has a catalog called `main`, and pointing lht at one that doesn't exist fails with `Catalog 'main' was not found`.

To see the catalogs you have:

```python
display(spark.sql("SHOW CATALOGS"))
spark.sql("SELECT current_catalog()").collect()[0][0]     # the one this session uses by default
```

Pick one you can create schemas and tables in, because lht creates its log tables on first use. Avoid `hive_metastore`, which isn't Unity Catalog. Then put the name in one variable and build everything from it, so there's a single place to change:

```python
CATALOG = "my_catalog"                    # replace with a name from SHOW CATALOGS
LOG_SCHEMA = f"{CATALOG}.lht_logs"        # if the name has a hyphen: f"`{CATALOG}`.lht_logs"
```

## The notebook

```python
from lht.salesforce import retl
from lht.warehouse.databricks import connect, salesforce_access_info

warehouse = connect()                                   # the cluster's `spark`
access_info = salesforce_access_info(scope="salesforce") # a secret scope

retl.upsert(
    warehouse, access_info,
    sobject="Account",
    query="""
        SELECT external_id    AS Ext__c,
               rating         AS Rating,
               annual_revenue AS AnnualRevenue
        FROM main.analytics.account_scores
        WHERE scored_at >= current_date() - INTERVAL 1 DAY
    """,
    field="Ext__c",
)
```

You can pass `spark` straight in as well — `retl.upsert(spark, ...)` works, because lht recognises a Spark session. `connect()` is just explicit about which warehouse you meant.

### Credentials

Put the Salesforce credentials in a [secret scope](https://docs.databricks.com/en/security/secrets/index.html), using the same key names lht uses everywhere else:

```bash
databricks secrets create-scope salesforce
databricks secrets put-secret salesforce client_id
databricks secrets put-secret salesforce client_secret
databricks secrets put-secret salesforce my_domain
```

`salesforce_access_info(scope="salesforce")` reads those, so the secret never appears in the notebook, in its output, or in a revision. For the JWT bearer flow — which needs no secret and suits a scheduled job — add `auth_flow=jwt_bearer`, `username` and `private_key_pem` to the scope instead. Both flows are described under [Authentication](authentication.md).

### Azure Key Vault

A secret scope [backed by Azure Key Vault](https://learn.microsoft.com/azure/databricks/security/secrets/) works the same way, with one difference: Key Vault secret names allow only letters, digits and hyphens, so write the keys with hyphens — `client-id`, `client-secret`, `my-domain` (and `auth-flow`, `username`, `private-key-pem` for the JWT bearer flow). lht reads either spelling, and prefers the underscore one if a scope somehow has both.

```python
access_info = salesforce_access_info(scope="kv-salesforce")
```

Add and change the secrets in Azure; a Key Vault-backed scope is read-only from Databricks, so `databricks secrets put-secret` does not apply to it.

!!! warning "Pointing at a sandbox"
    On the default client-credentials flow, **`my_domain` alone decides which org you reach** — put the sandbox's own My Domain there (`acme--dev.sandbox`, not `acme`). A `sandbox` key in the scope only affects the JWT bearer flow's login URL; on client credentials it changes nothing, and lht logs a warning if you set it alongside a production-looking domain. Print `access_info["instance_url"]` once to confirm which org you actually authenticated against.

## Developing locally, running in a notebook

The same file can run both places, which is the point of `connect()` and `salesforce_access_info()` taking no arguments that only make sense in one of them.

Locally, lht uses **Databricks Connect** against a `~/.databrickscfg` profile — the same file and profiles the Databricks CLI uses. There is no lht-side credential for Databricks at all.

```bash
pip install "lht[databricks]"
databricks auth login --host https://my-workspace.cloud.databricks.com
```

This needs **Python 3.10 or newer** — Databricks Connect 15.1 and later, which is what the extra installs, doesn't support 3.9, so on 3.9 pip reports that it can't find a matching version. (lht itself still runs on 3.9, and a Databricks cluster needs no extra at all.) Databricks Connect also has to be compatible with the runtime of the cluster you point it at; if you connect to a classic cluster rather than serverless, install the Databricks Connect release that matches that cluster's Databricks Runtime, per Databricks' compatibility table, instead of the newest.

Point the profile at compute by adding `serverless_compute_id = auto` (or a `cluster_id`) to its section in `~/.databrickscfg`, then:

```python
warehouse = connect(profile="my-workspace")
access_info = salesforce_access_info(scope="salesforce", connection_name="my_salesforce")
```

In a notebook, `connect()` finds the running session and ignores `profile`; `salesforce_access_info()` reads the scope. On your laptop, `connect(profile=...)` starts a Databricks Connect session and `salesforce_access_info()` falls back to the connection you made with `lht create-connection --salesforce`, because there is no `dbutils` to read a scope with. Nothing in the file changes between the two.

To keep credentials out of a local file as well, register them in memory:

```python
from lht.user.connections import register_connection

register_connection("my_salesforce", {
    "connection_type": "salesforce",
    "client_id": os.environ["SF_CLIENT_ID"],
    "client_key": os.environ["SF_CLIENT_SECRET"],
    "my_domain": "mycompany",
})
```

## From the CLI

`--databricks` takes a profile name, in place of `--snowflake`:

```bash
lht retl upsert --databricks my-workspace \
  --sobject Account --match-field Ext__c \
  --sql-file account_scores.sql

lht merge --databricks my-workspace --sobject Account --sql-file dupes.sql --dry-run
```

Omit the profile name (`--databricks` alone) to let Databricks Connect resolve it from `DATABRICKS_HOST`/`DATABRICKS_TOKEN` or the `DEFAULT` profile. Keeping the query in a `--sql-file` is what makes the handover to a notebook a copy-paste.

## Writing the query

Everything in [Reverse ETL](reverse-etl.md) applies — operations, `clear_nulls`, batching, match fields. Two things are specific to Spark SQL:

**Column names are Salesforce field API names, and Spark keeps your aliases exactly as written.** So `AS Ext__c` arrives at Salesforce as `Ext__c`. This is easier than on Snowflake, where an unquoted alias folds to uppercase. Salesforce matches field names case-insensitively either way, so it rarely matters — but it means you can read the CSV header and see what you wrote.

**Three-level names work as you'd expect:** `catalog.schema.table`. If a name needs quoting, use backticks, not double quotes — Spark SQL reads `"x"` as a string literal unless ANSI mode is on.

```sql
SELECT a.external_id AS Ext__c,
       a.score       AS Lead_Score__c,
       CASE WHEN a.score > 80 THEN 'Hot' ELSE 'Warm' END AS Rating
FROM main.analytics.account_scores a
WHERE a.score IS NOT NULL
```

## Result logging

`--log-results`, or `lht.salesforce.results_bapi.process_bulk_api_results()`, writes per-record outcomes to `JOB_INFO`, `SUCCESS` and `FAILURE`, created as Delta tables on first use. Pass the match field and each row records which source record produced which Salesforce Id — or which error.

**Qualify the schema.** The default is a bare `LOGS`, which resolves against whatever catalog the session happens to point at — rarely what you want on Unity Catalog. Name it outright. There are two places to say so, because lht keeps two kinds of log: the job history (`RETL_HISTORY`, written on *every* ingest, whether or not you log results) takes `log_schema=` on the `retl` call, and the per-record tables take `schema=` on `process_bulk_api_results`:

```python
from lht.salesforce.results_bapi import process_bulk_api_results

result = retl.upsert(warehouse, access_info, "Account", query, "Ext__c",
                     log_schema="main.lht_logs")                      # RETL_HISTORY
for batch in result["batch_results"]:
    if batch.get("job_id"):
        process_bulk_api_results(warehouse, access_info, batch["job_id"],
                                 match_field="Ext__c", schema="main.lht_logs")
```

From the CLI, one flag sets both: `--log-schema main.lht_logs`. The schema is created on first use if it doesn't exist.

**Check what `process_bulk_api_results` returns.** It never raises, because logging must not fail a load that already reached Salesforce. So it reports through its result instead: `success` is `True` only if everything was saved, and when it isn't, `error` says what failed.

```python
outcome = process_bulk_api_results(warehouse, access_info, job_id,
                                   match_field="Ext__c", schema=LOG_SCHEMA)
if not outcome["success"]:
    print(outcome["error"])
```

Every row in `SUCCESS` is a record Salesforce accepted, so its `SUCCESS` column is `TRUE`; `CREATED` says whether it was created (`TRUE`) or updated (`FALSE`). Then:

```sql
SELECT match_id AS external_id, sf_error
FROM main.lht_logs.failure
WHERE job_id = '750...'
```

Logging is best-effort: if the schema isn't writable, the load still completes. The failure is a warning, and `process_bulk_api_results` returns `success: False` with an `error` naming what couldn't be saved, so a log that wasn't written can't pass for one that was. Messages are cut down to the cause, without Databricks' stack trace. A schema name that can't be used at all — a typo, or something that isn't a valid identifier — is reported once as a failed logging result rather than as four warnings.

## Check it works on your cluster

Run these in order in a notebook, against a Salesforce **sandbox** — they write real records. You need an External ID field on Account; the examples call it `Ext__c`, so use your own field's API name.

**1. Set up.** Check that the URL it prints is your sandbox:

```python
CATALOG = "my_catalog"                    # from SHOW CATALOGS
LOG_SCHEMA = f"{CATALOG}.lht_logs"

from lht.warehouse.databricks import connect, salesforce_access_info
from lht.salesforce import retl
from lht.salesforce.results_bapi import process_bulk_api_results

wh = connect()
access = salesforce_access_info(scope="salesforce")
print(wh.name, access["instance_url"])      # databricks https://<your-sandbox>...
```

**2. Write one record.** Run it twice: the second run should update the same Account, not create another.

```python
result = retl.upsert(
    wh, access, sobject="Account",
    query="SELECT 'LHT-SMOKE-1' AS Ext__c, 'lht smoke test' AS Name, 'Warm' AS Rating",
    field="Ext__c",
    log_schema=LOG_SCHEMA,
)
print(result["successful_batches"], result["total_records"])      # 1 1
```

`1 1` means the Salesforce job finished. It doesn't say every record was accepted, so check the Account exists, or use step 3.

**3. Save per-record results, with awkward characters.** The query is SQL, so a value containing a quote has to be escaped for SQL first. Let the warehouse do it with `wh.literal(...)` instead of pasting the value in:

```python
tricky = "O'Brien \\ test"                  # an apostrophe and a backslash
result = retl.upsert(
    wh, access, sobject="Account",
    query=f"SELECT {wh.literal(tricky)} AS Ext__c, 'lht escaping test' AS Name",
    field="Ext__c",
    log_schema=LOG_SCHEMA,
)
for b in result["batch_results"]:
    if b.get("job_id"):
        print(process_bulk_api_results(wh, access, b["job_id"],
                                       match_field="Ext__c", schema=LOG_SCHEMA))
```

Look for `'success': True` in what it prints. If it's `False`, `error` names the cause — usually the catalog name or a missing privilege.

**4. Read it back:**

```python
display(spark.sql(f"SELECT MATCH_ID, SF_ID, CREATED, SUCCESS, CREATED_AT FROM {LOG_SCHEMA}.SUCCESS ORDER BY CREATED_AT DESC LIMIT 5"))
display(spark.sql(f"SELECT ID, STATE, NUMBER_RECORDS_PROCESSED, NUMBER_RECORDS_FAILED FROM {LOG_SCHEMA}.JOB_INFO ORDER BY CREATED_AT DESC LIMIT 5"))
display(spark.sql(f"SELECT ID, OPERATION, OBJECT, CREATEDDATE FROM {LOG_SCHEMA}.RETL_HISTORY LIMIT 5"))
```

`MATCH_ID` should read exactly `O'Brien \ test`, with both characters, and `SUCCESS` should be `TRUE`. If a table is missing, the catalog browser in the sidebar doesn't refresh by itself — reload it before assuming it wasn't created.

**5. Clean up.** Delete the test Accounts in the sandbox, and drop the log schema if you don't want to keep it:

```python
spark.sql(f"DROP SCHEMA IF EXISTS {LOG_SCHEMA} CASCADE")
```

## Scheduling

A Databricks Job running the notebook on a schedule is all this needs. Use a secret scope for credentials and the job's own cluster identity for Unity Catalog — there is nothing else to configure, and no local config directory in the picture.

For a Python task rather than a notebook, `connect()` still finds the job's Spark session, so the same code works unchanged.

## Memory

`upsert` reads the query once and holds the result on the driver, then cuts it into Bulk API batches. That is deliberate — re-reading per batch without an `ORDER BY` could send a row twice or skip it, since Spark doesn't promise a stable order. The practical consequence is that the driver has to hold the rows you're pushing, so make the query select only the rows that actually changed. Reverse ETL into Salesforce is rate-limited by the Bulk API long before it is by Spark, so a narrow query is the right shape anyway.

## Troubleshooting

| What you see | What it means |
|---|---|
| `No Spark session is running and Databricks Connect is not installed` | Running off-platform. `pip install "lht[databricks]"` and set up a profile. |
| `Could not start a Databricks Connect session` | The profile has no host/token, or no compute. Add `serverless_compute_id = auto` or a `cluster_id` to the profile. |
| `Cannot read secret <scope>/<key>: dbutils is not available` | `salesforce_access_info(scope=...)` off-platform. Pass `connection_name=` as well, or set up a local connection. |
| `Connecting to Snowflake needs the Snowpark client` | A Snowflake path was reached. On Databricks you want `--databricks` / `connect()`, not a Snowflake connection. |
| `Table or view not found` on a log table | The catalog or schema isn't writable by the cluster, or `schema` wasn't qualified and resolved somewhere unexpected. Logging is best-effort and the load still ran. |
| Logged in to the wrong Salesforce org | `my_domain` decides, not `sandbox`. See the warning under [Credentials](#credentials). |
| `Catalog 'main' was not found` (`NO_SUCH_CATALOG_EXCEPTION`) | The catalog name is wrong — often the placeholder `main` left in. Use a name from `SHOW CATALOGS`; see [Find your catalog](#find-your-catalog). |
| `Results for job ... were NOT fully saved to <schema>` | The Salesforce load worked; saving the log didn't. The rest of that line, and `error` in the returned result, name the table and the cause. |
| Log tables not in the catalog browser | Either nothing was saved yet — check `process_bulk_api_results(...)["success"]` — or the browser hasn't refreshed. Reload it. |
