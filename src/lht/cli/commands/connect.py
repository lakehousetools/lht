"""
Connect command implementation - verify a connection works.
"""

import sys
from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info
from lht.user.connections import load_connection


def connect(connection_name: str) -> int:
    """
    Verify a connection by attempting to connect and perform a basic operation.
    
    Args:
        connection_name: Name of the connection to verify.
        
    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Load connection to determine type
        credentials = load_connection(connection_name)
        if credentials is None:
            print(f"Error: Connection '{connection_name}' not found.")
            return 1
        
        connection_type = credentials.get('connection_type', 'snowflake').lower()
        
        print("=" * 60)
        print(f"Verifying {connection_type.capitalize()} Connection: {connection_name}")
        print("=" * 60)
        print()
        
        if connection_type == 'snowflake':
            return _verify_snowflake(connection_name)
        elif connection_type == 'salesforce':
            return _verify_salesforce(connection_name)
        else:
            print(f"Error: Unknown connection type '{connection_type}'.")
            return 1
            
    except Exception as e:
        print(f"Error verifying connection: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _verify_snowflake(connection_name: str) -> int:
    """Verify a Snowflake connection."""
    try:
        # create_session() already tests the connection and prints success/failure
        session = create_session(connection_name=connection_name)
        
        # Run a simple query to verify it works
        print("Verifying connection with query...")
        result = session.sql("SELECT CURRENT_VERSION()").collect()
        version = result[0][0]
        
        # Get current database and schema
        db_result = session.sql("SELECT CURRENT_DATABASE()").collect()
        schema_result = session.sql("SELECT CURRENT_SCHEMA()").collect()
        current_db = db_result[0][0] if db_result else "N/A"
        current_schema = schema_result[0][0] if schema_result else "N/A"
        
        print()
        print("✓ Connection verified successfully!")
        print(f"  Snowflake Version: {version}")
        print(f"  Current Database: {current_db}")
        print(f"  Current Schema: {current_schema}")
        print()
        
        session.close()
        return 0
        
    except Exception as e:
        print()
        print(f"✗ Connection verification failed: {e}")
        print()
        return 1


def _verify_salesforce(connection_name: str) -> int:
    """Verify a Salesforce connection."""
    try:
        # get_salesforce_access_info() already authenticates and validates
        access_info = get_salesforce_access_info(connection_name)
        
        # Make a simple API call to verify it works
        print("Verifying connection with API call...")
        import requests
        
        headers = {
            "Authorization": f"Bearer {access_info['access_token']}",
            "Content-Type": "application/json"
        }
        url = f"{access_info['instance_url']}/services/data/v58.0/sobjects"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        print()
        print("✓ Connection verified successfully!")
        print(f"  Instance URL: {access_info['instance_url']}")
        print(f"  API Version: v58.0")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print(f"✗ Connection verification failed: {e}")
        print()
        return 1

