# Getting started

This guide takes you from nothing to a Salesforce object synced into Snowflake. It takes about 15 minutes, most of it spent in the Salesforce and Snowflake setup screens.

## 1. Install

lht needs Python 3.9 or newer.

=== "From PyPI"

    ```bash
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install lht
    lht --help
    ```

=== "From source"

    ```bash
    git clone https://github.com/lakehousetools/lht.git
    cd lht
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    lht --help
    ```

`python -m lht --help` works too, which is useful when the `lht` script isn't on your `PATH`.

## 2. Set up credentials

You need:

- **Salesforce:** an External Client App or Connected App with the OAuth 2.0 Client Credentials flow enabled. Note its consumer key and secret, and your My Domain.
- **Snowflake:** a user with an RSA key pair, and a role that can use a warehouse and create tables in the target schema.

Step-by-step instructions are in [Authentication](authentication.md).

!!! warning "Use a sandbox first"
    Syncing only reads from Salesforce, but `lht retl` and `lht merge` change records. Try them in a sandbox or Developer Edition org before production.

## 3. Save connections

```bash
lht create-connection --snowflake
lht create-connection --salesforce
```

Each command prompts for its values and asks whether to make the connection the **primary** one for its type. Commands use the primary connection unless you pass `--snowflake NAME` or `--salesforce NAME`.

```bash
lht list-connections
lht connect my_salesforce
lht connect my_snowflake
```

Connections are saved in `~/.solomo/connections.toml`. The directory is `0700` and the file is `0600`.

## 4. Run your first sync

```bash
lht sync --sobject Account --table ACCOUNT --schema RAW
```

On the first run lht:

1. Describes `Account` and creates `RAW.ACCOUNT` with matching Snowflake column types.
2. Starts a Bulk API 2.0 `queryAll` job for every field.
3. Streams the CSV result pages into Snowflake.
4. Deletes the Bulk job.

Run the same command again and lht loads only records whose `LastModifiedDate` is newer than the latest one in the table, merging them on `ID`.

## 5. Next steps

- Sync a subset: `lht sync --sobject Contact --table CONTACT --where "MailingCountry = 'US'"`
- Rebuild a table from scratch: add `--force-full-sync`
- Push scores or enrichment back into Salesforce: see [Reverse ETL](reverse-etl.md)
- Schedule syncs: lht is a normal CLI, so cron, Airflow `BashOperator`, Dagster, GitHub Actions or any other scheduler works. For headless auth, see [Python API](python-api.md#headless-credentials).
