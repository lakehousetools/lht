# LHT Cleanup Log

Findings from the pre-open-source code review (2026-08-18), covering all 40 files
under `src/lht` (~8,200 lines). Ordered by how much each blocks a confident public
release, not by line count. Check items off as they're fixed.

## High

- [x] **License mismatch.** `LICENSE` was Apache 2.0 while `pyproject.toml` declared
  MIT. Resolved 2026-08-18: standardized on Apache 2.0 (matches the existing LICENSE
  file; patent grant is a better fit for enterprise-facing integration tooling).
  Updated `pyproject.toml:16` classifier and `README.md:407`.
- [x] **Library code calls `exit(0)` on error paths.** Resolved 2026-08-18: added
  `src/lht/exceptions.py` (`LHTError`, `SalesforceAuthError`, `SalesforceAPIError`,
  `UnknownFieldTypeError`) and replaced all three `exit(0)` calls with raises.
  Also fixed a latent bug in `sobjects.py` where the status-code check ran *after*
  `results.json()['retrieveable']`, so a real auth failure would have crashed with
  a confusing `TypeError` before ever reaching the `exit(0)` line — status is now
  checked first. As a side effect, these errors are now caught by the existing
  `except Exception` handlers in `intelligent_sync.py` (e.g. the field-removal retry
  path) instead of hard-killing the process, which is what those handlers were
  written to do all along.
  - `src/lht/salesforce/sobjects.py` (describe)
  - `src/lht/util/field_types.py` (salesforce_field_type)
  - `src/lht/salesforce/query_bapi20.py` (query_status)
- [ ] **Copy-pasted sync execution.** Two ~140-line methods duplicate job-polling and
  cleanup logic; comments literally label them first/second instance.
  - `src/lht/salesforce/intelligent_sync.py:726-837` (`_execute_bulk_api_job_with_id`)
  - `src/lht/salesforce/intelligent_sync.py:839-967` (`_execute_bulk_api_job`)
- [x] **No automated *unit* tests.** Resolved 2026-08-19: added
  `tests/unit/` (35 tests, no network, no credentials, runs as part of a
  plain `pytest`):
  - `test_field_types.py` — Salesforce -> Snowflake/pandas type mapping,
    including the `UnknownFieldTypeError` path and the "strings aren't
    length-bounded" fix.
  - `test_merge.py` — `merge_into_target()`'s SQL generation against a fake
    Snowpark session; regression-tests both bugs fixed on 2026-08-19 (a MERGE
    is actually executed, has both UPDATE and INSERT branches, and no
    identifier is quoted).
  - `test_connections.py` — `connections.toml` save/load/list/delete/primary
    round-trip, with `get_solomo_dir()` monkeypatched to a `tmp_path` so the
    real `~/.solomo` directory is never touched.

  Also a live integration suite exists (`tests/integration/`, 10 tests in
  `test_sync_scenario.py`, run via `pytest -m integration`) that drives the
  real `lht sync` CLI against a live Salesforce org + Snowflake warehouse
  through a full create/update/soft-delete/hard-delete/re-sync lifecycle,
  with explicit duplicate-Id checks at every stage — this is what caught (and
  now regression-tests) the INSERT-vs-MERGE bug. It's not a substitute for
  the unit suite (needs live credentials, excluded from a plain `pytest` run
  via `addopts = "-m 'not integration'"`), but the two together now give both
  a fast PR-gate layer and a real end-to-end check. See `tests/README.md`.

  Not exhaustive — this establishes the pattern and covers the areas
  central to the two bugs just fixed, not every module. More unit coverage
  (e.g. `table_creator.py`'s SQL, `sobjects.describe()`'s field filtering)
  is still worth adding as other items on this list get fixed.
- [x] **`python -m pytest` imports the wrong `lht`.** Found while adding
  `tests/unit/`: running `python -m pytest` from the repo root prepends the
  current directory to `sys.path`, and the dev-convenience `lht.py` script at
  the repo root then shadows the installed `lht` package (`src/lht/`), so
  `import lht` resolves to a script that immediately fails
  (`ModuleNotFoundError: No module named 'lht.cli'; 'lht' is not a package`).
  Whether this actually surfaces depends on module import/caching order, so
  it can look like a flaky, invocation-order-dependent failure rather than a
  deterministic one. The `venv/bin/pytest` console script doesn't add cwd to
  `sys.path` the same way and isn't affected — `tests/integration/README.md`
  already used this form for exactly this reason, so `tests/README.md` now
  says so explicitly for `tests/unit/` too. Not fixed at the root: the
  competing top-level `lht.py` shim (a `python lht.py ...` dev convenience
  predating the `lht` console-script entry point in `pyproject.toml`) is
  still there and will keep tripping up anyone who runs `python -m` from the
  repo root; consider deleting it now that `lht = "lht.cli:main"` gives the
  same thing via a properly installed console script.
