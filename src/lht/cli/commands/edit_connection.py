"""
Edit connection command implementation.
"""

import sys
from typing import Optional, Tuple


def _prompt_with_default(prompt: str, default: str = '') -> str:
    """
    Prompt user for input with a default value.
    
    Args:
        prompt: Prompt message
        default: Default value to show
        
    Returns:
        User input or default if empty
    """
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    value = input(full_prompt).strip()
    return value if value else default


def _prompt_optional(prompt: str, default: Optional[str] = None) -> Optional[str]:
    """
    Prompt user for optional input with a default value.
    
    Args:
        prompt: Prompt message
        default: Default value to show
        
    Returns:
        User input, default if empty, or None if no default
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


def _prompt_private_key_file(default_file: Optional[str] = None, default_passphrase: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Prompt user for private key file path and optional passphrase.
    
    Args:
        default_file: Default private key file path
        default_passphrase: Default passphrase (if any)
        
    Returns:
        Tuple of (private_key_file_path, passphrase or None)
    """
    print("\nPrivate Key File:")
    print("  Enter the path to your PEM private key file")
    print()
    
    while True:
        if default_file:
            key_file = _prompt_with_default("Private key file path", default_file)
        else:
            key_file = input("Private key file path: ").strip()
        
        if not key_file:
            print("Private key file is required. Please enter a value.")
            continue
        
        import os
        if not os.path.isfile(key_file):
            print(f"Error: File not found: {key_file}")
            response = input("Continue anyway? (y/n): ").strip().lower()
            if response != 'y':
                continue
        
        # Ask for passphrase if needed
        import getpass
        print("\nPrivate Key Passphrase:")
        print("  If your private key is encrypted, enter the passphrase.")
        print("  If not encrypted, press Enter to skip.")
        print()
        
        if default_passphrase:
            passphrase_input = getpass.getpass(f"Private key passphrase (optional) [current value hidden]: ").strip()
            # If user enters nothing, keep the existing passphrase
            if not passphrase_input:
                passphrase = default_passphrase
            else:
                passphrase = passphrase_input if passphrase_input else None
        else:
            passphrase_input = getpass.getpass("Private key passphrase (optional): ").strip()
            passphrase = passphrase_input if passphrase_input else None
        
        return key_file, passphrase


