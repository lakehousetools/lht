"""
Fixtures for the live Salesforce/Snowflake integration suite. See README.md in
this directory before running anything here -- it needs real credentials and
mutates real data.
"""
import pytest

import lht_common as C


def pytest_addoption(parser):
    parser.addoption(
        "--num-records", action="store", default=10, type=int,
        help="number of test records to create for the sync scenario (default: 10)",
    )
    parser.addoption(
        "--keep-test-records", action="store_true", default=False,
        help="skip the hard-delete/final-sync steps, leaving test records soft-deleted for inspection",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: live test against a real Salesforce org and Snowflake warehouse; "
        "requires a configured connection and network access. Excluded by default -- "
        "run explicitly with `pytest -m integration`.",
    )


@pytest.fixture(scope="session")
def num_records(request) -> int:
    return request.config.getoption("--num-records")


@pytest.fixture(scope="session")
def keep_test_records(request) -> bool:
    return request.config.getoption("--keep-test-records")


@pytest.fixture(scope="session")
def run_id() -> str:
    return C.now_run_id()


@pytest.fixture(scope="session")
def logger(run_id):
    return C.setup_logging(run_id)


@pytest.fixture(scope="session")
def cfg() -> C.Config:
    return C.load_config("config.toml")


@pytest.fixture(scope="session")
def field_toml(cfg) -> dict:
    return C.load_field_toml(cfg.sobject)


@pytest.fixture(scope="session")
def access_info(cfg) -> dict:
    return C.get_access_info(cfg.sf_org)


@pytest.fixture(scope="session")
def snowflake_connection_name(cfg) -> str:
    return C.resolve_snowflake_connection(cfg.snowflake_connection)


@pytest.fixture(scope="session")
def schema(cfg, snowflake_connection_name) -> str:
    return C.get_snowflake_schema(snowflake_connection_name, cfg.schema_override)


@pytest.fixture(scope="session")
def snowflake_session(snowflake_connection_name):
    session = C.get_snowflake_session(snowflake_connection_name)
    yield session
    session.close()


@pytest.fixture(scope="session")
def report(run_id, cfg, logger):
    r = C.TestReport(run_id, cfg, logger)
    yield r
    path = r.render_markdown()
    logger.info(f"\nReport written to {path}")
    logger.info(f"Overall result: {'PASS' if r.all_passed else 'FAIL'}")


@pytest.fixture(scope="session")
def scenario_state(run_id) -> dict:
    """Mutable dict shared across the ordered scenario tests in test_sync_scenario.py."""
    state = {"config_path": "config.toml", "record_ids": [], "run_id": run_id}
    C.save_state(run_id, state)
    return state
