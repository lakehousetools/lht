"""
Connection management module for Snowflake.

This module provides functionality to save, load, and manage Snowflake
connection configurations stored in TOML format.
"""

import shutil
from pathlib import Path
from typing import Dict, Optional, Any, List
import os

# Import TOML library
try:
    import tomllib  # Python 3.11+
    TOML_AVAILABLE = True
    TOML_READ_MODE = 'rb'
except ImportError:
    try:
        import tomli  # Python 3.10 and below
        tomllib = tomli
        TOML_AVAILABLE = True
        TOML_READ_MODE = 'rb'
    except ImportError:
        try:
            import toml
            tomllib = toml
            TOML_AVAILABLE = True
            TOML_READ_MODE = 'r'
        except ImportError:
            TOML_AVAILABLE = False


def get_solomo_dir() -> Path:
    """
    Get the path to the .solomo directory in the user's home directory.
    
    Returns:
        Path object pointing to ~/.solomo
    """
    home_dir = Path.home()
    solomo_dir = home_dir / '.solomo'
    return solomo_dir


def get_connections_file() -> Path:
    """
    Get the path to the connections.toml file.
    
    Returns:
        Path object pointing to ~/.solomo/connections.toml
    """
    return get_solomo_dir() / 'connections.toml'


def initialize_solomo_directory() -> Path:
    """
    Create the .solomo directory and connections.toml file if they don't exist.
    
    Returns:
        Path to the .solomo directory
        
    Raises:
        OSError: If directory creation fails
    """
    solomo_dir = get_solomo_dir()
    connections_file = get_connections_file()
    
    # Create .solomo directory if it doesn't exist
    solomo_dir.mkdir(mode=0o700, exist_ok=True)
    
    # Create connections.toml with template if it doesn't exist
    if not connections_file.exists():
        template = """[foley_dev1]

connection_type = 'snowflake'
private_key_file = ''
private_key_passphrase = ''
account = ''
user = ''
authenticator = ''
warehouse = ''
database = ''
schema = ''
role = ''
"""
        with open(connections_file, 'w') as f:
            f.write(template)
        print(f"✓ Created {connections_file}")
    
    return solomo_dir


def _load_connections_file() -> Dict[str, Any]:
    """
    Load all connections from the connections.toml file.
    
    Returns:
        Dictionary of all connections
        
    Raises:
        ValueError: If TOML library is not available
        FileNotFoundError: If connections.toml doesn't exist
    """
    if not TOML_AVAILABLE:
        raise ValueError(
            "TOML library is required. Install one of: tomli, toml, or use Python 3.11+"
        )
    
    connections_file = get_connections_file()
    
    if not connections_file.exists():
        raise FileNotFoundError(f"Connections file not found: {connections_file}")
    
    # Load connections
    if TOML_READ_MODE == 'rb':
        with open(connections_file, TOML_READ_MODE) as f:
            connections = tomllib.load(f)
    else:
        with open(connections_file, TOML_READ_MODE) as f:
            connections = tomllib.load(f)
    
    return connections


def _save_connections_file(connections: Dict[str, Any]) -> None:
    """
    Save connections dictionary to the connections.toml file.
    
    Args:
        connections: Dictionary of all connections to save
        
    Raises:
        ValueError: If TOML library is not available
        OSError: If file operations fail
    """
    if not TOML_AVAILABLE:
        raise ValueError(
            "TOML library is required. Install one of: tomli, toml, or use Python 3.11+"
        )
    
    connections_file = get_connections_file()
    
    # Write back to TOML file
    # Use toml library's dump function if available, otherwise manually format
    if hasattr(tomllib, 'dump'):
        with open(connections_file, 'w') as f:
            tomllib.dump(connections, f)
    else:
        # Manual TOML writing (simple format)
        with open(connections_file, 'w') as f:
            for conn_name, conn_data in connections.items():
                f.write(f"[{conn_name}]\n\n")
                for key, value in conn_data.items():
                    if value == '':
                        f.write(f"{key} = ''\n")
                    elif isinstance(value, str):
                        # Escape quotes in strings
                        escaped_value = value.replace("'", "\\'")
                        f.write(f"{key} = '{escaped_value}'\n")
                    elif isinstance(value, bool):
                        # TOML requires lowercase true/false
                        f.write(f"{key} = {str(value).lower()}\n")
                    elif value is None:
                        f.write(f"{key} = ''\n")
                    else:
                        f.write(f"{key} = {value}\n")
                f.write("\n")


