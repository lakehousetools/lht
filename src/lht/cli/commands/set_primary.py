"""
Set primary connection command implementation.
"""

import sys
from lht.user.connections import (
    load_connection,
    set_primary_connection,
    get_primary_connection,
    list_connections
)


def set_primary(connection_name: str) -> int:
    """
    Set a connection as the primary connection for its type.
    
    Args:
        connection_name: Name of the connection to set as primary
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Verify connection exists
        all_connections = list_connections()
        if connection_name not in all_connections:
            print(f"Error: Connection '{connection_name}' not found.")
            print(f"Available connections: {', '.join(all_connections)}")
            return 1
        
        # Load connection to determine type
        conn_details = load_connection(connection_name)
        if not conn_details:
            print(f"Error: Could not load connection '{connection_name}'")
            return 1
        
        connection_type = conn_details.get('connection_type', 'snowflake').lower()
        
        # Check if already primary
        current_primary = get_primary_connection(connection_type)
        if current_primary == connection_name:
            print(f"✓ Connection '{connection_name}' is already set as the primary {connection_type} connection.")
            return 0
        
        # Set as primary
        success = set_primary_connection(connection_name, connection_type=connection_type)
        
        if success:
            print(f"✓ Set '{connection_name}' as the primary {connection_type} connection.")
            return 0
        else:
            print(f"✗ Failed to set '{connection_name}' as primary connection.")
            return 1
            
    except ImportError:
        print("Error: Connections module not available.")
        print("Install a TOML library (tomli, toml) or use Python 3.11+ to enable connection management.")
        return 1
    except FileNotFoundError:
        print("No connections file found. Create a connection first using:")
        print("  lht create-connection --snowflake")
        print("  lht create-connection --salesforce")
        return 1
    except Exception as e:
        print(f"Error setting primary connection: {e}")
        import traceback
        traceback.print_exc()
        return 1

