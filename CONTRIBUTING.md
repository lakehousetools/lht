# Contributing to lht

Thanks for helping. Bug reports, docs fixes, new warehouse backends and small, focused pull requests are all welcome. Questions belong in [Discussions](https://github.com/lakehousetools/lht/discussions/categories/q-a) rather than Issues.

## Development setup

```bash
git clone https://github.com/lakehousetools/lht.git
cd lht
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"      # includes the Snowflake extra
pytest
```

The unit tests need no network access and no credentials. They must never read or write your real `connections.toml` (`~/.lakehousetools/` or `~/.solomo/`); use the `isolated_solomo_dir` fixture pattern in `tests/unit/test_connections.py` — or, if the test is specifically about directory resolution itself, patch `Path.home()` and clear `LHT_HOME` instead, since that fixture patches `get_solomo_dir()` directly.

### Integration tests

`tests/integration/` runs a full sync lifecycle against a real Salesforce org and Snowflake account. It creates and deletes records, so **use a sandbox**.

```bash
cp tests/integration/config.example.toml tests/integration/config.toml   # gitignored
# edit config.toml with your own connection names
pytest -m integration
```

See [tests/integration/README.md](tests/integration/README.md).

### Spark dialect tests

`tests/spark/` runs the SQL lht generates for Databricks against a real local Spark
engine. No workspace and no credentials — just `pyspark` and a JVM:

```bash
pip install "pyspark==4.0.1"
pytest -m spark
```

Run these after touching `lht/warehouse/databricks.py`. They are not redundant with
the unit tests, which assert what lht *writes*: these assert what Spark *does with
it*, and that is where the two once diverged. Spark concatenates adjacent string
literals, so the SQL standard's `''` escape silently turned `O'Brien` into `OBrien`
with no error anywhere — only an engine catches that.

## Pull requests

1. Open an issue first for anything larger than a bug fix, so we can agree on the approach.
2. Keep each PR to one change. Add or update tests for behaviour you change.
3. Run `pytest` before pushing. CI runs it on Python 3.9–3.12.
4. Update `CHANGELOG.md` under **Unreleased**.
5. **Never commit real org names, connection names, account identifiers, credentials or customer data**: not in code, tests, docs or commit messages. Use placeholders such as `acme`, `my_snowflake` and `example--dev.sandbox`.

## Code style

- Match the style of the surrounding code.
- Every HTTP call to Salesforce takes `timeout=DEFAULT_TIMEOUT` (`lht.util.http`).
- Any catalog, database, schema or table name formatted into SQL goes through `lht.util.sql.identifier()`. Any **value** goes through the warehouse's own `warehouse.literal()`, never the module-level `lht.util.sql.literal()` — the backends escape quotes differently, and getting it wrong corrupts data instead of failing.
- Don't import Snowpark or PySpark at module scope anywhere the reverse-ETL path can reach; both are optional extras. `tests/unit/test_databricks.py` guards this.
- New warehouse-facing code takes a `session` and calls `lht.warehouse.from_session()` on it, rather than calling `session.sql()` directly or branching on the backend.
- Never log or print access tokens, client secrets or key passphrases.

## Adding a warehouse

Snowflake and Databricks are supported for reverse ETL and merge, through `lht.warehouse`. Salesforce → warehouse **sync** is still Snowflake-only: it calls Snowpark directly. If you want to add another warehouse (BigQuery, Postgres, …), open an issue to discuss it first.

For reverse ETL a backend is small. Subclass `lht.warehouse.Warehouse`, give it a `TYPES` map for the log-table columns, a `timestamp_literal()`, and a `literal()` if its string escaping differs from the SQL standard's doubled quote (Spark's does, and getting this wrong corrupts data silently rather than failing). Then register it in `_BACKENDS` in `lht/warehouse/__init__.py` so `from_session()` recognises its sessions. Copy `tests/spark/` to run the generated SQL against a real engine: the unit tests only assert what lht writes, and the two worst Databricks bugs were invisible to them.

## Releasing (maintainers)

1. Update `CHANGELOG.md` and the `version` in `pyproject.toml`.
2. Run `./publish.sh`. It checks the version against PyPI, cleans and builds the sdist and wheel, runs `twine check`, and uploads to TestPyPI or PyPI. It reads the token from `LHT_PYPI_TOKEN_TEST` / `LHT_PYPI_TOKEN_PROD`, or prompts for it.
3. Check the install in a clean environment, **once per way people install it**: `pip install lht==<version>` with no extras and then `lht --help`, since that is what a Databricks cluster gets and the CLI once crashed there for want of Snowpark; and again with `"lht[snowflake]==<version>"`.
4. Tag the release (`git tag v<version> && git push --tags`) and create a GitHub Release with the changelog entry.

The manual equivalent of step 2:

```bash
rm -rf dist build src/*.egg-info
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```
