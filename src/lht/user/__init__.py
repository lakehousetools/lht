"""
User authentication module for Snowflake.

This module provides interactive authentication for Snowflake connections
using private key authentication.
"""

from lht.user.auth import (
    authenticate,
    create_session,
)

# Connection management is in a separate optional module
try:
    from lht.user.connections import (
        initialize_solomo_directory,
        save_connection_config,
        load_connection,
        list_connections,
        delete_connection,
        update_connection,
        get_primary_connection,
        set_primary_connection,
        get_solomo_dir,
        get_connections_file
    )
    CONNECTIONS_AVAILABLE = True
except ImportError:
    CONNECTIONS_AVAILABLE = False

__all__ = [
    'authenticate',
    'create_session',
]

# Add connection management exports if available
if CONNECTIONS_AVAILABLE:
    __all__.extend([
        'initialize_solomo_directory',
        'save_connection_config',
        'load_connection',
        'list_connections',
        'delete_connection',
        'update_connection',
        'get_primary_connection',
        'set_primary_connection',
        'get_solomo_dir',
        'get_connections_file'
    ])

