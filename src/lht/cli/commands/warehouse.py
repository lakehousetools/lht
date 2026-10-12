"""
Resolving what a CLI command connects to.

Snowflake comes from a named connection in connections.toml. Databricks comes
from a `~/.databrickscfg` profile through Databricks Connect, which is the same
file and the same profiles the Databricks CLI uses -- there is no lht-side
credential for it, and nothing to copy into a notebook later.
"""

from typing import Any, Optional, Tuple

from lht.user.connections import get_primary_connection, load_connection


class WarehouseError(Exception):
    """A warehouse could not be opened; the message is for the user."""


def open_warehouse(
    snowflake_connection: Optional[str] = None,
    databricks_profile: Optional[str] = None,
    use_databricks: bool = False,
) -> Tuple[Any, str]:
    """
    Open the warehouse a command should read from.

    Args:
        snowflake_connection: Snowflake connection name; the primary one if None.
        databricks_profile: ``~/.databrickscfg`` profile. An empty string means
            "let Databricks Connect resolve it" (DATABRICKS_* environment
            variables, then the DEFAULT profile).
        use_databricks: Pick Databricks rather than Snowflake.

    Returns:
        (session_or_warehouse, label) -- the label describes what was opened,
        for the command to print.

    Raises:
        WarehouseError: With a message explaining what is missing.
    """
    if use_databricks:
        from lht.warehouse.databricks import connect

        try:
            warehouse = connect(profile=databricks_profile or None)
        except (ImportError, RuntimeError) as e:
            raise WarehouseError(str(e)) from e
        label = f"Databricks (profile: {databricks_profile})" if databricks_profile else "Databricks"
        return warehouse, label

    if snowflake_connection is None:
        snowflake_connection = get_primary_connection("snowflake")
    if not snowflake_connection:
        raise WarehouseError(
            "No Snowflake connection found. Use --snowflake, set a primary connection, "
            "or use --databricks."
        )
    if load_connection(snowflake_connection) is None:
        raise WarehouseError(f"Snowflake connection '{snowflake_connection}' not found")

    from lht.user.auth import create_session

    return create_session(connection_name=snowflake_connection), f"Snowflake ({snowflake_connection})"


def resolve_salesforce_connection(name: Optional[str] = None) -> str:
    """
    The Salesforce connection a command should use; the primary one if unnamed.

    A missing connections.toml is reported as "create a connection" rather than
    as a FileNotFoundError, which is the state a Databricks user is most likely
    to be in: they need a Salesforce connection but no warehouse one.

    Raises:
        WarehouseError: With a message explaining what is missing.
    """
    if name:
        return name
    try:
        name = get_primary_connection("salesforce")
    except FileNotFoundError:
        name = None
    if not name:
        raise WarehouseError(
            "No Salesforce connection found. Create one with "
            "`lht create-connection --salesforce`, or name an existing one with --salesforce."
        )
    return name