- [x] **Client secret sent in the token URL's query string.** Fixed 2026-09-11:
  credentials now travel as a form-encoded POST body to the bare token URL, the wrong
  `Content-Type: application/json` header is gone, and the request has a 60s timeout.
  `tests/unit/test_salesforce_auth.py` (5 tests) pins it: nothing in the URL, the body
  carries all three parameters, and a failed login's exception text holds no secret.
  Verified against a live sandbox — token issued. Original report below. Found 2026-09-11 while
  wiring the RadNet sync. `login_user_flow()` builds the client-credentials request as
  `…/oauth2/token?grant_type=client_credentials&client_id=…&client_secret=…` and POSTs
  it with no body. Query strings are routinely captured by proxies, load balancers and
  server access logs, which a request body is not.
  - `src/lht/user/salesforce_auth.py:58`
  - **The sharper problem is the failure path.** The next line is
    `r.raise_for_status()`, and `requests.HTTPError` includes the full URL in its
    message (`400 Client Error: Bad Request for url: https://…&client_secret=…`). So
    any failed login — wrong secret, expired app, bad domain — puts the secret into
    the exception text, and from there into whatever prints or logs it: the terminal,
    a log file, CI output. That is far more likely to leak it than a proxy log.
  - Fix: POST to the bare token URL with the parameters as a form body —
    `requests.post(url, data={"grant_type": "client_credentials", "client_id": …,
    "client_secret": …})`. `requests` sets `application/x-www-form-urlencoded` itself,
    which is also what the OAuth token endpoint expects; the current
    `Content-Type: application/json` header is wrong for it and should go.
  - Only occurrence in the package (checked with a grep for secrets and tokens in
    URLs). Rotate any secret that has been through a failed login since this shipped.

- [ ] **In-place Cython builds silently shadow edited source.** Found 2026-09-11.
  `BUILD_AND_DISTRIBUTION.md` tells you to run `python setup.py build_ext --inplace`,
  which drops a `.so` next to every `.py` in `src/lht/`. Python imports a compiled
  extension ahead of source in the same directory, and the dev venv is an editable
  install, so **after any later edit the venv keeps running the old compiled code** —
  no error, no warning. Found because a fix to `salesforce_auth.py` had no effect: its
  `.so` dated from 2026-08-19. Six modules were stale that way, five of them carrying
  fixes committed on 2026-09-09 that had therefore never run locally:
  `cli/commands/retl.py`, `salesforce/results_bapi.py`, `salesforce/retl.py`,
  `user/salesforce_auth.py`, `util/csv.py`, `util/log_retl.py`. The stale `.so` files
  were moved out of `src/` so those modules now import from source.
  - It also means **unit tests can pass against stale compiled code** rather than the
    source under test. None of the four stale modules with 2026-09-09 fixes has a unit
    test, so nothing caught it.
  - Published wheels are unaffected as long as they are built fresh by `python -m build`.
  - Fix options: stop building in place in the working tree (build only into `build/`
    for distribution, and let the editable install run source); or add a guard — a
    test, or a check in `publish.sh` — that fails when any `src/lht/**/*.so` is older
    than its `.py`.

- [x] **`.gitignore` swallowed the test suites.** Fixed 2026-09-11. The rule
  `test_*.py`, commented "Test files in root directory", had no leading slash and so
  matched at every depth. **No test file under `tests/` has ever been committed** — the
  repo holds `tests/README.md`, the integration harness and `config.toml`, but none of the
  suites they describe:
  - `tests/unit/test_connections.py`, `test_field_types.py`, `test_merge.py` — the 35
    unit tests that "No automated unit tests" above records as resolved on 2026-08-19.
  - `tests/integration/test_sync_scenario.py` — the 10-test live integration suite.

  They exist only in the working copy they were written in; a fresh clone runs zero tests
  and any CI would pass vacuously. Anchored the rule to `/test_*.py`, which is what its
  comment always meant. `tests/unit/test_salesforce_auth.py` is committed. **The other four
  are now visible to git but deliberately not committed** — each scanned clean of
  credentials (they use fakes, `tmp_path`, and connection *names* from `config.toml`), and
  left for a deliberate `git add` since they are the author's work, not part of this fix.

