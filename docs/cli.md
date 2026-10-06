# CLI reference

Every command reads saved connections from `connections.toml` in lht's config directory (`~/.lakehousetools` by default — see [Authentication](authentication.md#where-credentials-live) for the full resolution order and how to override it). Snowflake and Salesforce commands use the **primary** connection of each type unless you pass `--snowflake NAME` or `--salesforce NAME`.

Run `lht <command> --help` for the same text shown here, or use `python -m lht` in place of `lht`.

## Common recipes

```bash
# Sync one object, then keep it fresh incrementally
lht sync --sobject Opportunity --table OPPORTUNITY --schema RAW

# Rebuild a table from scratch
lht sync --sobject Account --table ACCOUNT --force-full-sync

# Push a Snowflake query into Salesforce, matching on an external ID
lht retl upsert --sobject Account --match-field External_Id__c --sql-file account_scores.sql

# Clear fields in Salesforce where the query returns NULL
lht retl update --sobject Contact --sql "SELECT Id, Title FROM STAGE.CONTACT_FIXES" --clear-nulls

# Preview a merge without changing anything
lht merge --sobject Account --sql-file dedupe_pairs.sql --dry-run
```

## `lht create-connection`

```text
usage: lht create-connection [-h] (--snowflake | --salesforce)

Create and save a new connection configuration

options:
  -h, --help    show this help message and exit
  --snowflake   Create a Snowflake connection
  --salesforce  Create a Salesforce connection
```

## `lht list-connections`

```text
usage: lht list-connections [-h]

Display all saved connection configurations

options:
  -h, --help  show this help message and exit
```

## `lht edit-connection`

```text
usage: lht edit-connection [-h]

Edit an existing connection configuration

options:
  -h, --help  show this help message and exit
```

## `lht set-primary`

```text
usage: lht set-primary [-h] connection_name

Set a connection as the primary/default connection for Snowflake or Salesforce

positional arguments:
  connection_name  Name of the connection to set as primary

options:
  -h, --help       show this help message and exit
```

## `lht connect`

```text
usage: lht connect [-h] connection_name

Verify a saved connection by attempting to connect and perform a basic
operation

positional arguments:
  connection_name  Name of the connection to verify

options:
  -h, --help       show this help message and exit
```

## `lht sync`

```text
usage: lht sync [-h] --sobject SOBJECT --table TABLE [--schema SCHEMA]
                [--database DATABASE] [--snowflake NAME] [--salesforce NAME]
                [--match-field MATCH_FIELD] [--use-stage]
                [--stage-name STAGE_NAME] [--force-full-sync]
                [--force-bulk-api] [--existing-job-id EXISTING_JOB_ID]
                [--no-delete-job] [--where WHERE]

Synchronize a Salesforce SObject to a Snowflake table

options:
  -h, --help            show this help message and exit
  --sobject SOBJECT     Salesforce object name (e.g., Account, Contact)
  --table TABLE         Snowflake table name
  --schema SCHEMA       Snowflake schema (defaults to connection if available)
  --database DATABASE   Snowflake database (defaults to connection if
                        available)
  --snowflake NAME      Snowflake connection name (defaults to primary
                        connection)
  --salesforce NAME     Salesforce connection name (defaults to primary
                        connection)
  --match-field MATCH_FIELD
                        Field to use for matching records (default: ID)
  --use-stage           Use Snowflake stage for large datasets
  --stage-name STAGE_NAME
                        Snowflake stage name (required if --use-stage is
                        specified)
  --force-full-sync     Force a full sync regardless of previous sync status
  --force-bulk-api      Force use of Bulk API 2.0 instead of regular API
  --existing-job-id EXISTING_JOB_ID
                        Optional existing Bulk API job ID to use
  --no-delete-job       Do not delete the Bulk API job after completion
  --where WHERE         Optional SOQL WHERE clause to append to the Salesforce
                        query (e.g., "IsPersonAccount = False")
```

## `lht retl`

