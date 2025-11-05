"""
List connections command implementation.
"""

import sys


def list_connections() -> int:
    """
    List all saved connections with full details.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from lht.user.connections import (
            list_connections as get_connections,
            get_primary_connection,
            load_connection
        )
        
        connections = get_connections()
        
        if not connections:
            print("No saved connections found.")
            return 0
        
        # Get primary connections if set
        primary_snowflake = get_primary_connection('snowflake')
        primary_salesforce = get_primary_connection('salesforce')
        
        # For backward compatibility, also check legacy primary
        primary_legacy = get_primary_connection()
        
        print("\n" + "=" * 60)
        print("Saved Connections")
        print("=" * 60)
        print()
        
        for i, conn_name in enumerate(connections, 1):
            # Determine primary marker based on connection type
            conn_details = load_connection(conn_name) if connections else None
            conn_type = conn_details.get('connection_type', 'snowflake').lower() if conn_details else 'snowflake'
            
            if conn_type == 'snowflake' and conn_name == primary_snowflake:
                marker = " (PRIMARY SNOWFLAKE)"
            elif conn_type == 'salesforce' and conn_name == primary_salesforce:
                marker = " (PRIMARY SALESFORCE)"
            elif conn_name == primary_legacy and (primary_snowflake is None or primary_salesforce is None):
                # Show legacy primary marker if type-specific primary not set
                marker = " (PRIMARY)"
            else:
                marker = ""
            
            print(f"\n{i}. {conn_name}{marker}")
            print("-" * 60)
            
            # Load connection details
            try:
                if not conn_details:
                    conn_details = load_connection(conn_name)
                if conn_details:
                    connection_type = conn_details.get('connection_type', 'snowflake').upper()
                    print(f"   Type:          {connection_type}")
                    
                    if connection_type == 'SNOWFLAKE':
                        print(f"   Account:       {conn_details.get('account', 'N/A')}")
                        print(f"   User:          {conn_details.get('user', 'N/A')}")
                        print(f"   Role:          {conn_details.get('role', 'N/A')}")
                        print(f"   Warehouse:     {conn_details.get('warehouse', 'N/A')}")
                        
                        database = conn_details.get('database', '')
                        if database:
                            print(f"   Database:      {database}")
                        else:
                            print(f"   Database:      (not set)")
                        
                        schema = conn_details.get('schema', '')
                        if schema:
                            print(f"   Schema:        {schema}")
                        else:
                            print(f"   Schema:        (not set)")
                        
                        private_key_file = conn_details.get('private_key_file', '')
                        if private_key_file:
                            # Show just the filename, not the full path for privacy
                            import os
                            key_filename = os.path.basename(private_key_file)
                            print(f"   Private Key:   {key_filename}")
                        
                        if conn_details.get('private_key_passphrase'):
                            print(f"   Passphrase:    (set)")
                        else:
                            print(f"   Passphrase:    (not set)")
                    elif connection_type == 'SALESFORCE':
                        print(f"   Client ID:     {conn_details.get('client_id', 'N/A')}")
                        print(f"   Client Key:    {'(set)' if conn_details.get('client_key') else '(not set)'}")
                        print(f"   My Domain:     {conn_details.get('my_domain', 'N/A')}")
                        print(f"   Sandbox:       {'Yes' if conn_details.get('sandbox') else 'No'}")
                        print(f"   Redirect URL:  {conn_details.get('redirect_url', 'N/A')}")
                else:
                    print("   (Unable to load connection details)")
            except Exception as e:
                print(f"   Error loading details: {e}")
        
        print("\n" + "=" * 60)
        print(f"Total: {len(connections)} connection(s)")
        if primary_snowflake:
            print(f"Primary Snowflake: {primary_snowflake}")
        if primary_salesforce:
            print(f"Primary Salesforce: {primary_salesforce}")
        print()
        
        return 0
        
    except ImportError:
        print("Error: Connections module not available.")
        print("Install a TOML library (tomli, toml) or use Python 3.11+ to enable connection management.")
        return 1
    except FileNotFoundError:
        print("No connections file found. Create a connection first using:")
        print("  lht create-connection --snowflake")
        return 1
    except Exception as e:
        print(f"Error listing connections: {e}")
        import traceback
        traceback.print_exc()
        return 1