- [x] **Bulk CSV responses decoded as Latin-1.** Fixed 2026-09-11. Salesforce sends Bulk
  API 2.0 results as UTF-8 under `Content-Type: text/csv` with no charset, and requests
  falls back to ISO-8859-1 for text/* without one — so every `response.text` turned
  multi-byte characters into mojibake. A synced Account named `ACME – NORTH` landed in
  Snowflake as `ACME â€“ NORTH`. Affected the query path (`query_bapi20`, i.e. every
  `lht sync`) and the job-result paths (`results_bapi`, `jobs`, `log_retl`). All now go
  through `util.csv.bulk_csv_text`, which decodes the bytes as UTF-8.
  `tests/unit/test_bulk_csv_encoding.py`. Rows synced before the fix keep the corrupted
  text until a `--force-full-sync`, since their LastModifiedDate has not moved.

- [x] **`retl.upsert` could skip or repeat rows above one batch.** Fixed 2026-09-11. It
  paged the query with `LIMIT/OFFSET` around a subquery, re-running it per batch with no
  outer `ORDER BY`; Snowflake does not promise the same order twice. It now reads the
  query once and cuts the batches in memory. `tests/unit/test_retl.py`.

- [x] **`retl` could never clear a field.** Added 2026-09-11: `--clear-nulls`
  (`clear_nulls=` on `upsert`/`update`). NULL goes out as an empty cell, which Bulk API
  treats as "leave unchanged", so a value the source had emptied stayed in Salesforce. The
  flag sends `#N/A`, which clears it. Opt-in so callers relying on NULL-means-untouched are
  unaffected.

## Medium

- [ ] **Redundant Salesforce API call.** Result-fetching re-runs `sobjects.describe()`
  and silently discards the `snowflake_fields` the caller already computed and
  passed in — doubles a Salesforce API call per sync for no reason.
  `src/lht/salesforce/query_bapi20.py:161,199`
- [ ] **Debug table intentionally never dropped.** A fallback write path creates
  `<table>_DEBUG` via `write_pandas` "for manual inspection" and comments that it
  should not be dropped — litters the target schema on every run that hits this path.
  `src/lht/util/data_writer.py:332-346`
- [ ] **Per-row INSERT loops with hand-rolled SQL escaping.** Success/failure result
  logging issues one `INSERT` per row via string interpolation, re-implementing
  quote-escaping (`.replace(chr(39), chr(39)+chr(39))`) at each call site instead of
  using bind parameters. Slow on jobs with many failures, and fragile.
  `src/lht/salesforce/results_bapi.py:292-381`
- [ ] **Dead legacy sync path still shipped.** An entire earlier pipeline (describe +
  REST query + manual table create) that nothing in the CLI calls anymore —
  `intelligent_sync.py` + `query_bapi20.py` replaced it. Confirm no external caller
  depends on `lht.salesforce.query_records` / `create`, then delete.
  - `src/lht/salesforce/sobject_sync.py`
  - `src/lht/salesforce/sobject_query.py`
  - `src/lht/salesforce/sobject_create.py`

## Low

- [ ] **`print()` used throughout library modules** (418 call sites) alongside real
  logging (509 `logger.*` calls). In modules meant to be imported into other apps —
  `auth.py`, `salesforce_auth.py`, `connections/manager.py` are the worst offenders —
  `print()` pollutes the host app's stdout and can't be filtered or redirected.
  Move to `logger` calls; keep `print()` only in `cli/commands/*`.
- [ ] **Salesforce API version hardcoded inconsistently** — v58.0 in some modules,
  v62.0 in others. Should be one constant.
  - v58.0: `src/lht/salesforce/query_bapi20.py`, `src/lht/salesforce/sobject_create.py`
  - v62.0: `src/lht/salesforce/results_bapi.py`, `src/lht/salesforce/retl.py`,
    `src/lht/salesforce/sobjects.py`
- [ ] **`requirements.txt` doesn't match runtime deps.** Lists packaging/publishing
  tools (twine, build, keyring, Cython) instead of the runtime deps declared in
  `pyproject.toml` (pandas, snowflake-snowpark-python, requests, etc.). A new
  contributor running `pip install -r requirements.txt` won't get a working dev env.
- [ ] **Large blocks of commented-out debug code** left in place. Not a bug, but the
  most visible evidence of "many iterations, no cleanup" to anyone browsing a file.
  - `src/lht/salesforce/intelligent_sync.py`
  - `src/lht/util/field_types.py`
  - `src/lht/util/data_writer.py`

## Bugs found during manual testing (2026-08-19)

- [x] **Case-mismatch broke the incremental-sync date filter.** `table_creator.py`
  created tables with quoted, case-preserving identifiers (`"Account"`), while
  `intelligent_sync.py`'s `_get_last_modified_date()` queried them unquoted
  (`FROM {db}.{schema}.{table}`), which Snowflake case-folds to uppercase
  (`ACCOUNT`). For any table name with lowercase letters, the query silently
  found nothing, `last_modified_date` came back `None`, and every "incremental"
  sync quietly reloaded the entire Salesforce object instead of just what
  changed. Resolved: identifiers are now never quoted anywhere in the sync
  path, and `schema`/`table`/`match_field` are uppercased once at the top of
  `IntelligentSync.sync_sobject()` and flow through consistently from there.
  - `src/lht/util/table_creator.py` (`create_salesforce_table`,
    `_build_create_table_sql`, `ensure_table_exists_for_dataframe`)
  - `src/lht/salesforce/intelligent_sync.py` (`sync_sobject`)
  - `src/lht/salesforce/query_bapi20.py` (`get_bulk_results_direct`)
- [x] **Write path was `INSERT`, not `MERGE` — every sync duplicated rows.**
  `query_bapi20.get_bulk_results_direct()` loaded every batch via a plain
  `INSERT INTO {table} SELECT ... FROM tmp_{table}`, regardless of whether the
  record already existed. `util/merge.py` had a real `MERGE INTO ... WHEN
  MATCHED UPDATE ... WHEN NOT MATCHED INSERT` builder, but nothing in the sync
  path ever executed it - a record that changed in Salesforce and got
  re-synced was appended as a new row instead of updated in place, on every
  sync, full or incremental. Also: `match_field` was accepted as a parameter
  all the way from `sync_sobject()` but silently dropped at
  `_execute_sync_strategy()` and never reached the write path at all.
  Resolved: replaced the two dead, quoted, never-executed merge-builder
  functions in `merge.py` with `merge_into_target()`, which builds and
  *executes* an unquoted, uppercase `MERGE` keyed on `match_field` (default
  `ID`), reusing the existing `transform_and_match_datatypes()` casting logic
  for the source side. `match_field` is now threaded through
  `sync_sobject -> _execute_bulk_api_job(_with_id) -> get_bulk_results ->
  get_bulk_results_direct` and used for every batch, first or subsequent.
  - `src/lht/util/merge.py` (new `merge_into_target`, replaces
    `format_filter_condition` / `format_insert_upsert`)
  - `src/lht/salesforce/query_bapi20.py` (`get_bulk_results`,
    `get_bulk_results_direct`)
  - `src/lht/salesforce/intelligent_sync.py` (`sync_sobject`,
    `_execute_bulk_api_job`, `_execute_bulk_api_job_with_id`)

  Note: `util/data_writer.py`'s `write_batch_to_main_table` /
  `write_batch_to_temp_table` still write via plain append/overwrite, but
  they're only reachable from the dead legacy `sobject_sync.py` path (see
  the "Dead legacy sync path" item above), not from `intelligent_sync.py`,
  so they were left alone. Delete-the-legacy-path is still the right fix
  for those rather than merge-ifying dead code.

## Architecture note (not a bug, worth doing alongside the cleanup)

Before adding a Databricks backend: extract a small write-backend interface out of
`src/lht/util/data_writer.py`, `table_creator.py`, and `merge.py`, which currently
import `snowflake.snowpark.Session` directly and build Snowflake-specific SQL
(`MERGE INTO`, `SHOW TABLES`, `write_pandas`/`save_as_table`). The `salesforce/`
layer is already backend-agnostic — the coupling is isolated to these three files.

---
Full writeup with rationale: see the review artifact shared 2026-08-18.
