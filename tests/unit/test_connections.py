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


def test_connections_file_is_readable_by_owner_only(isolated_solomo_dir):
    # It holds client secrets; the default umask would often leave it world-readable.
    connections_file = conn_manager.get_connections_file()
    connections_file.write_text("")
    connections_file.chmod(0o644)  # a file saved by an older lht
    conn_manager.save_connection_config(
        "secret_holder", {"client_id": "id", "client_key": "secret", "my_domain": "d"},
        connection_type="salesforce",
    )
    assert connections_file.stat().st_mode & 0o777 == 0o600


# ─── Directory resolution (get_solomo_dir / get_lht_home / LHT_HOME) ───────────
#
# These tests cannot use isolated_solomo_dir -- that fixture patches
# get_solomo_dir() directly, which is exactly the function under test here.
# Each one patches Path.home() instead and clears LHT_HOME, so they're still
# fully isolated from the real home directory and from each other.

@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setattr(conn_manager.Path, "home", lambda: tmp_path)
    monkeypatch.delenv("LHT_HOME", raising=False)
    return tmp_path


def test_lht_home_env_var_wins_outright(isolated_home, monkeypatch, tmp_path):
    # Set even though neither ~/.lakehousetools nor ~/.solomo exist, and even
    # though it doesn't itself exist -- an explicit override is trusted as-is.
    override = tmp_path / "wherever"
    monkeypatch.setenv("LHT_HOME", str(override))
    assert conn_manager.get_solomo_dir() == override


def test_lht_home_env_var_expands_user(isolated_home, monkeypatch):
    # Path.expanduser() reads the HOME env var directly (not Path.home(),
    # which isolated_home's monkeypatch doesn't reach) -- patch that too so
    # this stays isolated from the real home directory.
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("LHT_HOME", "~/custom-lht-dir")
    assert conn_manager.get_solomo_dir() == isolated_home / "custom-lht-dir"


def test_prefers_new_dir_when_it_exists(isolated_home):
    (isolated_home / ".lakehousetools").mkdir()
    (isolated_home / ".solomo").mkdir()  # both exist -- new one must win
    assert conn_manager.get_solomo_dir() == isolated_home / ".lakehousetools"


def test_falls_back_to_old_dir_when_only_it_exists(isolated_home):
    (isolated_home / ".solomo").mkdir()
    assert conn_manager.get_solomo_dir() == isolated_home / ".solomo"


def test_defaults_to_new_dir_when_neither_exists(isolated_home):
    assert conn_manager.get_solomo_dir() == isolated_home / ".lakehousetools"


def test_get_lht_home_is_the_same_resolution_as_get_solomo_dir(isolated_home):
    (isolated_home / ".solomo").mkdir()
    assert conn_manager.get_lht_home() == conn_manager.get_solomo_dir()


# ─── register_connection / unregister_connection ───────────────────────────────

@pytest.fixture(autouse=True)
def _clear_registered_connections():
    """register_connection() writes to module-level state -- never leak a
    registration from one test into the next."""
    conn_manager._registered_connections.clear()
    yield
    conn_manager._registered_connections.clear()


def test_registered_connection_works_with_no_file_on_disk(isolated_solomo_dir):
    # No connections.toml exists in isolated_solomo_dir at all -- would raise
    # FileNotFoundError via _load_connections_file() if this fell through to
    # the file, which is exactly what register_connection() must prevent.
    conn_manager.register_connection("from_secrets_manager", {
        "connection_type": "snowflake", "account": "acct", "user": "u",
        "role": "r", "warehouse": "w", "private_key_file": "",
    })
    loaded = conn_manager.load_connection("from_secrets_manager")
    assert loaded["account"] == "acct"


def test_registered_connection_defaults_connection_type_to_snowflake(isolated_solomo_dir):
    conn_manager.register_connection("no_type_given", {"account": "a", "user": "u"})
    loaded = conn_manager.load_connection("no_type_given")
    assert loaded["connection_type"] == "snowflake"


def test_registered_connection_takes_precedence_over_the_file(isolated_solomo_dir):
    conn_manager.save_connection_config(
        "dup", {"account": "from_file", "user": "u", "role": "r", "warehouse": "w"},
        connection_type="snowflake",
    )
    conn_manager.register_connection("dup", {
        "connection_type": "snowflake", "account": "from_registry", "user": "u",
        "role": "r", "warehouse": "w", "private_key_file": "",
    })
    assert conn_manager.load_connection("dup")["account"] == "from_registry"


def test_unregister_connection_falls_back_to_the_file(isolated_solomo_dir):
    conn_manager.save_connection_config(
        "dup2", {"account": "from_file", "user": "u", "role": "r", "warehouse": "w"},
        connection_type="snowflake",
    )
    conn_manager.register_connection("dup2", {"connection_type": "snowflake", "account": "from_registry"})
    conn_manager.unregister_connection("dup2")
    assert conn_manager.load_connection("dup2")["account"] == "from_file"


def test_unregister_connection_is_a_noop_if_not_registered():
    conn_manager.unregister_connection("never_registered")  # must not raise
