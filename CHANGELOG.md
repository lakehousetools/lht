# Changelog

All notable changes to lht. Versions follow [semantic versioning](https://semver.org/).

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
