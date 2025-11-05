"""
Connection management module for Snowflake.

This module provides functionality to save, load, and manage Snowflake
connection configurations stored in TOML format.
"""

from lht.user.connections.manager import (
    get_solomo_dir,
    get_connections_file,
    initialize_solomo_directory,
    save_connection_config,
    load_connection,
    list_connections,
    delete_connection,
    update_connection,
    get_primary_connection,
    set_primary_connection
)

__all__ = [
    'get_solomo_dir',
    'get_connections_file',
    'initialize_solomo_directory',
    'save_connection_config',
    'load_connection',
    'list_connections',
    'delete_connection',
    'update_connection',
    'get_primary_connection',
    'set_primary_connection'
]