def save_connection_config(connection_name: str, credentials: Dict[str, Any], connection_type: str = 'snowflake', copy_key: bool = True) -> None:
    """
    Save connection credentials to connections.toml file.
    
    Args:
        connection_name: Name of the connection (e.g., 'foley_dev1')
        credentials: Dictionary containing connection credentials
        connection_type: Type of connection ('snowflake' or 'salesforce'), default 'snowflake'
        copy_key: If True, copy the private key file to .solomo directory (Snowflake only)
        
    Raises:
        ValueError: If TOML library is not available
        OSError: If file operations fail
    """
    if not TOML_AVAILABLE:
        raise ValueError(
            "TOML library is required. Install one of: tomli, toml, or use Python 3.11+"
        )
    
    # Trim whitespace from connection name
    connection_name = connection_name.strip()
    connection_type = connection_type.strip().lower()
    
    # Initialize .solomo directory
    initialize_solomo_directory()
    
    connections_file = get_connections_file()
    solomo_dir = get_solomo_dir()
    
    # Load existing connections
    connections = {}
    if connections_file.exists():
        connections = _load_connections_file()
    
    # Create base connection entry with connection type
    connection_entry = {
        'connection_type': connection_type,
    }
    
    if connection_type == 'snowflake':
        # Handle private key file - copy to .solomo if requested
        private_key_file = credentials.get('private_key_file', '')
        if copy_key and private_key_file and os.path.isfile(private_key_file):
            # Get the filename from the original path
            key_filename = os.path.basename(private_key_file)
            dest_key_path = solomo_dir / key_filename
            
            # Convert both to absolute paths for comparison
            src_path = os.path.abspath(private_key_file)
            dst_path = os.path.abspath(dest_key_path)
            
            # Only copy if source and destination are different files
            if src_path != dst_path:
                # Copy the key file
                shutil.copy2(private_key_file, dest_key_path)
                # Set restrictive permissions (read-only for owner)
                os.chmod(dest_key_path, 0o600)
                print(f"✓ Copied private key to {dest_key_path}")
            else:
                # File is already in the .solomo directory, just ensure permissions are correct
                os.chmod(dest_key_path, 0o600)
                print(f"✓ Private key already in .solomo directory")
            
            # Update the path to point to the copied file (or existing file)
            private_key_file = str(dest_key_path)
        
        # Add Snowflake-specific fields
        connection_entry.update({
            'private_key_file': str(private_key_file).strip(),
            'private_key_passphrase': str(credentials.get('private_key_passphrase', '')).strip(),
            'account': str(credentials.get('account', '')).strip(),
            'user': str(credentials.get('user', '')).strip(),
            'authenticator': 'SNOWFLAKE_JWT',
            'warehouse': str(credentials.get('warehouse', '')).strip(),
            'database': str(credentials.get('database', '')).strip(),
            'schema': str(credentials.get('schema', '')).strip(),
            'role': str(credentials.get('role', '')).strip(),
        })
    elif connection_type == 'salesforce':
        # Add Salesforce-specific fields
        connection_entry.update({
            'client_id': str(credentials.get('client_id', '')).strip(),
            'client_key': str(credentials.get('client_key', '')).strip(),
            'sandbox': credentials.get('sandbox', False),
            'my_domain': str(credentials.get('my_domain', '')).strip(),
            'redirect_url': str(credentials.get('redirect_url', 'https://localhost:1717//OauthRedirect')).strip(),
        })
    else:
        raise ValueError(f"Unknown connection type: {connection_type}. Must be 'snowflake' or 'salesforce'")
    
    connections[connection_name] = connection_entry
    
    # Save connections back to file
    _save_connections_file(connections)
    
    print(f"✓ Saved connection '{connection_name}' ({connection_type}) to {connections_file}")


