# Reverse ETL: warehouse → Salesforce

`lht retl` runs a `SELECT` against your warehouse and writes the rows to a Salesforce object through a Bulk API 2.0 ingest job. Use it to push lead scores, enrichment, cleaned addresses, account hierarchies, or any model output back to where your sales team works.

```bash
lht retl upsert --sobject Account --match-field External_Id__c \
  --sql "SELECT External_Id__c, Rating, AnnualRevenue FROM ANALYTICS.ACCOUNT_SCORES"
```

Snowflake is the default. Add `--databricks [PROFILE]` to read from Databricks instead; everything on this page applies to both. In a notebook, use the Python API — see [Databricks](databricks.md).

## Operations

| Operation | Required columns | Notes |
|---|---|---|
| `upsert` | The `--match-field` column (an External ID field, or `Id`) plus the fields to set | Creates records whose match value isn't found. A blank match value always creates a record. |
| `update` | `Id` plus the fields to set | |
| `insert` | Fields to set | |
| `delete` | `Id` | Soft delete: records go to the Recycle Bin |

Column names in the query must be Salesforce **field API names** (`Industry`, `My_Field__c`). Snowflake folds unquoted names to uppercase and Spark SQL keeps your aliases as written; Salesforce matches field names case-insensitively either way, so `SELECT industry` works on both.

## NULL handling

By default a `NULL` becomes an empty CSV cell, which Salesforce treats as "don't change this field". To blank a field, pass `--clear-nulls`: lht then sends `#N/A`, which clears it. The match field itself is never turned into `#N/A`.

## Batching

`upsert` reads the query once and sends it in batches of `--batch-size` rows (default 25,000). Each batch is its own Bulk API ingest job.

## Results and logging

- `lht get-job-results JOB_ID` downloads the successful, failed and unprocessed CSVs for any ingest job.
- `--log-results` records job metadata and per-record outcomes in a `LOGS` schema in the warehouse (`RETL_HISTORY`, `JOB_INFO`, `SUCCESS`, `FAILURE`), created on first use — as Snowflake tables or Delta tables, depending on the warehouse. Pass `--match-field` and each row records which source record produced which Salesforce Id. Logging is best-effort: a logging failure never aborts the load.
- `--log-schema` puts those tables somewhere other than a bare `LOGS`, and covers all of them: the job history (`RETL_HISTORY`, written on every run) as well as the per-record tables. Worth setting on Databricks, where an unqualified name resolves against whichever catalog the session points at: `--log-schema main.lht_logs`. The schema is created on first use if it does not exist.

## Tips

- Keep reverse-ETL queries deterministic, and include only the rows that actually changed. That saves API usage and avoids noisy field history. It also keeps memory down: the query is read once and held while it is cut into batches, because re-reading it per batch without an `ORDER BY` could send a row twice or skip it.
- Try new jobs in a sandbox first. Salesforce validation rules, triggers and flows all run on Bulk API writes.
- Use `--sql-file` for anything longer than a line, and keep those files in version control next to your dbt models.