```text
usage: lht retl [-h] --sobject SOBJECT (--sql SQL | --sql-file SQL_FILE)
                [--match-field MATCH_FIELD] [--batch-size BATCH_SIZE]
                [--snowflake NAME] [--salesforce NAME] [--clear-nulls]
                [--log-results] [-v]
                {upsert,insert,update,delete}

Push rows from a Snowflake SQL query into a Salesforce SObject using Bulk API
2.0 ingest

positional arguments:
  {upsert,insert,update,delete}
                        Operation to perform in Salesforce

options:
  -h, --help            show this help message and exit
  --sobject SOBJECT     Salesforce object name (e.g., Account)
  --sql SQL             Snowflake SQL SELECT that outputs Salesforce field
                        columns
  --sql-file SQL_FILE   Path to a file containing the Snowflake SQL SELECT
  --match-field MATCH_FIELD
                        External ID field for matching records (required for
                        upsert)
  --batch-size BATCH_SIZE
                        Upsert batch size (default: 25000)
  --snowflake NAME      Snowflake connection name (defaults to primary
                        connection)
  --salesforce NAME     Salesforce connection name (defaults to primary
                        connection)
  --clear-nulls         Send NULL as #N/A so Salesforce clears the field
                        (upsert/update). Without it a NULL is an empty cell,
                        which Salesforce treats as 'leave unchanged'
  --log-results         (Best-effort) Log ingest results into Snowflake LOGS
                        schema tables
  -v, --verbose         Show detailed progress and debug output
```

## `lht merge`

```text
usage: lht merge [-h] --sobject SOBJECT (--sql SQL | --sql-file SQL_FILE)
                 [--snowflake NAME] [--salesforce NAME] [--dry-run] [-v]

Merge Salesforce records inside Salesforce using the SOAP API merge() call.
The query returns one row per record to merge away: MasterId survives, LoserId
is merged into it. The master keeps its field values; the loser's related
records move to it. Exits non-zero if any merge fails. Salesforce refuses to
merge accounts that both relate to the same contact: remove the loser's
redundant AccountContactRelation first.

options:
  -h, --help           show this help message and exit
  --sobject SOBJECT    Salesforce object whose records are merged (Account,
                       Contact or Lead)
  --sql SQL            Snowflake SQL SELECT returning MasterId and LoserId
                       columns
  --sql-file SQL_FILE  Path to a file containing the Snowflake SQL SELECT
  --snowflake NAME     Snowflake connection name (defaults to primary
                       connection)
  --salesforce NAME    Salesforce connection name (defaults to primary
                       connection)
  --dry-run            Validate the pairs and report the merge requests
                       without sending anything to Salesforce
  -v, --verbose        Show detailed progress and debug output
```

## `lht list-jobs`

```text
usage: lht list-jobs [-h] [--salesforce NAME] [--api-version API_VERSION]

List all Bulk API 2.0 query jobs from Salesforce

options:
  -h, --help            show this help message and exit
  --salesforce NAME     Salesforce connection name (defaults to primary
                        connection)
  --api-version API_VERSION
                        Salesforce API version (default: v58.0)
```

## `lht show-job`

```text
usage: lht show-job [-h] [--salesforce NAME] [--api-version API_VERSION]
                    job_id

Show detailed information about a specific Bulk API 2.0 query job from
Salesforce

positional arguments:
  job_id                The ID of the Bulk API 2.0 job to retrieve

options:
  -h, --help            show this help message and exit
  --salesforce NAME     Salesforce connection name (defaults to primary
                        connection)
  --api-version API_VERSION
                        Salesforce API version (default: v58.0)
```

## `lht get-job-results`

```text
usage: lht get-job-results [-h] [--salesforce NAME]
                           [--api-version API_VERSION]
                           job_id

Download successfulResults, failedResults, and unprocessedrecords for a Bulk
API 2.0 ingest job

positional arguments:
  job_id                The ID of the Bulk API 2.0 ingest job

options:
  -h, --help            show this help message and exit
  --salesforce NAME     Salesforce connection name (defaults to primary
                        connection)
  --api-version API_VERSION
                        Salesforce API version (default: v58.0)
```

## `lht delete-job`

```text
usage: lht delete-job [-h] [--salesforce NAME] [--api-version API_VERSION]
                      job_id

Delete a specific Bulk API 2.0 query job from Salesforce

positional arguments:
  job_id                The ID of the Bulk API 2.0 job to delete

options:
  -h, --help            show this help message and exit
  --salesforce NAME     Salesforce connection name (defaults to primary
                        connection)
  --api-version API_VERSION
                        Salesforce API version (default: v58.0)
```

