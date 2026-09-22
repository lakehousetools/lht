"""
Salesforce authentication module with interactive credential prompting.

This module provides functions to interactively prompt users for Salesforce
credentials and save connection configurations.
"""

import base64
import getpass
import json
import os
import time
from typing import Dict, Optional, Any
import requests

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    raise ImportError(
        "cryptography library is required for JWT bearer authentication. "
        "Install it with: pip install cryptography"
    )


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
    # Credentials go in a form-encoded body, never the query string. A query string is recorded
    # by proxies, load balancers and server access logs, where a body is not -- and
    # raise_for_status() below puts the full URL into the HTTPError message, so with the secret
    # in the URL any failed login printed it into whatever handled the exception. The token
    # endpoint expects application/x-www-form-urlencoded, which requests sets itself for `data=`.
    url = f"https://{my_domain}.my.salesforce.com/services/oauth2/token"

    r = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": clientid,
            "client_secret": clientsecret,
        },
        headers={"Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()  # Safe to surface now: the URL carries no credential

    response_data = r.json()

    return response_data


def _b64url(data: bytes) -> str:
    """Base64url without padding, as the JWT spec requires."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _load_rsa_private_key(private_key_pem: bytes, passphrase: Optional[str] = None):
    """Loads a PEM-encoded RSA private key for JWT signing.

    Unlike auth.py's _load_private_key (which converts to DER for the
    Snowflake connector), this keeps the key as a cryptography key object,
    since sign() below needs to call it directly. Accepts PEM bytes rather
    than a file path so a Databricks job can pass secret content straight
    through without ever writing it to disk.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError("cryptography library is required")

    try:
        return serialization.load_pem_private_key(
            private_key_pem,
            password=passphrase.encode() if passphrase else None,
            backend=default_backend(),
        )
    except Exception as e:
        raise ValueError(f"Failed to load private key: {str(e)}")


def build_jwt_assertion(client_id: str, username: str, login_url: str,
                         private_key_pem: bytes, passphrase: Optional[str] = None,
                         expires_in_seconds: int = 180) -> str:
    """
    Builds and signs the JWT bearer assertion Salesforce expects.

    Built by hand (header/payload/signature, RS256) rather than via a JWT
    library, since `cryptography` -- already an lht dependency for the
    Snowflake key-pair flow -- is all RS256 signing needs; no reason to add
    PyJWT as a second dependency for the same primitive.

    Args:
        client_id: Connected App consumer key (JWT `iss`)
        username: Salesforce username to authenticate as (JWT `sub`) --
                  this must be a user the Connected App is pre-authorized
                  for (Setup > Manage Connected Apps > this app), since the
                  JWT bearer flow has no interactive consent step.
        login_url: Token endpoint's issuer, e.g. https://login.salesforce.com
                   (production/most sandboxes with My Domain) or
                   https://test.salesforce.com (sandbox without My Domain).
        private_key_pem: PEM bytes of the private key matching the digital
                          certificate uploaded to the Connected App.
        expires_in_seconds: JWT validity window. Keep short -- this is
                             minted fresh on every call, not reused, so
                             there's no benefit to a longer window.

    Returns:
        The signed JWT assertion string.
    """
    private_key = _load_rsa_private_key(private_key_pem, passphrase)

    header = {"alg": "RS256"}
    payload = {
        "iss": client_id,
        "sub": username,
        "aud": login_url,
        "exp": int(time.time()) + expires_in_seconds,
    }

    signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}"
    signature = private_key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input}.{_b64url(signature)}"