def load_connection(connection_name: str) -> Optional[Dict[str, Any]]:
    """
    Load connection credentials from connections.toml file.
    
    Args:
        connection_name: Name of the connection to load (whitespace will be trimmed)
        
    Returns:
        Dictionary containing connection credentials with 'connection_type' field, or None if not found
        
    Raises:
        ValueError: If TOML library is not available
        FileNotFoundError: If connections.toml doesn't exist
    """
    # Trim whitespace from connection name
    connection_name = connection_name.strip()
    
    connections = _load_connections_file()
    
    if connection_name not in connections:
        return None
    
    conn_data = connections[connection_name]
    
    # Get connection type (default to 'snowflake' for backward compatibility)
    connection_type = str(conn_data.get('connection_type', 'snowflake')).strip().lower()
    
    # Start with connection type
    credentials = {
        'connection_type': connection_type,
    }
    
    if connection_type == 'snowflake':
        # Convert to expected format and trim all string values
        credentials.update({
            'account': str(conn_data.get('account', '')).strip(),
            'user': str(conn_data.get('user', '')).strip(),
            'role': str(conn_data.get('role', '')).strip(),
            'warehouse': str(conn_data.get('warehouse', '')).strip(),
            'private_key_file': str(conn_data.get('private_key_file', '')).strip(),
            'private_key_passphrase': str(conn_data.get('private_key_passphrase', '')).strip() or None,
        })
        
        database = str(conn_data.get('database', '')).strip()
        if database:
            credentials['database'] = database
        
        schema = str(conn_data.get('schema', '')).strip()
        if schema:
            credentials['schema'] = schema
    elif connection_type == 'salesforce':
        # Load Salesforce-specific fields
        credentials.update({
            'client_id': str(conn_data.get('client_id', '')).strip(),
            'client_key': str(conn_data.get('client_key', '')).strip(),
            'sandbox': conn_data.get('sandbox', False),
            'my_domain': str(conn_data.get('my_domain', '')).strip(),
            'redirect_url': str(conn_data.get('redirect_url', 'https://localhost:1717//OauthRedirect')).strip(),
        })
    
    return credentials


def list_connections() -> List[str]:
    """
    List all saved connection names.
    
    Returns:
        List of connection names (excludes metadata entries like '_primary')
        
    Raises:
        ValueError: If TOML library is not available
        FileNotFoundError: If connections.toml doesn't exist
    """
    connections = _load_connections_file()
    # Filter out metadata entries that start with underscore
    return [name for name in connections.keys() if not name.startswith('_')]


def delete_connection(connection_name: str) -> bool:
    """
    Delete a connection from connections.toml.
    
    Args:
        connection_name: Name of the connection to delete
        
    Returns:
        True if connection was deleted, False if not found
        
    Raises:
        ValueError: If TOML library is not available
        FileNotFoundError: If connections.toml doesn't exist
    """
    connections = _load_connections_file()
    
    if connection_name not in connections:
        return False
    
    del connections[connection_name]
    _save_connections_file(connections)
    
    print(f"✓ Deleted connection '{connection_name}'")
    return True


def update_connection(connection_name: str, credentials: Dict[str, Any], connection_type: Optional[str] = None, copy_key: bool = True) -> bool:
    """
    Update an existing connection's credentials.
    
    Args:
        connection_name: Name of the connection to update
        credentials: Dictionary containing updated connection credentials
        connection_type: Type of connection ('snowflake' or 'salesforce'). If None, will try to detect from existing connection.
        copy_key: If True, copy the private key file to .solomo directory (Snowflake only)
        
    Returns:
        True if connection was updated, False if not found
        
    Raises:
        ValueError: If TOML library is not available
        FileNotFoundError: If connections.toml doesn't exist
        OSError: If file operations fail
    """
    connections = _load_connections_file()
    
    if connection_name not in connections:
        return False
    
    # Determine connection type
    if connection_type is None:
        # Try to get from existing connection or credentials
        existing_type = connections[connection_name].get('connection_type', 'snowflake')
        connection_type = credentials.get('connection_type', existing_type)
    
    connection_type = str(connection_type).strip().lower()
    
    solomo_dir = get_solomo_dir()
    
    # Create base connection entry with connection type
    connection_entry = {
        'connection_type': connection_type,
    }
    
    if connection_type == 'snowflake':
        # Handle private key file - copy to .solomo if requested
        private_key_file = credentials.get('private_key_file', '')
        if copy_key and private_key_file and os.path.isfile(private_key_file):
            # Get the filename from the original path
            key_filename = os.path.basename(private_key_file)
            dest_key_path = solomo_dir / key_filename
            
            # Convert both to absolute paths for comparison
            src_path = os.path.abspath(private_key_file)
            dst_path = os.path.abspath(dest_key_path)
            
            # Only copy if source and destination are different files
            if src_path != dst_path:
                # Copy the key file
                shutil.copy2(private_key_file, dest_key_path)
                # Set restrictive permissions (read-only for owner)
                os.chmod(dest_key_path, 0o600)
                print(f"✓ Copied private key to {dest_key_path}")
            else:
                # File is already in the .solomo directory, just ensure permissions are correct
                os.chmod(dest_key_path, 0o600)
                print(f"✓ Private key already in .solomo directory")
            
            # Update the path to point to the copied file (or existing file)
            private_key_file = str(dest_key_path)
        
        # Update connection entry with Snowflake fields
        connection_entry.update({
            'private_key_file': str(private_key_file).strip(),
            'private_key_passphrase': str(credentials.get('private_key_passphrase', '')).strip(),
            'account': str(credentials.get('account', '')).strip(),
            'user': str(credentials.get('user', '')).strip(),
            'authenticator': 'SNOWFLAKE_JWT',
            'warehouse': str(credentials.get('warehouse', '')).strip(),
            'database': str(credentials.get('database', '')).strip(),
            'schema': str(credentials.get('schema', '')).strip(),
            'role': str(credentials.get('role', '')).strip(),
        })
    elif connection_type == 'salesforce':
        # Update connection entry with Salesforce fields
        connection_entry.update({
            'client_id': str(credentials.get('client_id', '')).strip(),
            'client_key': str(credentials.get('client_key', '')).strip(),
            'sandbox': credentials.get('sandbox', False),
            'my_domain': str(credentials.get('my_domain', '')).strip(),
            'redirect_url': str(credentials.get('redirect_url', 'https://localhost:1717//OauthRedirect')).strip(),
        })
    
    connections[connection_name] = connection_entry
    
    # Save connections back to file
    _save_connections_file(connections)
    
    print(f"✓ Updated connection '{connection_name}' ({connection_type})")
    return True


