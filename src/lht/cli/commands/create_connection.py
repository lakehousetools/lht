"""
Create connection command implementations.
"""

import sys
from lht.user.auth import authenticate
from lht.user.salesforce_auth import authenticate_salesforce


def snowflake() -> int:
    """
    Create a new Snowflake connection.
    
    This performs the same action as test_auth.py - it calls authenticate()
    which will interactively prompt for credentials and save the connection.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        credentials = authenticate()
        
        if credentials:
            print("\n" + "=" * 60)
            print("✓ Connection created successfully!")
            print("=" * 60)
            return 0
        else:
            print("\n✗ Connection creation cancelled or failed.")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n✗ Connection creation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error creating connection: {e}")
        import traceback
        traceback.print_exc()
        return 1


def salesforce() -> int:
    """
    Create a new Salesforce connection.
    
    This calls authenticate_salesforce() which will interactively prompt for
    Salesforce credentials and save the connection.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        credentials = authenticate_salesforce()
        
        if credentials:
            print("\n" + "=" * 60)
            print("✓ Connection created successfully!")
            print("=" * 60)
            return 0
        else:
            print("\n✗ Connection creation cancelled or failed.")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n✗ Connection creation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error creating connection: {e}")
        import traceback
        traceback.print_exc()
        return 1

