# lht: Lakehouse Tools

**Bring Your Own Data Warehouse.**

lht is an open-source Python library and CLI that moves Salesforce data into Snowflake and pushes it back. It uses the Salesforce Bulk API 2.0 and runs on your own infrastructure, with your own credentials. There is no hosted service and no per-row pricing, and your data doesn't pass through a third party.

[![PyPI](https://img.shields.io/pypi/v/lht.svg)](https://pypi.org/project/lht/)
[![Python](https://img.shields.io/pypi/pyversions/lht.svg)](https://pypi.org/project/lht/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/lakehousetools/lht/actions/workflows/ci.yml/badge.svg)](https://github.com/lakehousetools/lht/actions/workflows/ci.yml)

```bash
pip install lht
lht sync --sobject Account --table ACCOUNT
```

**Supported today:** Salesforce ↔ Snowflake. The connection layer is built so more warehouses can be added; see [Roadmap](#roadmap).

---

## What it does

| | |
|---|---|
| **Salesforce → Snowflake sync** | Full load on the first run. After that, incremental loads use `LastModifiedDate` and a `MERGE` on the record Id. Tables are created for you, with Salesforce field types mapped to Snowflake types. |
| **Reverse ETL (Snowflake → Salesforce)** | `upsert`, `insert`, `update` and `delete` records in Salesforce from any Snowflake `SELECT`. Runs through Bulk API 2.0 ingest jobs, with optional result logging back into Snowflake. |
| **Record merge** | Deduplicate Accounts, Contacts or Leads inside Salesforce from a Snowflake query that returns `MasterId` / `LoserId` pairs. Uses the SOAP `merge()` call, which the Bulk API can't do. `--dry-run` validates the pairs first. |
| **Bulk job management** | List, inspect and delete Bulk API 2.0 jobs, and download their success, failure and unprocessed results. |
| **Headless auth** | Supports the OAuth 2.0 Client Credentials flow and JWT bearer flow for Salesforce, and key-pair (JWT) auth for Snowflake. Credentials can come from a local config file or from your own secret store. |

## Why lht

- **You own the pipeline.** It's a `pip install`, not a SaaS contract. Run it from a laptop, cron, Airflow, Dagster, GitHub Actions, or a Snowflake/Databricks job.
- **Bulk API 2.0 everywhere.** Reads and writes both use Bulk API 2.0, so large objects don't burn through your REST API call limits.
- **Two directions, one tool.** Sync, reverse ETL and merge share the same saved connections.
- **Plain Python, Apache 2.0.** Read it, fork it, extend it.

## Installation

### From PyPI (recommended)

Requires Python 3.9 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install lht
lht --help
```

To upgrade: `pip install --upgrade lht`. To pin a version: `pip install "lht==2.1.1"`.

### From source

```bash
git clone https://github.com/lakehousetools/lht.git
cd lht
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"            # editable install, plus pytest/build/twine
pytest                             # unit tests; no Salesforce or Snowflake needed
```

You can also download a release archive from [GitHub Releases](https://github.com/lakehousetools/lht/releases) or the source distribution from [PyPI](https://pypi.org/project/lht/#files) and run `pip install lht-<version>.tar.gz`.

## Quickstart

### 1. Prepare Salesforce

Create an External Client App (or Connected App) with the **OAuth 2.0 Client Credentials flow** enabled and a run-as user assigned. Note its **Consumer Key**, **Consumer Secret** and your **My Domain** (the part before `.my.salesforce.com`). See [docs/authentication.md](docs/authentication.md) for step-by-step setup, including the JWT bearer flow.

> Start with a sandbox or Developer Edition org. Reverse ETL and merge change data in Salesforce.

### 2. Prepare Snowflake

Create a user with [key-pair authentication](https://docs.snowflake.com/en/user-guide/key-pair-auth) and a role that can use a warehouse and create tables in your target schema:

```sql
CREATE ROLE IF NOT EXISTS LHT_ROLE;
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE LHT_ROLE;
GRANT USAGE ON DATABASE SALESFORCE TO ROLE LHT_ROLE;
GRANT USAGE, CREATE TABLE ON SCHEMA SALESFORCE.RAW TO ROLE LHT_ROLE;
GRANT ROLE LHT_ROLE TO USER LHT_USER;
ALTER USER LHT_USER SET RSA_PUBLIC_KEY = '<contents of rsa_key.pub>';
```

### 3. Save connections

```bash
lht create-connection --snowflake     # account, user, role, warehouse, private key, database, schema
lht create-connection --salesforce    # client id, client secret, My Domain, sandbox y/n
lht list-connections
lht connect my_salesforce             # verify it works
```

Connections are stored in `~/.solomo/connections.toml` with owner-only permissions (`0600`). Snowflake private keys are copied into the same directory.

### 4. Sync

```bash
lht sync --sobject Account --table ACCOUNT --schema RAW
lht sync --sobject Contact --table CONTACT --schema RAW --where "IsDeleted = false"
```

Run the same command again to pick up only records changed since the last sync.

### 5. Push data back (reverse ETL)

```bash
lht retl upsert --sobject Account --match-field External_Id__c \
  --sql "SELECT External_Id__c, Name, Industry FROM ANALYTICS.ACCOUNT_ENRICHED"
```

Column names in the query must match Salesforce field API names.

## Python API

```python
from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info
from lht.salesforce.intelligent_sync import sync_sobject_intelligent
from lht.salesforce import retl

session = create_session(connection_name="my_snowflake")           # Snowpark session
access_info = get_salesforce_access_info("my_salesforce")          # {'access_token', 'instance_url'}

result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Opportunity",
    schema="RAW",
    table="OPPORTUNITY",
)
print(result["sync_method"], result["actual_records"])

retl.upsert(
    session, access_info,
    sobject="Account",
    query="SELECT External_Id__c, Rating FROM ANALYTICS.ACCOUNT_SCORES",
    field="External_Id__c",
)
```

To run without a local config file (CI, Airflow, Snowflake tasks), pass credentials from your secret store directly:

```python
from lht.user.salesforce_auth import get_salesforce_access_info_from_credentials

access_info = get_salesforce_access_info_from_credentials({
    "auth_flow": "jwt_bearer",
    "client_id": os.environ["SF_CLIENT_ID"],
    "username": "integration@example.com",
    "private_key_pem": os.environ["SF_PRIVATE_KEY"],
    "sandbox": True,
})
```

More in [docs/python-api.md](docs/python-api.md) and [examples/](examples/).

## CLI reference

| Command | Purpose |
|---|---|
| `lht create-connection --snowflake \| --salesforce` | Save a connection interactively |
| `lht list-connections` / `edit-connection` / `set-primary NAME` / `connect NAME` | Manage and test connections |
| `lht sync --sobject OBJ --table TABLE [--schema --database --where --force-full-sync --use-stage --stage-name]` | Salesforce → Snowflake |
| `lht retl {upsert,insert,update,delete} --sobject OBJ (--sql SQL \| --sql-file FILE) [--match-field --batch-size --clear-nulls --log-results]` | Snowflake → Salesforce |
| `lht merge --sobject {Account,Contact,Lead} (--sql \| --sql-file) [--dry-run]` | Merge duplicate records in Salesforce |
| `lht list-jobs` / `show-job ID` / `get-job-results ID` / `delete-job ID` | Bulk API 2.0 job management |

Every command accepts `--snowflake NAME` / `--salesforce NAME` to override the primary connection. Full details are in [docs/cli.md](docs/cli.md), or run `lht <command> --help`.

## How incremental sync works

1. If the target table doesn't exist, lht creates it from the SObject describe and runs a full Bulk API 2.0 query.
2. If it exists, lht reads `MAX(LASTMODIFIEDDATE)` from the table and queries only newer records.
3. Result batches load into a temporary table and are `MERGE`d into the target on `ID`.
4. The Bulk API job is deleted afterwards unless you pass `--no-delete-job`.

Queries use `queryAll`, so records deleted in Salesforce arrive with `IsDeleted = true` while they're in the Recycle Bin. Records that are hard-deleted or purged before the next sync aren't seen; run `--force-full-sync` periodically if that matters to you.

## How lht compares

| | lht | Managed ELT services | Hand-written scripts |
|---|---|---|---|
| Where it runs | Your infrastructure | Vendor cloud | Your infrastructure |
| Cost model | Free (Apache 2.0) + your warehouse compute | Subscription / usage-based | Engineering time |
| Salesforce → warehouse | ✅ Bulk API 2.0, incremental | ✅ | You build it |
| Warehouse → Salesforce (reverse ETL) | ✅ Built in | Often a separate product | You build it |
| Record merge / dedupe in Salesforce | ✅ `lht merge` | Rare | You build it |
| Data leaves your control | No | Yes, transits the vendor | No |

lht is a good fit if you already run Snowflake, want Salesforce data there on your own schedule, and want reverse ETL without adding another vendor.

## Security

- Credentials are stored locally in `~/.solomo/` (directory `0700`, files `0600`), or passed in from your own secret store.
- Salesforce secrets are sent in POST bodies, never URLs, and are never logged.
- Every HTTP call has a timeout, and database, schema and table names are validated before they go into SQL.

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Documentation

- [Getting started](docs/getting-started.md)
- [Authentication (Salesforce & Snowflake)](docs/authentication.md)
- [CLI reference](docs/cli.md)
- [Python API](docs/python-api.md)
- [Reverse ETL](docs/reverse-etl.md)
- [Merging records](docs/merge.md)
- [Intelligent sync internals](docs/intelligent_sync_guide.md)
- [FAQ](docs/faq.md)

## Getting help

| I want to… | Go to |
|---|---|
| Ask a question or get setup help | [Discussions → Q&A](https://github.com/lakehousetools/lht/discussions/categories/q-a) |
| Share an idea or how you use lht | [Discussions → Ideas](https://github.com/lakehousetools/lht/discussions/categories/ideas) / [Show and tell](https://github.com/lakehousetools/lht/discussions/categories/show-and-tell) |
| Report a bug or request a feature | [Issues](https://github.com/lakehousetools/lht/issues/new/choose) |
| Report a security vulnerability | [Private report](https://github.com/lakehousetools/lht/security/advisories/new) (see [SECURITY.md](SECURITY.md)) |

Please remove credentials, org names and customer data from anything you post.

## Roadmap

- Additional warehouses (Databricks, BigQuery, Postgres) behind the same CLI
- Hard-delete detection for incremental sync
- Scheduling recipes (Airflow, Dagster, Snowflake Tasks)

Ideas are welcome in [Discussions](https://github.com/lakehousetools/lht/discussions/categories/ideas); pull requests are welcome too.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, tests and the release process. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[Apache License 2.0](LICENSE)
