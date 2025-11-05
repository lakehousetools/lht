"""
Snowflake authentication module with interactive credential prompting.

This module provides functions to interactively prompt users for Snowflake
credentials and create authenticated Snowflake sessions using JWT authentication.
"""

import getpass
from typing import Dict, Optional, Any, Tuple
from snowflake.snowpark import Session
import os

# Import cryptography for private key handling
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    raise ImportError(
        "cryptography library is required for private key authentication. "
        "Install it with: pip install cryptography"
    )


def _load_private_key(private_key_file: str, passphrase: Optional[str] = None) -> bytes:
    """
    Load and convert private key to DER format bytes.
    
    Args:
        private_key_file: Path to PEM private key file
        passphrase: Optional passphrase for encrypted private key
        
    Returns:
        Private key as DER-encoded bytes
        
    Raises:
        FileNotFoundError: If private key file doesn't exist
        ValueError: If private key is invalid
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError("cryptography library is required")
    
    if not os.path.isfile(private_key_file):
        raise FileNotFoundError(f"Private key file not found: {private_key_file}")
    
    try:
        with open(private_key_file, "rb") as key:
            private_key = load_pem_private_key(
                key.read(),
                password=passphrase.encode() if passphrase else None,
                backend=default_backend()
            )
        
        # Convert to DER format bytes
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return private_key_bytes
    except Exception as e:
        raise ValueError(f"Failed to load private key: {str(e)}")


def _prompt_required(prompt: str, default: Optional[str] = None) -> str:
    """
    Prompt user for required input.
    
    Args:
        prompt: Prompt message to display
        default: Optional default value (if provided and user presses Enter, default is used)
        
    Returns:
        User input string or default value
    """
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    while True:
        value = input(full_prompt).strip()
        if value:
            return value
        elif default:
            return default
        print("This field is required. Please enter a value.")


def _prompt_optional(prompt: str, default: Optional[str] = None) -> Optional[str]:
    """
    Prompt user for optional input.
    
    Args:
        prompt: Prompt message to display
        default: Optional default value
        
    Returns:
        User input string or None if empty
    """
    if default:
        full_prompt = f"{prompt} [{default}] (optional): "
    else:
        full_prompt = f"{prompt} (optional): "
    
    value = input(full_prompt).strip()
    if value:
        return value
    elif default:
        return default
    return None


def _prompt_private_key_file() -> Tuple[str, Optional[str]]:
    """
    Prompt user for private key file path and optional passphrase.
    
    Returns:
        Tuple of (private_key_file_path, passphrase or None)
    """
    print("\nPrivate Key File:")
    print("  Enter the path to your PEM private key file")
    print()
    
    while True:
        key_file = _prompt_required("Private key file path")
        
        if not os.path.isfile(key_file):
            print(f"Error: File not found: {key_file}")
            print("Please try again.")
            continue
        
        # Check if file looks like a PEM key
        try:
            with open(key_file, 'r') as f:
                first_line = f.readline().strip()
                if not first_line.startswith('-----BEGIN'):
                    print("Warning: File does not appear to be a PEM format private key.")
                    response = input("Continue anyway? (y/n): ").strip().lower()
                    if response != 'y':
                        continue
        except Exception as e:
            print(f"Error reading file: {e}")
            continue
        
        # Ask for passphrase if needed
        passphrase = None
        print("\nPrivate Key Passphrase:")
        print("  If your private key is encrypted, enter the passphrase.")
        print("  If not encrypted, press Enter to skip.")
        print()
        passphrase_input = getpass.getpass("Private key passphrase (optional): ").strip()
        if passphrase_input:
            passphrase = passphrase_input
        
        return key_file, passphrase


def authenticate() -> Dict[str, Any]:
    """
    Interactively prompt user for Snowflake authentication credentials and save connection.
    
    Prompts for:
    - account (required)
    - username (required)
    - role (required)
    - warehouse (required)
    - private_key_file (required)
    - private_key_passphrase (optional)
    - database (optional)
    - schema (optional)
    - connection name (with default value)
    - whether to make connection primary
    
    Returns:
        Dictionary containing authentication credentials
        
    Example:
        >>> creds = authenticate()
        Account: myaccount
        Username: myuser
        Role: MYROLE
        Warehouse: MYWAREHOUSE
        Private key file path: /path/to/key.pem
        Private key passphrase (optional): 
        Database (optional): MYDB
        Schema (optional): MYSCHEMA
        Connection name [myaccount]: 
        Make this the primary connection? (y/n): y
        >>> print(creds)
        {'account': 'myaccount', 'user': 'myuser', ...}
    """
    print("=" * 60)
    print("Snowflake Authentication")
    print("=" * 60)
    print()
    
    account = _prompt_required("Account")
    username = _prompt_required("Username")
    role = _prompt_required("Role")
    warehouse = _prompt_required("Warehouse")
    private_key_file, private_key_passphrase = _prompt_private_key_file()
    database = _prompt_optional("Database")
    schema = _prompt_optional("Schema")
    
    credentials = {
        'account': account,
        'user': username,
        'role': role,
        'warehouse': warehouse,
        'private_key_file': private_key_file,
        'private_key_passphrase': private_key_passphrase,
    }
    
    if database:
        credentials['database'] = database
    if schema:
        credentials['schema'] = schema
    
    print()
    print("✓ Credentials collected successfully")
    print()
    
    # Always save connection (optional import from connections module)
    try:
        from lht.user.connections import save_connection_config, set_primary_connection
        
        # Prompt for connection name with default value (account_database format)
        account_clean = account.lower().replace('.', '_')
        database_clean = database.lower().replace('.', '_') if database else ''
        if database_clean:
            default_connection_name = f"{account_clean}_{database_clean}"
        else:
            default_connection_name = account_clean
        connection_name = _prompt_required("Connection name", default=default_connection_name).strip()
        
        # Save connection
        save_connection_config(connection_name, credentials, connection_type='snowflake', copy_key=True)
        print(f"\n✓ Connection '{connection_name}' saved. You can now use it with:")
        print(f"  create_session(connection_name='{connection_name}')")
        
        # Prompt to make primary
        print()
        make_primary = input("Make this the primary connection? (y/n): ").strip().lower() == 'y'
        if make_primary:
            try:
                set_primary_connection(connection_name, connection_type='snowflake')
            except Exception as e:
                print(f"Warning: Failed to set primary connection: {e}")
        
    except ImportError:
        print("Warning: Connections module not available. Connection was not saved.")
        print("Install a TOML library (tomli, toml) or use Python 3.11+ to enable connection saving.")
    except Exception as e:
        print(f"Warning: Failed to save connection: {e}")
    
    return credentials


def create_session(credentials: Optional[Dict[str, Any]] = None, connection_name: Optional[str] = None) -> Session:
    """
    Create a Snowflake session using provided or prompted credentials.
    
    Uses JWT authentication with private key (DER format) as shown in the
    reference implementation.
    
    Args:
        credentials: Optional dictionary of credentials. If not provided,
                    will prompt user interactively or load from connection_name.
                    Must include:
                    - account (required)
                    - user (required)
                    - role (required)
                    - warehouse (required)
                    - private_key_file (required) - path to PEM key file
                    - private_key_passphrase (optional) - passphrase for encrypted key
                    - database (optional)
                    - schema (optional)
        connection_name: Optional name of connection to load from connections.toml.
                        If provided and credentials is None, will load from file.
                    
    Returns:
        Authenticated Snowflake Snowpark session
        
    Raises:
        ConnectionError: If authentication fails
        FileNotFoundError: If private key file doesn't exist
        ValueError: If private key is invalid
        
    Example:
        >>> # Interactive mode
        >>> session = create_session()
        
        >>> # Load from saved connection
        >>> session = create_session(connection_name='foley_dev1')
        
        >>> # With provided credentials
        >>> session = create_session({
        ...     'account': 'myaccount',
        ...     'user': 'myuser',
        ...     'role': 'MYROLE',
        ...     'warehouse': 'MYWAREHOUSE',
        ...     'private_key_file': '/path/to/key.pem',
        ...     'private_key_passphrase': None,  # or passphrase string if encrypted
        ...     'database': 'MYDB',
        ...     'schema': 'MYSCHEMA'
        ... })
    """
    # If connection_name is provided, try to load from connections module
    if connection_name:
        try:
            from lht.user.connections import load_connection
            credentials = load_connection(connection_name)
            if credentials is None:
                raise ValueError(f"Connection '{connection_name}' not found in connections.toml")
            print(f"✓ Loaded connection '{connection_name}' from connections.toml")
        except ImportError:
            raise ValueError(
                "Connections module not available. Cannot load connection by name. "
                "Install a TOML library (tomli, toml) or use Python 3.11+ to enable connection management. "
                "Alternatively, pass credentials directly to create_session()."
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Connections file not found: {e}. "
                "Please create a connection first using save_connection_config() from lht.user.connections"
            )
        except Exception as e:
            raise ValueError(f"Failed to load connection '{connection_name}': {e}")
    elif credentials is None:
        # No connection_name and no credentials - prompt interactively
        credentials = authenticate()
    
    # Load and convert private key to DER format
    private_key_bytes = _load_private_key(
        credentials['private_key_file'],
        credentials.get('private_key_passphrase')
    )
    
    # Build connection parameters (matching the reference implementation)
    connection_parameters = {
        "account": credentials['account'],
        "user": credentials['user'],
        "private_key": private_key_bytes,
        "authenticator": 'SNOWFLAKE_JWT',
        "warehouse": credentials['warehouse'],
    }
    
    # Add role (required)
    if 'role' in credentials:
        connection_parameters["role"] = credentials['role']
    
    # Add optional parameters
    if 'database' in credentials:
        connection_parameters["database"] = credentials['database']
    if 'schema' in credentials:
        connection_parameters["schema"] = credentials['schema']
    
    try:
        print("Connecting to Snowflake...")
        
        # Use the builder pattern from the reference implementation
        sessionBuilder = Session.builder
        for key, value in connection_parameters.items():
            sessionBuilder = sessionBuilder.config(key, value)
        
        session = sessionBuilder.create()
        print("Connection successful!")
        return session
        
    except Exception as e:
        error_msg = f"Failed to connect: {str(e)}"
        print(error_msg)
        raise ConnectionError(error_msg)


def create_session_from_prompt() -> Session:
    """
    Convenience function to create a session with interactive prompting.
    
    This is an alias for create_session() with no arguments.
    
    Returns:
        Authenticated Snowflake Snowpark session
    """
    return create_session()
