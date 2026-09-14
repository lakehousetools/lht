# Changelog

Changes since **2.0.80** (the version on TestPyPI). Nothing below has been released yet;
`pyproject.toml` still says 2.0.80. Commit hashes are in this repository. The reasoning for each
change is in its commit message; open and resolved findings are tracked in `ISSUES.md`.

## Unreleased — on `main`

### Security
- **Salesforce credentials go in the request body, not the URL** (`3bae355`). `login_user_flow()`
  put `client_id` and `client_secret` in the token request's query string, where proxies and access
  logs keep them, and `raise_for_status()` echoed the full URL into the exception, so a failed login
  printed the secret. Now a form-encoded POST to the bare token URL, the wrong
  `Content-Type: application/json` header removed, and a 60 s timeout. Anyone whose secret went
  through a failed login before this should rotate it.

### Fixed
- **Bulk API CSV decoded as UTF-8** (`df2308c`). Salesforce sends `text/csv` with no charset and
  `requests` falls back to ISO-8859-1, so non-ASCII text (an en dash, accented names) was stored as
  mojibake by every `lht sync`, and by the retl result paths. All go through
  `util.csv.bulk_csv_text`. Rows synced before the fix stay corrupted until a `--force-full-sync`.
- **`retl upsert` could skip or repeat rows** (`8404203`). It paged the query with `LIMIT/OFFSET`
  and no outer `ORDER BY`, re-running it per batch. It now reads the query once and batches in memory.
- **Sync kept the strings `NA`, `N/A`, `None`, `nan`, `null`** (`e1db8c8`). pandas' default NA
  parsing turned them into NULL. Only an empty cell is NULL now, which is how the Bulk API writes one.
- **`LOGS.RETL_HISTORY` is created on first use** (`e1db8c8`); the insert used to fail silently.
- **Reverse-ETL results traceable to source records** (`b93a0ce`). Result parsing read columns by
  position and dropped the external ID Salesforce echoes back; both parsers now match by header name
  and record `MATCH_FIELD` / `MATCH_ID`. Also: `RETL_HISTORY` logging re-enabled at all call sites
  (a logging failure cannot abort an ingest), a hard-coded database name removed from
  `history_query`, DataFrames aligned to the destination table before `write_pandas`, and per-record
  INSERTs replaced with chunked multi-row VALUES.
- **Sync path threads `database`, `force_full_sync` and `match_field` through** (`9ff19a2`);
  `merge.py` reduced to one `merge_into_target` helper.
- **`.gitignore` hid every test file** (`3bae355`, `d1dfe97`): `test_*.py` matched at all depths.
  Anchored to the repo root, and the unit and integration suites that had never been committed are
  now tracked.

### Added
- **`lht retl --clear-nulls`** (`8404203`, `20246b6`; `clear_nulls=` on `retl.upsert` / `update`).
  A NULL is sent as `#N/A`, which clears the field; without the flag it is an empty cell, which the
  Bulk API treats as "leave unchanged". Opt-in, so existing callers are unaffected. The upsert's
  match field is never turned into `#N/A` — a blank match value is how a row asks to be created
  (e.g. upserting on `Id`).
- `src/lht/exceptions.py`, `publish.sh`, and build/local-install notes in
  `BUILD_AND_DISTRIBUTION.md` (`9ff19a2`, `b93a0ce`).

### Added: `lht merge`
- **`lht merge`** (`8b3e675`, `1f8275f`): merges Salesforce records in Salesforce from a Snowflake
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

### Logged in `ISSUES.md`, not yet fixed
- `retl update` / `insert` / `delete` with no rows still start a Bulk job, which cannot succeed.
- `log_retl.log_results` writes `LOGS.RETL_RESULTS` / `RETL_FAILURES`, which nothing creates.
- `lht sync` reports a record count that ignores `--where`.
- Dependabot: 7 alerts from exact pins in `requirements.txt` (4 high, urllib3).
- In-place Cython builds (`python setup.py build_ext --inplace`) leave `.so` files that shadow
  edited `.py` source in an editable install — edits silently do not run.
- lht's integration-test hard-delete helper calls `DELETE /sobjects/RecycleBin`, which returns 404;
  purging the Recycle Bin needs SOAP `emptyRecycleBin`. (Not in `ISSUES.md`.)