def edit_connection() -> int:
    """
    Edit an existing connection.
    
    Lists connections, prompts for selection, then prompts for all fields
    with existing values pre-populated.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from lht.user.connections import (
            list_connections as get_connections,
            get_primary_connection,
            load_connection,
            update_connection
        )
        
        connections = get_connections()
        
        if not connections:
            print("No saved connections found.")
            print("Create a connection first using:")
            print("  lht create-connection --snowflake")
            print("  lht create-connection --salesforce")
            return 1
        
        # Get primary connections if set
        primary_snowflake = get_primary_connection('snowflake')
        primary_salesforce = get_primary_connection('salesforce')
        
        # Display numbered list
        print("\n" + "=" * 60)
        print("Select Connection to Edit")
        print("=" * 60)
        print()
        
        for i, conn_name in enumerate(connections, 1):
            # Load connection to determine type for marker
            conn_details = load_connection(conn_name)
            conn_type = conn_details.get('connection_type', 'snowflake').lower() if conn_details else 'snowflake'
            
            if conn_type == 'snowflake' and conn_name == primary_snowflake:
                marker = " (PRIMARY SNOWFLAKE)"
            elif conn_type == 'salesforce' and conn_name == primary_salesforce:
                marker = " (PRIMARY SALESFORCE)"
            else:
                marker = ""
            
            print(f"  {i}. {conn_name}{marker}")
        
        print()
        
        # Prompt for selection
        while True:
            try:
                selection = input(f"Enter connection number (1-{len(connections)}): ").strip()
                conn_index = int(selection) - 1
                
                if 0 <= conn_index < len(connections):
                    selected_connection = connections[conn_index]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(connections)}")
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\n\n✗ Edit cancelled by user")
                return 1
        
        # Load existing connection details
        existing_credentials = load_connection(selected_connection)
        
        if not existing_credentials:
            print(f"Error: Could not load connection '{selected_connection}'")
            return 1
        
        print("\n" + "=" * 60)
        print(f"Editing Connection: {selected_connection}")
        print("=" * 60)
        print()
        print("Enter new values or press Enter to keep existing value")
        print()
        
        # Determine connection type
        connection_type = existing_credentials.get('connection_type', 'snowflake').lower()
        
        if connection_type == 'snowflake':
            # Prompt for all Snowflake fields with existing values as defaults
            account = _prompt_with_default("Account", existing_credentials.get('account', ''))
            username = _prompt_with_default("Username", existing_credentials.get('user', ''))
            role = _prompt_with_default("Role", existing_credentials.get('role', ''))
            warehouse = _prompt_with_default("Warehouse", existing_credentials.get('warehouse', ''))
            
            # Private key file handling
            existing_key_file = existing_credentials.get('private_key_file', '')
            existing_passphrase = existing_credentials.get('private_key_passphrase', '')
            private_key_file, private_key_passphrase = _prompt_private_key_file(
                default_file=existing_key_file if existing_key_file else None,
                default_passphrase=existing_passphrase if existing_passphrase else None
            )
            
            database = _prompt_optional("Database", existing_credentials.get('database', ''))
            schema = _prompt_optional("Schema", existing_credentials.get('schema', ''))
            
            # Build updated credentials
            updated_credentials = {
                'connection_type': 'snowflake',
                'account': account,
                'user': username,
                'role': role,
                'warehouse': warehouse,
                'private_key_file': private_key_file,
                'private_key_passphrase': private_key_passphrase,
            }
            
            if database:
                updated_credentials['database'] = database
            if schema:
                updated_credentials['schema'] = schema
                
        elif connection_type == 'salesforce':
            # Prompt for all Salesforce fields with existing values as defaults
            client_id = _prompt_with_default("Client ID", existing_credentials.get('client_id', ''))
            
            # For client_key, we need special handling since we don't want to show the existing value
            import getpass
            print("\nClient Key:")
            print("  Enter new client key or press Enter to keep existing value")
            print()
            client_key_input = getpass.getpass("Client Key (press Enter to keep existing): ").strip()
            if client_key_input:
                client_key = client_key_input
            else:
                # Keep existing value
                client_key = existing_credentials.get('client_key', '')
            
            # Sandbox (y/n)
            existing_sandbox = existing_credentials.get('sandbox', False)
            sandbox_str = 'y' if existing_sandbox else 'n'
            while True:
                sandbox_input = input(f"Sandbox (y/n) [{sandbox_str}]: ").strip().lower()
                if sandbox_input in ['y', 'yes']:
                    sandbox = True
                    break
                elif sandbox_input in ['n', 'no', '']:
                    sandbox = False
                    break
                else:
                    print("Please enter 'y' for yes or 'n' for no")
            
            my_domain = _prompt_with_default("My Domain", existing_credentials.get('my_domain', ''))
            redirect_url = _prompt_with_default("Redirect URL", existing_credentials.get('redirect_url', 'https://localhost:1717//OauthRedirect'))
            
            # Build updated credentials
            updated_credentials = {
                'connection_type': 'salesforce',
                'client_id': client_id,
                'client_key': client_key,
                'sandbox': sandbox,
                'my_domain': my_domain,
                'redirect_url': redirect_url,
            }
        else:
            print(f"Error: Unknown connection type '{connection_type}'")
            return 1
        
        print()
        print("✓ Updated credentials collected")
        print()
        
        # Update the connection
        # Only copy key for Snowflake connections
        copy_key = (connection_type == 'snowflake')
        success = update_connection(selected_connection, updated_credentials, connection_type=connection_type, copy_key=copy_key)
        
        if success:
            print("\n" + "=" * 60)
            print(f"✓ Connection '{selected_connection}' updated successfully!")
            print("=" * 60)
            
            # Ask if user wants to set this as primary
            print()
            from lht.user.connections import set_primary_connection, get_primary_connection
            current_primary = get_primary_connection(connection_type)
            if current_primary == selected_connection:
                print(f"✓ This connection is already set as the primary {connection_type} connection.")
            else:
                make_primary = input(f"Set '{selected_connection}' as the primary {connection_type} connection? (y/n): ").strip().lower() == 'y'
                if make_primary:
                    try:
                        set_primary_connection(selected_connection, connection_type=connection_type)
                        print(f"✓ Set '{selected_connection}' as primary {connection_type} connection")
                    except Exception as e:
                        print(f"⚠ Warning: Failed to set primary connection: {e}")
            
            return 0
        else:
            print(f"\n✗ Failed to update connection '{selected_connection}'")
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
    except KeyboardInterrupt:
        print("\n\n✗ Edit cancelled by user")
        return 1
    except Exception as e:
        print(f"Error editing connection: {e}")
        import traceback
        traceback.print_exc()
        return 1

