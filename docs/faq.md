# FAQ

### How do I get Salesforce data into Snowflake with Python?

Install lht (`pip install lht`), save a Snowflake connection and a Salesforce connection with `lht create-connection`, then run `lht sync --sobject Account --table ACCOUNT`. lht creates the table, loads every record through the Bulk API 2.0, and loads only changes on later runs. See [Getting started](getting-started.md).

### Is lht an alternative to Fivetran, Airbyte or other managed connectors?

For Salesforce ↔ Snowflake, yes. lht covers extraction, incremental loads and reverse ETL, and runs on your own infrastructure under the Apache 2.0 license. It doesn't provide a hosted UI, a scheduler, or connectors for other SaaS sources; pair it with the scheduler you already use.

### Does lht work with Databricks, BigQuery, Redshift or Postgres?

Not yet. Snowflake is the only warehouse supported today. The tagline, "Bring Your Own Data Warehouse", is the direction, and other warehouses are on the [roadmap](https://github.com/lakehousetools/lht#roadmap). Contributions are welcome.

### How much of my Salesforce API limit does a sync use?

Very little. A Bulk API 2.0 query job costs a handful of API calls however many records it returns: create the job, poll it, fetch the result pages, delete the job. Bulk API 2.0 has its own daily limits on jobs and records processed; see Salesforce's [Bulk API 2.0 limits](https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/salesforce_app_limits_platform_bulkapi.htm).

### How are deleted records handled?

Syncs use `queryAll`, so records deleted in Salesforce arrive with `ISDELETED = TRUE` while they're in the Recycle Bin. Records that are hard-deleted or purged between syncs aren't seen by an incremental sync; run `--force-full-sync` periodically if you need them removed.

### Which fields are synced?

All fields the integration user can read on that object, except compound fields (addresses and geolocations are synced as their component fields). Filter rows with `--where`.

### How are Salesforce types mapped to Snowflake?

Text, picklist, Id and reference fields become `VARCHAR`; numbers, currency and percentages become `NUMBER`; checkboxes become `BOOLEAN`; dates become `DATE`; datetimes become `TIMESTAMP_NTZ`. Text is decoded as UTF-8, and an empty cell becomes `NULL`. Literal strings such as `NA` or `null` are kept as text.

### Can I run lht inside Snowflake, Airflow or GitHub Actions?

Yes. It's a normal Python package. Use `create_session(credentials_dict)` / `get_salesforce_access_info_from_credentials()`, or `register_connection(name, credentials_dict)` if you want to refer to it by name afterward, with secrets from your platform instead of a local config directory. See [Python API](python-api.md#headless-credentials).

### Where are my credentials stored?

In `connections.toml` under lht's config directory (`0600`), with private keys copied alongside. Nothing is sent anywhere except Salesforce and Snowflake. See [Authentication](authentication.md#where-credentials-live) for exactly which directory that is and how to override it.

### Why was the config directory called `.solomo`?

lht was first built at [Solomo](https://solomo.io). As of this writing the default is `~/.lakehousetools`, matching the project's current name — `~/.solomo` still works if it's what an existing install already has (see [Authentication](authentication.md#where-credentials-live) for the exact precedence), so upgrading doesn't break anything already set up.