def jwt_bearer_flow(client_id: str, username: str, login_url: str,
                     private_key_pem: bytes, passphrase: Optional[str] = None) -> Dict[str, Any]:
    """
    Authenticates with Salesforce using the OAuth 2.0 JWT bearer flow.

    Unlike login_user_flow's client_credentials grant, this needs no client
    secret and no interactive login -- only a pre-authorized Connected App
    and a private key -- which is what makes it suitable for a headless
    scheduled job (e.g. a Databricks Job) instead of a human-driven flow.
    There is no refresh token to manage: since a fresh JWT is minted and
    exchanged on every call, "refreshing" the access token just means
    calling this function again.

    Args:
        client_id: Connected App consumer key
        username: Salesforce username to authenticate as
        login_url: Token endpoint's issuer -- see build_jwt_assertion
        private_key_pem: PEM bytes of the matching private key
        passphrase: Optional passphrase if the private key is encrypted

    Returns:
        Dictionary containing the OAuth response (access_token, instance_url, etc.)

    Raises:
        requests.RequestException: If the token exchange fails
    """
    assertion = build_jwt_assertion(client_id, username, login_url, private_key_pem, passphrase)

    url = f"{login_url}/services/oauth2/token"
    r = requests.post(
        url,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        headers={"Accept": "application/json"},
        timeout=60,
    )
    if not r.ok:
        # Bubble up Salesforce's own error description (e.g. "invalid_grant:
        # user hasn't approved this consumer") rather than a bare status code --
        # that's almost always exactly why a JWT bearer login fails.
        raise requests.HTTPError(f"JWT bearer authentication failed ({r.status_code}): {r.text[:500]}", response=r)

    return r.json()


def _access_info_from_auth_result(auth_result: Dict[str, Any], context: str) -> Dict[str, Any]:
    access_info = {
        'access_token': auth_result.get('access_token'),
        'instance_url': auth_result.get('instance_url'),
    }
    if not access_info['access_token'] or not access_info['instance_url']:
        raise ValueError(
            f"Salesforce authentication failed for {context}. "
            "Missing access_token or instance_url in response."
        )
    return access_info


def get_salesforce_access_info_from_credentials(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Authenticates using a credentials dict directly, bypassing connections.toml
    entirely -- the entry point for a headless caller (a Databricks job, a
    CI job) that sources its own credentials from a secret store rather than
    a local file. Mirrors the flexible credentials-dict-or-connection-name
    shape auth.py's create_session() already uses for Snowflake.

    Dispatches on credentials['auth_flow']:
      - 'jwt_bearer' (recommended for unattended use): needs client_id,
        username, private_key_pem (bytes or str), login_url (optional --
        defaults from `sandbox`), private_key_passphrase (optional).
      - 'client_credentials' (default, matches the interactive flow):
        needs client_id, client_key, my_domain.

    Args:
        credentials: Dict as described above.

    Returns:
        Dictionary containing access_info with 'access_token' and 'instance_url'

    Raises:
        ValueError: If required fields are missing for the chosen auth_flow
        requests.RequestException: If authentication fails
    """
    auth_flow = credentials.get('auth_flow', 'client_credentials')

    if auth_flow == 'jwt_bearer':
        client_id = credentials.get('client_id', '')
        username = credentials.get('username', '')
        private_key_pem = credentials.get('private_key_pem', '')
        if not client_id or not username or not private_key_pem:
            raise ValueError(
                "JWT bearer auth needs: client_id, username, private_key_pem"
            )
        if isinstance(private_key_pem, str):
            private_key_pem = private_key_pem.encode()

        login_url = credentials.get('login_url') or (
            'https://test.salesforce.com' if credentials.get('sandbox') else 'https://login.salesforce.com'
        )

        auth_result = jwt_bearer_flow(
            client_id, username, login_url, private_key_pem,
            passphrase=credentials.get('private_key_passphrase') or None,
        )
        return _access_info_from_auth_result(auth_result, f"JWT bearer flow (user '{username}')")

    elif auth_flow == 'client_credentials':
        client_id = credentials.get('client_id', '')
        client_key = credentials.get('client_key', '')
        my_domain = credentials.get('my_domain', '')
        if not client_id or not client_key or not my_domain:
            raise ValueError(
                "client_credentials auth needs: client_id, client_key, my_domain"
            )
        auth_result = login_user_flow(client_id, client_key, my_domain)
        return _access_info_from_auth_result(auth_result, f"client_credentials flow (domain '{my_domain}')")

    raise ValueError(f"Unknown auth_flow: {auth_flow!r}. Must be 'jwt_bearer' or 'client_credentials'")


def get_salesforce_access_info(connection_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Salesforce access_info from a saved connection.

    Loads a Salesforce connection from connections.toml and authenticates
    with whichever auth_flow that connection is configured for (see
    get_salesforce_access_info_from_credentials) -- 'client_credentials' by
    default, matching every connection saved before auth_flow existed.

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

    return get_salesforce_access_info_from_credentials(credentials)


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
