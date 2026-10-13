# lht: Lakehouse Tools

**Bring Your Own Data Warehouse.**

lht is an open-source Python library and CLI for moving Salesforce data into your warehouse and back, on your own infrastructure. It uses the Salesforce Bulk API 2.0 for every read and write.

```bash
pip install "lht[snowflake]"      # or "lht[databricks]"
```

## What you can do

- **Sync Salesforce → Snowflake**: a full load first, then incremental `MERGE`s on `LastModifiedDate`. Tables and types are created for you. See [Getting started](getting-started.md).
- **Reverse ETL, warehouse → Salesforce**: upsert, insert, update or delete records from any Snowflake or Databricks `SELECT`. See [Reverse ETL](reverse-etl.md).
- **Reverse ETL from Databricks**: the direction Databricks has no connector for, running on your own compute from a notebook or a Job. See [Databricks](databricks.md).
- **Merge duplicate records** in Salesforce from `MasterId` / `LoserId` pairs computed in the warehouse. See [Merging records](merge.md).
- **Manage Bulk API 2.0 jobs**: list, inspect, delete and download results. See [CLI reference](cli.md).

## Where to go next

| I want to… | Read |
|---|---|
| Install lht and run my first sync | [Getting started](getting-started.md) |
| Set up the Salesforce app and Snowflake key pair | [Authentication](authentication.md) |
| Look up a command or flag | [CLI reference](cli.md) |
| Call lht from Python, Airflow or a notebook | [Python API](python-api.md) |
| Push data into Salesforce from Databricks | [Databricks](databricks.md) |
| Understand how incremental sync decides what to load | [Intelligent sync internals](intelligent_sync_guide.md) |
| Find answers to common questions | [FAQ](faq.md) |

## Support

- **Questions and setup help:** [GitHub Discussions → Q&A](https://github.com/lakehousetools/lht/discussions/categories/q-a)
- **Bugs and feature requests:** [GitHub Issues](https://github.com/lakehousetools/lht/issues/new/choose)
- **Security vulnerabilities:** report privately; see [SECURITY.md](https://github.com/lakehousetools/lht/blob/main/SECURITY.md)
