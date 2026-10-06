# Python API

Everything the CLI does is available as plain Python functions. Use the API from notebooks, Airflow or Dagster tasks, Snowflake Python procedures, or your own scripts.

## Sessions and access tokens

```python
from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info

session = create_session(connection_name="my_snowflake")        # snowflake.snowpark.Session
access_info = get_salesforce_access_info("my_salesforce")       # {"access_token": ..., "instance_url": ...}
```

Pass no name to use the primary connection of each type.

### Headless credentials

In CI or an orchestrator, read secrets from your secret manager and pass them in directly. Nothing touches a local config directory.

```python
import os
from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info_from_credentials

session = create_session({
    "account": os.environ["SNOWFLAKE_ACCOUNT"],
    "user": os.environ["SNOWFLAKE_USER"],
    "role": "LHT_ROLE",
    "warehouse": "COMPUTE_WH",
    "database": "SALESFORCE",
    "schema": "RAW",
    "private_key_file": "/run/secrets/snowflake_key.p8",
    "private_key_passphrase": os.environ.get("SNOWFLAKE_KEY_PASSPHRASE"),
})

# Client Credentials flow
access_info = get_salesforce_access_info_from_credentials({
    "auth_flow": "client_credentials",
    "client_id": os.environ["SF_CLIENT_ID"],
    "client_key": os.environ["SF_CLIENT_SECRET"],
    "my_domain": "acme",                      # or "acme--dev.sandbox"
})

# ...or JWT Bearer flow
access_info = get_salesforce_access_info_from_credentials({
    "auth_flow": "jwt_bearer",
    "client_id": os.environ["SF_CLIENT_ID"],
    "username": "integration@acme.com",
    "private_key_pem": os.environ["SF_PRIVATE_KEY"],
    "sandbox": False,
})
```

### Registering credentials under a name, without a file

The headless pattern above works well when a single call site builds the
session. When several call sites need the *same* connection by name — the
way `connection_name="my_snowflake"` works against `connections.toml` —
register it once instead of threading the credentials dict everywhere:

```python
import os
from lht.user.connections import register_connection
from lht.user.auth import create_session

register_connection("prod_snowflake", {
    "connection_type": "snowflake",
    "account": os.environ["SNOWFLAKE_ACCOUNT"],
    "user": os.environ["SNOWFLAKE_USER"],
    "role": "LHT_ROLE",
    "warehouse": "COMPUTE_WH",
    "private_key_file": "/run/secrets/snowflake_key.p8",
})

# Anywhere else in this process, by name -- same as a connections.toml entry:
session = create_session(connection_name="prod_snowflake")
```

`register_connection` takes precedence over a same-named entry in
`connections.toml` if one exists, and never touches the file — safe to
call even when no `connections.toml` is present at all. It's process-local
and not persisted; call it again in any new process that needs it. Pair it
with `unregister_connection(name)` if a long-running process needs to
clear or rotate a registered connection without restarting.

## Sync Salesforce → Snowflake

```python
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Account",
    schema="RAW",
    table="ACCOUNT",
    match_field="ID",            # merge key (default)
    where_clause=None,           # e.g. "IsPersonAccount = false"
    force_full_sync=False,       # True rebuilds the table
    use_stage=False,             # True + stage_name loads through a Snowflake stage
    stage_name=None,
    delete_job=True,             # delete the Bulk API job when done
)
```

`result` is a dict:

```python
{
    "sobject": "Account",
    "target_table": "RAW.ACCOUNT",
    "sync_method": "bulk_api_incremental",   # or bulk_api_full, bulk_api_stage_*
    "estimated_records": 1500,
    "actual_records": 1487,
    "sync_duration_seconds": 45.2,
    "last_modified_date": Timestamp("2026-01-15 10:30:00"),
    "sync_timestamp": Timestamp("2026-01-16 14:20:00"),
    "success": True,
    "error": None,
}
```

To sync several objects in a loop:

```python
for sobject in ["Account", "Contact", "Opportunity", "Case"]:
    r = sync_sobject_intelligent(session, access_info, sobject, schema="RAW", table=sobject.upper())
    print(f"{sobject}: {r['actual_records']} rows via {r['sync_method']}")
```

## Reverse ETL: Snowflake → Salesforce

```python
from lht.salesforce import retl

# Column names must be Salesforce field API names.
retl.upsert(session, access_info, sobject="Account",
            query="SELECT External_Id__c, Rating, Industry FROM ANALYTICS.ACCOUNT_SCORES",
            field="External_Id__c", batch_size=25000, clear_nulls=False)

retl.update(session, access_info, sobject="Contact",
            query="SELECT Id, Title FROM STAGE.CONTACT_FIXES", clear_nulls=True)

retl.insert(session, access_info, sobject="Task",
            query="SELECT WhoId, Subject, ActivityDate FROM STAGE.NEW_TASKS")

retl.delete(session, access_info, sobject="Lead",
            query="SELECT Id FROM STAGE.LEADS_TO_DELETE", field="Id")
```

`clear_nulls=True` sends `NULL` as `#N/A`, which clears the field in Salesforce. Without it, a `NULL` is sent as an empty cell, which Salesforce treats as "leave unchanged".

## Merge records

```python
from lht.salesforce.merge import merge

summary = merge(session, access_info, sobject="Account",
                query="SELECT MasterId, LoserId FROM DEDUPE.ACCOUNT_PAIRS",
                dry_run=True)
```

See [Merging records](merge.md) for the validation rules.

## Bulk API 2.0 jobs

```python
from lht.salesforce import jobs

jobs.list_bulk_api_jobs(access_info)
jobs.get_bulk_api_job(access_info, "750xx000000abcDAAQ")
jobs.get_ingest_job_results(access_info, "750xx000000abcDAAQ")   # successful / failed / unprocessed CSVs
jobs.delete_bulk_api_job(access_info, "750xx000000abcDAAQ")
```
