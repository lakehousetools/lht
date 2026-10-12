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

## Developing locally, running in a notebook

The same file can run both places, which is the point of `connect()` and `salesforce_access_info()` taking no arguments that only make sense in one of them.

Locally, lht uses **Databricks Connect** against a `~/.databrickscfg` profile — the same file and profiles the Databricks CLI uses. There is no lht-side credential for Databricks at all.

```bash
pip install "lht[databricks]"
databricks auth login --host https://my-workspace.cloud.databricks.com
```

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

`--log-results`, or `lht.salesforce.results_bapi.process_bulk_api_results()`, writes per-record outcomes to a `LOGS` schema in Unity Catalog: `LOGS.JOB_INFO`, `LOGS.SUCCESS` and `LOGS.FAILURE`, created as Delta tables on first use. Pass the match field and each row records which source record produced which Salesforce Id — or which error.

```python
from lht.salesforce.results_bapi import process_bulk_api_results

result = retl.upsert(warehouse, access_info, "Account", query, "Ext__c")
for batch in result["batch_results"]:
    if batch.get("job_id"):
        process_bulk_api_results(warehouse, access_info, batch["job_id"], match_field="Ext__c")
```

```sql
SELECT match_id AS external_id, sf_error
FROM logs.failure
WHERE job_id = '750...'
```

Logging is best-effort: if the `LOGS` schema isn't writable, the load still completes and the failure is a warning. Create the schema where your catalog wants it, or use a catalog your cluster can write to.

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
| `Table or view not found` on a `LOGS` table | The catalog or schema isn't writable by the cluster. Logging is best-effort and the load still ran. |
