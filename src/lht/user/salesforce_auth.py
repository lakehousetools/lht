"""
Salesforce authentication module with interactive credential prompting.

This module provides functions to interactively prompt users for Salesforce
credentials and save connection configurations.
"""

import getpass
from typing import Dict, Optional, Any
import requests


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


def login_user_flow(clientid: str, clientsecret: str, my_domain: str) -> Dict[str, Any]:
    """
    Perform OAuth2 client credentials authentication with Salesforce.
    
    Args:
        clientid: Salesforce Client ID
        clientsecret: Salesforce Client Secret
        my_domain: Salesforce My Domain (subdomain before .my.salesforce.com)
        
    Returns:
        Dictionary containing OAuth response (access_token, instance_url, etc.)
        
    Raises:
        requests.RequestException: If authentication request fails
    """
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    url = f"https://{my_domain}.my.salesforce.com/services/oauth2/token?grant_type=client_credentials&client_id={clientid}&client_secret={clientsecret}"
    
    r = requests.post(url, headers=headers)
    r.raise_for_status()  # Raise exception for bad status codes
    
    response_data = r.json()
    
    return response_data


def get_salesforce_access_info(connection_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Salesforce access_info from a saved connection.
    
    Loads a Salesforce connection, authenticates using OAuth2 client credentials flow,
    and returns the access_info dictionary needed for Salesforce API calls.
    
    Args:
        connection_name: Optional name of Salesforce connection to use.
                        If None, uses the primary Salesforce connection.
        
    Returns:
        Dictionary containing access_info with 'access_token' and 'instance_url'
        
    Raises:
        ValueError: If connection not found or invalid
        FileNotFoundError: If connections.toml doesn't exist
        requests.RequestException: If authentication fails
    """
    from lht.user.connections import load_connection, get_primary_connection
    
    # Get connection name if not provided
    if connection_name is None:
        connection_name = get_primary_connection('salesforce')
        if connection_name is None:
            raise ValueError(
                "No Salesforce connection specified and no primary Salesforce connection found. "
                "Please specify a connection with --salesforce or create a primary connection."
            )
    
    # Load connection credentials
    credentials = load_connection(connection_name)
    if credentials is None:
        raise ValueError(f"Salesforce connection '{connection_name}' not found")
    
    if credentials.get('connection_type', 'snowflake') != 'salesforce':
        raise ValueError(f"Connection '{connection_name}' is not a Salesforce connection")
    
    # Extract credentials
    client_id = credentials.get('client_id', '')
    client_key = credentials.get('client_key', '')
    my_domain = credentials.get('my_domain', '')
    
    if not client_id or not client_key or not my_domain:
        raise ValueError(
            f"Salesforce connection '{connection_name}' is missing required credentials. "
            "Need: client_id, client_key, my_domain"
        )
    
    # Authenticate with Salesforce
    auth_result = login_user_flow(client_id, client_key, my_domain)
    
    # Extract access_info from auth result
    access_info = {
        'access_token': auth_result.get('access_token'),
        'instance_url': auth_result.get('instance_url'),
    }
    
    if not access_info['access_token'] or not access_info['instance_url']:
        raise ValueError(
            f"Salesforce authentication failed for connection '{connection_name}'. "
            "Missing access_token or instance_url in response."
        )
    
    return access_info


def authenticate_salesforce() -> Dict[str, Any]:
    """
    Interactively prompt user for Salesforce authentication credentials and save connection.
    
    Prompts for:
    - client_id (required)
    - client_key (required)
    - sandbox (y/n)
    - my_domain (required)
    - redirect_url (optional, default: https://localhost:1717//OauthRedirect)
    - connection name (with default value from my_domain)
    - whether to make connection primary
    
    Returns:
        Dictionary containing authentication credentials
        
    Example:
        >>> creds = authenticate_salesforce()
        Client ID: 3MVG9...
        Client Key: ***
        Sandbox (y/n): n
        My Domain: mycompany
        Redirect URL [https://localhost:1717//OauthRedirect]: 
        Connection name [mycompany]: 
        Make this the primary connection? (y/n): y
    """
    print("=" * 60)
    print("Salesforce Authentication")
    print("=" * 60)
    print()
    print("Note: This interface currently only supports the web credentials flow.")
    print()
    
    client_id = _prompt_required("Client ID")
    client_key = getpass.getpass("Client Key: ").strip()
    
    if not client_key:
        print("Client Key is required.")
        raise ValueError("Client Key is required")
    
    # Prompt for sandbox (y/n)
    while True:
        sandbox_input = input("Sandbox (y/n): ").strip().lower()
        if sandbox_input in ['y', 'yes']:
            sandbox = True
            break
        elif sandbox_input in ['n', 'no', '']:
            sandbox = False
            break
        else:
            print("Please enter 'y' for yes or 'n' for no")
    
    my_domain = _prompt_required("My Domain")
    
    # Default redirect URL
    default_redirect_url = "https://localhost:1717//OauthRedirect"
    redirect_url = _prompt_required("Redirect URL", default=default_redirect_url)
    
    credentials = {
        'client_id': client_id,
        'client_key': client_key,
        'sandbox': sandbox,
        'my_domain': my_domain,
        'redirect_url': redirect_url,
    }
    
    print()
    print("✓ Credentials collected successfully")
    print()
    
    # Optionally test the connection
    test_connection = input("Test connection now? (y/n): ").strip().lower() == 'y'
    if test_connection:
        try:
            print("\nTesting Salesforce connection...")
            auth_result = login_user_flow(client_id, client_key, my_domain)
            if 'access_token' in auth_result:
                print("✓ Connection test successful!")
            else:
                print("⚠ Warning: Connection test completed but no access_token in response")
        except Exception as e:
            print(f"⚠ Warning: Connection test failed: {e}")
            print("Connection will still be saved, but may need to be corrected.")
    
    # Always save connection (optional import from connections module)
    try:
        from lht.user.connections import save_connection_config, set_primary_connection
        
        # Prompt for connection name with default value (first portion of my_domain)
        default_connection_name = my_domain.split('.')[0] if my_domain else 'salesforce_connection'
        connection_name = _prompt_required("Connection name", default=default_connection_name).strip()
        
        # Save connection
        save_connection_config(connection_name, credentials, connection_type='salesforce', copy_key=False)
        print(f"\n✓ Connection '{connection_name}' saved. You can now use it with:")
        print(f"  (connection utilities coming soon)")
        
        # Prompt to make primary
        print()
        make_primary = input("Make this the primary connection? (y/n): ").strip().lower() == 'y'
        if make_primary:
            try:
                set_primary_connection(connection_name, connection_type='salesforce')
            except Exception as e:
                print(f"Warning: Failed to set primary connection: {e}")
        
    except ImportError:
        print("Warning: Connections module not available. Connection was not saved.")
        print("Install a TOML library (tomli, toml) or use Python 3.11+ to enable connection saving.")
    except Exception as e:
        print(f"Warning: Failed to save connection: {e}")
    
    return credentials
