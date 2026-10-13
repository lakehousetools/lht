# Changelog

All notable changes to lht. Versions follow [semantic versioning](https://semver.org/).

## Unreleased

Hardening, from a scan of the repository and its history for leaked secrets (none found).

### Changed

- `lht merge` refuses a Salesforce SOAP reply that declares a DTD or entity, instead of handing it to the XML parser. A SOAP reply never has one; the standard-library parser expands internal entities, so a crafted reply could balloon in memory.
- `lht.util.log_retl.history_query()` (and so `check_log()`) validates the database and schema it formats into SQL with `identifier()`, as the rest of the package does. A bad name now raises `ValueError`.
- `.gitignore` also covers `connections.toml`, `*.pem` and `*.key`, so a config directory pointed inside a clone with `LHT_HOME` can't be committed by accident.

### Removed

- `lht.salesforce.sobject_sync`, which was not imported anywhere and could not have worked: its one function, `new_changed_records()`, called `merge.format_filter_condition()`, which doesn't exist.

## 3.0.0 — 2026-10-13

Databricks reverse ETL, and a warehouse-independent core.

### ⚠️ Upgrading from 2.x

**`pip install lht` no longer installs the Snowflake client.** The warehouse client
is now an extra, because installing Snowpark's pandas and pyarrow pins onto
Databricks compute — where it is never used — can displace the versions the runtime
ships. Change your install to:

```bash
pip install "lht[snowflake]"      # Snowflake: sync, reverse ETL, merge
pip install "lht[databricks]"     # Databricks from a laptop or CI (Python 3.10+)
pip install "lht[all]"            # both
pip install lht                   # on Databricks compute, where `spark` already exists
```

Nothing else changes for Snowflake users: the same CLI, the same Python calls, the
same connections, and the log tables keep exactly the column types they had. A
Snowflake code path without Snowpark installed now fails immediately with
`Connecting to Snowflake needs the Snowpark client [...] pip install "lht[snowflake]"`
rather than an opaque `ModuleNotFoundError`.

### Added

- **Databricks as a warehouse for reverse ETL and merge.** `lht.salesforce.retl.upsert/insert/update/delete` and `lht.salesforce.merge.merge` now accept a Spark session as readily as a Snowpark one, so a Databricks notebook can hand them `spark` directly. Databricks ingests Salesforce well and has no way to write back; this is that direction. See `docs/databricks.md`.
- `lht.warehouse`: the warehouse layer. `from_session(session)` returns the backend for a Snowpark session, a Spark session or a `Warehouse` (idempotent), and each backend owns its own column types, timestamp casts and DDL. Anything else that answers `sql()` is still treated as Snowflake, so callers written before this release behave exactly as they did.
- `lht.warehouse.databricks.connect()`: the running Spark session on Databricks compute, or a Databricks Connect session against a `~/.databrickscfg` profile off-platform — the same profiles the Databricks CLI uses, so there is no lht-side Databricks credential.
- `lht.warehouse.databricks.salesforce_access_info(scope=..., connection_name=...)`: Salesforce credentials from a Databricks secret scope on-platform, falling back to `connections.toml` where there is no `dbutils` to read a scope with. One call, so the same notebook file runs unchanged on a laptop. A scope that *is* reachable but misconfigured raises rather than silently falling back.
- `lht retl` and `lht merge` take `--databricks [PROFILE]` in place of `--snowflake`, mutually exclusive with it.
- **Where the log tables go is now configurable, for all of them.** `process_bulk_api_results(..., schema='LOGS')` places the per-record tables (`JOB_INFO`, `SUCCESS`, `FAILURE`); `retl.upsert/update/insert/delete(..., log_schema='LOGS')` places the job history (`RETL_HISTORY`); and `lht retl --log-schema SCHEMA` sets both. The old behaviour was a hard-coded, unqualified `LOGS`, which on Unity Catalog resolves against whichever catalog the session happens to point at — so there was no way to say `main.lht_logs`. A schema name that is not a usable identifier is reported once as a failed logging result (per-record tables) or as one warning (job history), instead of as four separate warnings from the individual table steps; either way the load itself is unaffected.
- **`RETL_HISTORY`'s schema is now created on first use**, as the table already was. Without it, a run against a database or catalog with no such schema logged a warning and kept no job history. Creating it is best-effort: a role without `CREATE SCHEMA` carries on to the table, since the schema usually exists already. On Snowflake this adds one `CREATE SCHEMA IF NOT EXISTS` statement per ingest job.
- Per-record result logging (`--log-results`, `results_bapi.process_bulk_api_results`) works on both warehouses: `LOGS.JOB_INFO`, `LOGS.SUCCESS` and `LOGS.FAILURE` are created as Delta tables on Databricks and as Snowflake tables on Snowflake, from one set of column definitions.
- `examples/databricks_retl.py`: a notebook/Job/laptop reverse-ETL script that needs no edits between the three.
- `tests/spark/`, marked `spark` and excluded by default: runs lht's generated Databricks SQL against a local Spark engine. Needs `pyspark` and a JVM, no workspace. `pytest -m spark`.

### Changed

- `lht.util.sql.identifier()` also accepts backtick-quoted name parts, for Databricks.
- The `client_credentials` Salesforce flow now warns when `sandbox` is set alongside a `my_domain` that doesn't look like a sandbox. Only the `jwt_bearer` flow has a login URL for that flag to switch; on client credentials the org is whatever `my_domain` names, so a `sandbox` flag there did nothing at all — silently, with the login succeeding against the other org. The flag still changes no behaviour (`my_domain` decides); it is the silence that's fixed.
- `lht.util.__init__` and `lht.salesforce.__init__` resolve their exports on first access instead of at import time, so importing the reverse-ETL path no longer pulls in the Snowflake writers (and with them Snowpark). The names they export are unchanged.
- `insert_failure_records()` no longer raises when the insert fails. It was the odd one out: `insert_success_records()` and `insert_job_info()` only logged. All three now report through an optional `problems` list, which `process_bulk_api_results` turns into its result; the three `create_*_table()` functions take a matching `notes` list.
- `lht.util.sql.identifier()` says `Not a valid SQL identifier`, not `Snowflake identifier`, now that it also guards Databricks names.
- `retl.delete()`'s `field` argument is now optional. Bulk API 2.0 deletes by `Id` only and the argument was already unused; callers passing it still work.
- `retl.insert()` no longer routes through `lht.sflake.query.get_records()`. Same behaviour — a NULL is an empty cell, since an insert has no existing value to clear.

### Fixed

- **The `lht` command no longer crashes when Snowpark isn't installed.** The entry point imports every command's module on startup, and `lht sync`'s imported the Snowflake writers at the top of the file, so on a core-only install — which is what a Databricks cluster, or a `lht[databricks]`-only laptop, has — every command failed with `No module named 'snowflake'` before parsing an argument, `lht retl --databricks` included. That import now happens inside `lht sync`, which, being Snowflake-only, says `pip install "lht[snowflake]"` if it is missing. Every other command works without Snowpark. Found by installing the built wheel in a clean environment; the earlier import guard covered the library but not the CLI, and now a test runs every subcommand with Snowpark made unimportable.
- **`process_bulk_api_results` no longer reports success when it saved nothing.** Every step in it swallows its own exception, by design, so that a logging problem can never fail a load that already reached Salesforce — but nothing then told the caller, and it returned `success: True` with the tables missing. It now returns `success: False` and an `error` when an insert failed, naming each thing that could not be saved, and logs one `NOT fully saved` error line. The verdict rests on the inserts: a role that cannot `CREATE TABLE` but can write to existing tables is still a success, with the refused `CREATE` as a warning, and with nothing to insert there is nothing to fail. `lht retl --log-results` prints this as `Logging failed`. This predates the Databricks work and applies to Snowflake too.
- **The `SUCCESS` column in the `SUCCESS` table is now filled.** It was read from an `sf__Success` field that Salesforce's `successfulResults` CSV does not have (it carries `sf__Id` and `sf__Created`, then the submitted fields), so it has always been `NULL`. A row in that CSV is a success by definition, so it is now `TRUE`; an explicit `sf__Success`, if a caller passes one, is still honoured. Rows already logged keep their `NULL`; to backfill them: `UPDATE <schema>.SUCCESS SET SUCCESS = TRUE WHERE SUCCESS IS NULL`.
- **Errors from the warehouse are now one short line, not a stack trace.** Databricks follows each message with a hundred-frame JVM stack trace, sometimes a dump of the query plan, which in a notebook buried the line that said what went wrong. Log lines and the returned `error` now keep the message up to its `SQLSTATE` and drop the rest (`lht.warehouse.base.brief_error`).
- **String escaping is now per-warehouse**, and `Warehouse.literal()` owns it. Spark concatenates adjacent string literals, so the SQL standard's doubled quote (`'it''s'`) parses as `'it'` followed by `'s'` and evaluates to `its` — the quote is dropped with no error at all. Any Salesforce value or error message with an apostrophe would have been logged corrupted on Databricks. Backslashes are escaped too, since inside a Spark literal `\b` is a backspace rather than two characters. Snowflake's escaping is unchanged. Found by running the generated SQL against a real Spark engine; `tests/spark/` (`pytest -m spark`) now keeps doing that.
- `connect()` finds a running Spark session from any thread. `SparkSession.getActiveSession()` is thread-local and answers `None` off the thread that created the session, which a notebook cell can easily be — lht would then have tried to start a Databricks Connect session and failed with "No Spark session is running" on a perfectly good cluster. It now asks `active()` first and falls back.
- A Bulk API counter of **0** is now logged as `0` in `LOGS.JOB_INFO`, not `NULL`. `job_data.get(...) or 'NULL'` treated a genuine zero as missing, so a job that processed no records was indistinguishable from one lht could not read at all. A non-numeric counter still logs as `NULL`, with a debug line.
- `LOGS.JOB_INFO`'s `STATE` is escaped on the error path, where it was previously interpolated into the INSERT unescaped.

### Removed

- Unused Snowpark imports: `lht.util.log_retl` (`Session`, `col`), `lht.salesforce.results_bapi` (`Session`, `SnowparkSQLException`) and `lht.util.merge` (`Session`, `functions as F`). The whole unit suite now runs with Snowpark absent.

## 2.2.0 — 2026-10-06

### Added
- **Config directory renamed to `~/.lakehousetools`**, matching the project's name. Resolution order: `LHT_HOME` env var (if set, used as-is) → `~/.lakehousetools` (if it exists) → `~/.solomo` (if it exists, for anything upgrading from before this change) → `~/.lakehousetools` (the default for everything new). `get_lht_home()` is the preferred name for this; `get_solomo_dir()` is unchanged and kept for backward compatibility.
- `lht.user.connections.register_connection(name, credentials)` and `unregister_connection(name)` — register credentials in memory under a name, so `create_session(connection_name=...)` and `get_salesforce_access_info(connection_name=...)` work without `connections.toml` on disk at all. Takes precedence over a same-named file entry when both exist. Not persisted.

## 2.1.1 — 2026-09-26

lht is now developed in the open under the Apache 2.0 license. Tagline: **Bring Your Own Data Warehouse**.

### Changed
- **Readable Python on PyPI.** The wheel is now pure Python (`py3-none-any`). It is no longer Cython-compiled, and the source is no longer stripped. One wheel works on every platform, and editable installs can't be shadowed by stale `.so` files.
- `pyarrow` now comes from `snowflake-snowpark-python[pandas]`, so its version always matches what the Snowflake connector supports. `tomli` is added on Python < 3.11.
- `python -m lht` runs the CLI. `lht.__version__` is available.
- Project metadata: correct GitHub URLs, author, keywords and classifiers, and an SPDX license expression.

### Security
- `~/.solomo/connections.toml` is written with mode `0600`, and `~/.solomo/` is tightened to `0700` on every save. Previously the file was created with the default umask, often world-readable, although it holds client secrets and key passphrases.
- Every Salesforce HTTP call now has a timeout (`lht.util.http.DEFAULT_TIMEOUT`). A dropped connection used to hang a sync forever.
- Database, schema and table names are validated by `lht.util.sql.identifier()` before being formatted into SQL. Job Ids written to `LOGS.JOB_INFO` are escaped.
- Removed exact-pinned `requirements.txt`, which was the source of the Dependabot alerts.

### Docs
- New README, a docs site (`mkdocs.yml`, `docs/`), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, `AGENTS.md`, `llms.txt`, examples, and GitHub CI, issue and PR templates.
- Removed `docs/salesforce_sync_guide.md`, which documented classes that don't exist, and the unused Sphinx scaffolding.
- Integration tests read `tests/integration/config.toml`, now gitignored, from the tracked `config.example.toml`.

## 2.0.81 – 2.0.82

### Security
- **Salesforce credentials go in the request body, not the URL** (`bd1ef0b`). `login_user_flow()`
  put `client_id` and `client_secret` in the token request's query string, where proxies and access
  logs keep them, and `raise_for_status()` echoed the full URL into the exception, so a failed login
  printed the secret. Now a form-encoded POST to the bare token URL, the wrong
  `Content-Type: application/json` header removed, and a 60 s timeout. Anyone whose secret went
  through a failed login before this should rotate it.

### Fixed
- **Bulk API CSV decoded as UTF-8** (`58eee64`). Salesforce sends `text/csv` with no charset and
  `requests` falls back to ISO-8859-1, so non-ASCII text (an en dash, accented names) was stored as
  mojibake by every `lht sync`, and by the retl result paths. All go through
  `util.csv.bulk_csv_text`. Rows synced before the fix stay corrupted until a `--force-full-sync`.
- **`retl upsert` could skip or repeat rows** (`b79104d`). It paged the query with `LIMIT/OFFSET`
  and no outer `ORDER BY`, re-running it per batch. It now reads the query once and batches in memory.
- **Sync kept the strings `NA`, `N/A`, `None`, `nan`, `null`** (`7643c64`). pandas' default NA
  parsing turned them into NULL. Only an empty cell is NULL now, which is how the Bulk API writes one.
- **`LOGS.RETL_HISTORY` is created on first use** (`7643c64`); the insert used to fail silently.
- **Reverse-ETL results traceable to source records** (`55ad79e`). Result parsing read columns by
  position and dropped the external ID Salesforce echoes back; both parsers now match by header name
  and record `MATCH_FIELD` / `MATCH_ID`. Also: `RETL_HISTORY` logging re-enabled at all call sites
  (a logging failure cannot abort an ingest), a hard-coded database name removed from
  `history_query`, DataFrames aligned to the destination table before `write_pandas`, and per-record
  INSERTs replaced with chunked multi-row VALUES.
- **Sync path threads `database`, `force_full_sync` and `match_field` through** (`c707c2b`);
  `merge.py` reduced to one `merge_into_target` helper.
- **`.gitignore` hid every test file** (`bd1ef0b`, `a137a5f`): `test_*.py` matched at all depths.
  Anchored to the repo root, and the unit and integration suites that had never been committed are
  now tracked.

### Added
- **Salesforce JWT bearer flow** (`c620853`): `get_salesforce_access_info_from_credentials()` accepts
  `auth_flow='jwt_bearer'` for unattended jobs that authenticate with a certificate and pass
  credentials directly instead of reading `connections.toml`.
- **`lht retl --clear-nulls`** (`b79104d`, `ded68de`; `clear_nulls=` on `retl.upsert` / `update`).
  A NULL is sent as `#N/A`, which clears the field; without the flag it is an empty cell, which the
  Bulk API treats as "leave unchanged". Opt-in, so existing callers are unaffected. The upsert's
  match field is never turned into `#N/A` — a blank match value is how a row asks to be created
  (e.g. upserting on `Id`).
- `src/lht/exceptions.py` and `publish.sh` (`c707c2b`, `55ad79e`).

### Added: `lht merge`
- **`lht merge`** (`b34474e`, `1906f86`): merges Salesforce records in Salesforce from a Snowflake
  query returning `MasterId` / `LoserId` pairs, via SOAP `merge()` (the Bulk API cannot merge).
  Pairs are validated before anything is sent (malformed or missing Ids, self-merge by 15-character
  Id, a loser listed twice, a record that is both master and loser); losers are grouped two per
  request and 200 requests per call; `--dry-run` validates without calling Salesforce; exits
  non-zero if any merge fails. Unit tests in `test_merge_records.py`.
- Behaviour confirmed in a sandbox: the loser goes to the Recycle Bin with `MasterRecordId` set, its
  related records (relationships, Tasks) move to the master, and **the master keeps only its own
  field values** — none of the loser's fields are copied, blanks included. Salesforce refuses to
  merge two accounts that both relate to the same contact (`MERGE_FAILED`); remove the loser's
  redundant AccountContactRelation first.

### Tests
- Unit: `test_salesforce_auth.py` (credentials never in the URL or exception text),
  `test_bulk_csv_encoding.py`, `test_retl.py` (single read, NULL handling, match field), `test_merge_records.py`, plus the
  previously uncommitted `test_connections.py`, `test_field_types.py`, `test_merge.py`.
- Integration: `tests/integration/` (live Salesforce + Snowflake; connection names only in
  `config.toml`).

### Known issues
- `retl update` / `insert` / `delete` with no rows still start a Bulk job, which cannot succeed.
- `log_retl.log_results` writes `LOGS.RETL_RESULTS` / `RETL_FAILURES`, which nothing creates.
- `lht sync` reports a record count that ignores `--where`.
- lht's integration-test hard-delete helper calls `DELETE /sobjects/RecycleBin`, which returns 404;
  purging the Recycle Bin needs SOAP `emptyRecycleBin`.
