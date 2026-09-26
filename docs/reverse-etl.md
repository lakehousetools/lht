# Reverse ETL: Snowflake → Salesforce

`lht retl` runs a Snowflake `SELECT` and writes the rows to a Salesforce object through a Bulk API 2.0 ingest job. Use it to push lead scores, enrichment, cleaned addresses, account hierarchies, or any model output back to where your sales team works.

```bash
lht retl upsert --sobject Account --match-field External_Id__c \
  --sql "SELECT External_Id__c, Rating, AnnualRevenue FROM ANALYTICS.ACCOUNT_SCORES"
```

## Operations

| Operation | Required columns | Notes |
|---|---|---|
| `upsert` | The `--match-field` column (an External ID field, or `Id`) plus the fields to set | Creates records whose match value isn't found. A blank match value always creates a record. |
| `update` | `Id` plus the fields to set | |
| `insert` | Fields to set | |
| `delete` | `Id` | Soft delete: records go to the Recycle Bin |

Column names in the query must be Salesforce **field API names** (`Industry`, `My_Field__c`). Snowflake folds unquoted names to uppercase; Salesforce matches field names case-insensitively, so `SELECT industry` works.

## NULL handling

By default a `NULL` becomes an empty CSV cell, which Salesforce treats as "don't change this field". To blank a field, pass `--clear-nulls`: lht then sends `#N/A`, which clears it. The match field itself is never turned into `#N/A`.

## Batching

`upsert` reads the query once and sends it in batches of `--batch-size` rows (default 25,000). Each batch is its own Bulk API ingest job.

## Results and logging

- `lht get-job-results JOB_ID` downloads the successful, failed and unprocessed CSVs for any ingest job.
- `--log-results` records job metadata in Snowflake tables in a `LOGS` schema (`LOGS.RETL_HISTORY` and friends), created on first use. Logging is best-effort: a logging failure never aborts the load.

## Tips

- Keep reverse-ETL queries deterministic, and include only the rows that actually changed. That saves API usage and avoids noisy field history.
- Try new jobs in a sandbox first. Salesforce validation rules, triggers and flows all run on Bulk API writes.
- Use `--sql-file` for anything longer than a line, and keep those files in version control next to your dbt models.