def get_primary_connection(connection_type: Optional[str] = None) -> Optional[str]:
    """
    Get the name of the primary/default connection.
    
    Args:
        connection_type: Optional connection type ('snowflake' or 'salesforce').
                        If None, returns the legacy primary connection for backward compatibility.
    
    Returns:
        Name of primary connection, or None if not set
        
    Raises:
        ValueError: If TOML library is not available
        FileNotFoundError: If connections.toml doesn't exist
    """
    connections = _load_connections_file()
    
    # Check for primary connection marker
    if '_primary' not in connections:
        return None
    
    primary_data = connections['_primary']
    
    if connection_type:
        connection_type = connection_type.strip().lower()
        if connection_type == 'snowflake':
            primary_name = primary_data.get('snowflake_primary', None)
        elif connection_type == 'salesforce':
            primary_name = primary_data.get('salesforce_primary', None)
        else:
            raise ValueError(f"Invalid connection_type: {connection_type}. Must be 'snowflake' or 'salesforce'")
        
        # If type-specific primary not found, fall back to legacy 'name' and verify type
        if not primary_name:
            legacy_name = primary_data.get('name', None)
            if legacy_name:
                legacy_name = str(legacy_name).strip()
                # Verify the connection exists and matches the requested type
                if legacy_name in connections:
                    conn_data = connections[legacy_name]
                    conn_type = str(conn_data.get('connection_type', 'snowflake')).strip().lower()
                    if conn_type == connection_type:
                        primary_name = legacy_name
        
        if primary_name:
            return str(primary_name).strip()
    else:
        # Backward compatibility: check for legacy 'name' field
        primary_name = primary_data.get('name', None)
        if primary_name:
            return str(primary_name).strip()
    
    return None


def set_primary_connection(connection_name: str, connection_type: Optional[str] = None) -> bool:
    """
    Set a connection as the primary/default connection for its type.
    
    Args:
        connection_name: Name of the connection to set as primary
        connection_type: Optional connection type ('snowflake' or 'salesforce').
                        If None, will be auto-detected from the connection.
        
    Returns:
        True if primary connection was set, False if connection doesn't exist
        
    Raises:
        ValueError: If TOML library is not available or connection type is invalid
        FileNotFoundError: If connections.toml doesn't exist
    """
    connections = _load_connections_file()
    
    if connection_name not in connections:
        return False
    
    # Determine connection type if not provided
    if connection_type is None:
        conn_data = connections[connection_name]
        connection_type = str(conn_data.get('connection_type', 'snowflake')).strip().lower()
    
    connection_type = connection_type.strip().lower()
    
    if connection_type not in ['snowflake', 'salesforce']:
        raise ValueError(f"Invalid connection_type: {connection_type}. Must be 'snowflake' or 'salesforce'")
    
    # Store primary connection marker
    if '_primary' not in connections:
        connections['_primary'] = {}
    
    # Set type-specific primary
    if connection_type == 'snowflake':
        connections['_primary']['snowflake_primary'] = connection_name.strip()
    elif connection_type == 'salesforce':
        connections['_primary']['salesforce_primary'] = connection_name.strip()
    
    # Keep legacy 'name' for backward compatibility (set to the primary connection)
    # This maintains backward compatibility with code that doesn't specify type
    connections['_primary']['name'] = connection_name.strip()
    
    # Save connections back to file
    _save_connections_file(connections)
    
    print(f"✓ Set '{connection_name}' as primary {connection_type} connection")
    return True

