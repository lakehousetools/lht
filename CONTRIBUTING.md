# Contributing to lht

Thanks for helping. Bug reports, docs fixes, new warehouse backends and small, focused pull requests are all welcome. Questions belong in [Discussions](https://github.com/lakehousetools/lht/discussions/categories/q-a) rather than Issues.

## Development setup

```bash
git clone https://github.com/lakehousetools/lht.git
cd lht
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The unit tests need no network access and no credentials. They must never read or write your real `~/.solomo/connections.toml`; use the `isolated_solomo_dir` fixture pattern in `tests/unit/test_connections.py`.

### Integration tests

`tests/integration/` runs a full sync lifecycle against a real Salesforce org and Snowflake account. It creates and deletes records, so **use a sandbox**.

```bash
cp tests/integration/config.example.toml tests/integration/config.toml   # gitignored
# edit config.toml with your own connection names
pytest -m integration
```

See [tests/integration/README.md](tests/integration/README.md).

## Pull requests

1. Open an issue first for anything larger than a bug fix, so we can agree on the approach.
2. Keep each PR to one change. Add or update tests for behaviour you change.
3. Run `pytest` before pushing. CI runs it on Python 3.9–3.12.
4. Update `CHANGELOG.md` under **Unreleased**.
5. **Never commit real org names, connection names, account identifiers, credentials or customer data**: not in code, tests, docs or commit messages. Use placeholders such as `acme`, `my_snowflake` and `example--dev.sandbox`.

## Code style

- Match the style of the surrounding code.
- Every HTTP call to Salesforce takes `timeout=DEFAULT_TIMEOUT` (`lht.util.http`).
- Any database, schema or table name formatted into SQL goes through `lht.util.sql.identifier()`. Any value goes through `literal()`, or better, a bound parameter.
- Never log or print access tokens, client secrets or key passphrases.

## Adding a warehouse

lht's sync and reverse-ETL paths currently call Snowpark directly. If you want to add another warehouse (Databricks, BigQuery, Postgres, …), open an issue to discuss the interface first.

## Releasing (maintainers)

1. Update `CHANGELOG.md` and the `version` in `pyproject.toml`.
2. Run `./publish.sh`. It checks the version against PyPI, cleans and builds the sdist and wheel, runs `twine check`, and uploads to TestPyPI or PyPI. It reads the token from `LHT_PYPI_TOKEN_TEST` / `LHT_PYPI_TOKEN_PROD`, or prompts for it.
3. Check the install in a clean environment: `pip install lht==<version>` and `lht --help`.
4. Tag the release (`git tag v<version> && git push --tags`) and create a GitHub Release with the changelog entry.

The manual equivalent of step 2:

```bash
rm -rf dist build src/*.egg-info
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```
