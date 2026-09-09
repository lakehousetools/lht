# Integration tests

Live, end-to-end lifecycle test of `lht sync` against a **real** Salesforce org
and a **real** Snowflake database/warehouse. Unlike the rest of `lht`'s test
suite, these tests need real credentials, make real network calls, and
create/update/delete real Salesforce records (in a scratch object, not
production data you care about).

Because of that, they're excluded from a plain `pytest` run. The `integration`
marker (registered in `conftest.py`) is deselected by default; you have to ask
for them explicitly.

## One-time setup

1. **Editable install**, so tests run against this working tree instead of a
   published PyPI release:

   ```bash
   cd /Users/danielkauppi/project/lht
   venv/bin/pip install -e ".[dev]"
   ```

2. **A Salesforce connection and a Snowflake connection**, already saved via
   the `lht` CLI itself:

   ```bash
   venv/bin/lht create-connection --salesforce
   venv/bin/lht create-connection --snowflake
   venv/bin/lht list-connections   # confirm names
   ```

   If your account has multiple saved connections for either type (this one
   does -- ~20, across several unrelated projects), **don't rely on the
   primary connection**. `config.toml` in this directory pins both by name
   explicitly for exactly that reason.

3. **`config.toml`** in this directory -- edit `[salesforce] org`,
   `[snowflake] database`/`connection` to match your setup.

4. **`<Sobject>.toml`** (e.g. `Account.toml`) -- generate it by querying the
   org for valid Record Type Ids and realistic sample field values:

   ```bash
   venv/bin/python discover_fields.py
   ```

   Review the generated file before running the suite -- it's a starting
   point, not guaranteed correct for every custom field/validation rule your
   org enforces.

## Running

```bash
venv/bin/pytest -m integration -v
```

Useful flags:

```bash
venv/bin/pytest -m integration -v --num-records 5       # fewer test records (default: 10)
venv/bin/pytest -m integration -v --keep-test-records    # skip hard-delete + final sync, for manual inspection
```

Each of the ten `test_NN_...` functions in `test_sync_scenario.py` covers one
step of the scenario (baseline refresh, create, sync+verify, update,
sync+verify, soft-delete, sync+verify, verify-in-Salesforce, hard-delete,
final sync+verify). They run in file order and share state (created record
ids, the pre-test baseline) via the `scenario_state` fixture. A failure in one
step doesn't stop the rest from running -- same as any other pytest file --
except that steps 3 onward will `SKIP` (not silently pass) if step 2 didn't
actually create any records.

A run writes:
- `reports/lht_test_report_<run_id>.md` and `.json` -- full step-by-step
  results, including checks that pytest's pass/fail alone doesn't show (e.g.
  per-record field mismatches).
- `reports/run_<run_id>.log` -- full debug log.

Both `reports/` and `state/` are gitignored.

## Cleaning up after a failed or `--keep-test-records` run

```bash
venv/bin/python cleanup_test_records.py <run_id>
```

`<run_id>` is the timestamp pytest prints at the start of the run (also the
suffix on the report/state filenames).
