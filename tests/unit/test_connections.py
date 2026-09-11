"""
Unit tests for lht.user.connections.manager's connections.toml round-trip.

Every test here monkeypatches get_solomo_dir() to a pytest tmp_path, so
nothing ever touches the real ~/.solomo/connections.toml on the machine
running the tests - that file can hold real, live credentials.
"""
import pytest

from lht.user.connections import manager as conn_manager


@pytest.fixture
def isolated_solomo_dir(tmp_path, monkeypatch):
    """Point every connections.toml read/write at a throwaway directory."""
    monkeypatch.setattr(conn_manager, "get_solomo_dir", lambda: tmp_path)
    return tmp_path


def test_fixture_actually_isolates_the_connections_file(isolated_solomo_dir):
    # Guards the guard: if this ever resolves to the real home directory,
    # every other test in this file would be writing real credentials.
    assert conn_manager.get_connections_file().parent == isolated_solomo_dir


def test_save_and_load_snowflake_connection_round_trips(isolated_solomo_dir):
    creds = {
        "account": "myaccount",
        "user": "myuser",
        "role": "MYROLE",
        "warehouse": "MYWH",
        "private_key_file": "",
        "database": "MYDB",
        "schema": "MYSCHEMA",
    }
    conn_manager.save_connection_config("test_sf_conn", creds, connection_type="snowflake", copy_key=False)

    loaded = conn_manager.load_connection("test_sf_conn")
    assert loaded["connection_type"] == "snowflake"
    assert loaded["account"] == "myaccount"
    assert loaded["user"] == "myuser"
    assert loaded["warehouse"] == "MYWH"
    assert loaded["database"] == "MYDB"


def test_save_and_load_salesforce_connection_round_trips(isolated_solomo_dir):
    creds = {
        "client_id": "3MVG9...",
        "client_key": "supersecret",
        "sandbox": False,
        "my_domain": "mycompany",
    }
    conn_manager.save_connection_config("test_sfdc_conn", creds, connection_type="salesforce")

    loaded = conn_manager.load_connection("test_sfdc_conn")
    assert loaded["connection_type"] == "salesforce"
    assert loaded["client_id"] == "3MVG9..."
    assert loaded["my_domain"] == "mycompany"
    assert loaded["sandbox"] is False


def test_load_connection_trims_whitespace_from_name(isolated_solomo_dir):
    conn_manager.save_connection_config(
        "spacey", {"account": "a", "user": "u", "role": "r", "warehouse": "w"}, connection_type="snowflake"
    )
    assert conn_manager.load_connection("  spacey  ") is not None


def test_load_unknown_connection_returns_none(isolated_solomo_dir):
    conn_manager.save_connection_config(
        "exists", {"account": "a", "user": "u", "role": "r", "warehouse": "w"}, connection_type="snowflake"
    )
    assert conn_manager.load_connection("does_not_exist") is None


def test_list_connections_excludes_the_primary_marker(isolated_solomo_dir):
    conn_manager.save_connection_config(
        "conn_a", {"account": "a", "user": "u", "role": "r", "warehouse": "w"}, connection_type="snowflake"
    )
    conn_manager.set_primary_connection("conn_a", connection_type="snowflake")

    names = conn_manager.list_connections()
    assert "conn_a" in names
    assert "_primary" not in names


def test_delete_connection_removes_it_and_reports_missing(isolated_solomo_dir):
    conn_manager.save_connection_config(
        "to_delete", {"account": "a", "user": "u", "role": "r", "warehouse": "w"}, connection_type="snowflake"
    )
    assert conn_manager.delete_connection("to_delete") is True
    assert conn_manager.load_connection("to_delete") is None
    assert conn_manager.delete_connection("to_delete") is False


def test_primary_connection_is_tracked_independently_per_type(isolated_solomo_dir):
    conn_manager.save_connection_config(
        "sf_conn", {"account": "a", "user": "u", "role": "r", "warehouse": "w"}, connection_type="snowflake"
    )
    conn_manager.save_connection_config(
        "sfdc_conn", {"client_id": "x", "client_key": "y", "my_domain": "d"}, connection_type="salesforce"
    )

    conn_manager.set_primary_connection("sf_conn", connection_type="snowflake")
    conn_manager.set_primary_connection("sfdc_conn", connection_type="salesforce")

    assert conn_manager.get_primary_connection("snowflake") == "sf_conn"
    assert conn_manager.get_primary_connection("salesforce") == "sfdc_conn"
