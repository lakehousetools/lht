"""
Sync Salesforce object command implementation.
"""

import sys
from typing import Optional
from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info
from lht.user.connections import get_primary_connection, load_connection
from lht.salesforce import sync_sobject_intelligent


def sync_sobject(
    sobject: str,
    table: str,
    schema: Optional[str] = None,
    database: Optional[str] = None,
    snowflake_connection: Optional[str] = None,
    salesforce_connection: Optional[str] = None,
    match_field: str = 'ID',
    use_stage: bool = False,
    stage_name: Optional[str] = None,
    force_full_sync: bool = False,
    force_bulk_api: bool = False,
    existing_job_id: Optional[str] = None,
    delete_job: bool = True
) -> int:
    """
    Sync a Salesforce object to Snowflake.
    
    Args:
        sobject: Salesforce object name (required)
        table: Snowflake table name (required)
        schema: Snowflake schema (optional, uses connection default if available)
        database: Snowflake database (optional, uses connection default if available)
        snowflake_connection: Snowflake connection name (optional, uses primary if not specified)
        salesforce_connection: Salesforce connection name (optional, uses primary if not specified)
        match_field: Field to use for matching records (default: 'ID')
        use_stage: Whether to use Snowflake stage for large datasets
        stage_name: Snowflake stage name (required if use_stage=True)
        force_full_sync: Force a full sync regardless of previous sync status
        force_bulk_api: Force use of Bulk API 2.0 instead of regular API
        existing_job_id: Optional existing Bulk API job ID to use
        delete_job: Whether to delete the Bulk API job after completion (default: True)
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Get Snowflake connection
        if snowflake_connection is None:
            snowflake_connection = get_primary_connection('snowflake')
            if snowflake_connection is None:
                # Try to find a Snowflake connection automatically
                from lht.user.connections import list_connections as get_all_connections
                all_connections = get_all_connections()
                snowflake_connections = []
                for conn_name in all_connections:
                    conn_details = load_connection(conn_name)
                    if conn_details:
                        conn_type = conn_details.get('connection_type', 'snowflake').lower()
                        if conn_type == 'snowflake':
                            snowflake_connections.append(conn_name)
                
                if len(snowflake_connections) == 1:
                    # Only one Snowflake connection, use it automatically
                    snowflake_connection = snowflake_connections[0]
                    print(f"ℹ Using the only available Snowflake connection: {snowflake_connection}")
                elif len(snowflake_connections) > 1:
                    print("Error: No Snowflake connection specified and no primary Snowflake connection found.")
                    print(f"Found {len(snowflake_connections)} Snowflake connections: {', '.join(snowflake_connections)}")
                    print("Please specify a connection with --snowflake or set a primary connection using:")
                    print("  lht edit-connection")
                    return 1
                else:
                    print("Error: No Snowflake connection specified and no primary Snowflake connection found.")
                    print("Please create a Snowflake connection first using:")
                    print("  lht create-connection --snowflake")
                    return 1
        
        print(f"✓ Using Snowflake connection: {snowflake_connection}")
        
        # Load Snowflake connection to get database/schema defaults
        snowflake_creds = load_connection(snowflake_connection)
        if snowflake_creds is None:
            print(f"Error: Snowflake connection '{snowflake_connection}' not found")
            return 1
        
        # Use database/schema from connection if not provided
        if database is None:
            database = snowflake_creds.get('database')
        
        if schema is None:
            schema = snowflake_creds.get('schema')
        
        # Validate schema is available
        if not schema:
            print("Error: Schema is required. Please specify --schema or ensure your Snowflake connection has a schema configured.")
            return 1
        
        # Create Snowflake session
        print(f"✓ Connecting to Snowflake...")
        session = create_session(connection_name=snowflake_connection)
        print(f"✓ Connected to Snowflake")
        
        # Get Salesforce connection
        if salesforce_connection is None:
            salesforce_connection = get_primary_connection('salesforce')
            if salesforce_connection is None:
                # Try to find a Salesforce connection automatically
                from lht.user.connections import list_connections as get_all_connections
                all_connections = get_all_connections()
                salesforce_connections = []
                for conn_name in all_connections:
                    conn_details = load_connection(conn_name)
                    if conn_details:
                        conn_type = conn_details.get('connection_type', 'snowflake').lower()
                        if conn_type == 'salesforce':
                            salesforce_connections.append(conn_name)
                
                if len(salesforce_connections) == 1:
                    # Only one Salesforce connection, use it automatically
                    salesforce_connection = salesforce_connections[0]
                    print(f"ℹ Using the only available Salesforce connection: {salesforce_connection}")
                elif len(salesforce_connections) > 1:
                    print("Error: No Salesforce connection specified and no primary Salesforce connection found.")
                    print(f"Found {len(salesforce_connections)} Salesforce connections: {', '.join(salesforce_connections)}")
                    print("Please specify a connection with --salesforce or set a primary connection using:")
                    print("  lht edit-connection")
                    return 1
                else:
                    print("Error: No Salesforce connection specified and no primary Salesforce connection found.")
                    print("Please create a Salesforce connection first using:")
                    print("  lht create-connection --salesforce")
                    return 1
        
        print(f"✓ Using Salesforce connection: {salesforce_connection}")
        
        # Authenticate with Salesforce and get access_info
        print(f"✓ Authenticating with Salesforce...")
        access_info = get_salesforce_access_info(salesforce_connection)
        print(f"✓ Authenticated with Salesforce")
        
        # Validate stage_name if use_stage is True
        if use_stage and not stage_name:
            print("Error: --stage-name is required when --use-stage is specified")
            return 1
        
        # Display sync configuration
        print("\n" + "=" * 60)
        print("Sync Configuration")
        print("=" * 60)
        print(f"Salesforce Object: {sobject}")
        print(f"Target Table: {table}")
        if database:
            print(f"Database: {database}")
        print(f"Schema: {schema}")
        print(f"Match Field: {match_field}")
        if use_stage:
            print(f"Using Stage: {stage_name}")
        if force_full_sync:
            print("Force Full Sync: Yes")
        if force_bulk_api:
            print("Force Bulk API: Yes")
        if existing_job_id:
            print(f"Existing Job ID: {existing_job_id}")
        print(f"Delete Job: {delete_job}")
        print("=" * 60)
        print()
        
        # Perform the sync
        print("Starting sync...")
        result = sync_sobject_intelligent(
            session=session,
            access_info=access_info,
            sobject=sobject,
            schema=schema,
            table=table,
            match_field=match_field,
            use_stage=use_stage,
            stage_name=stage_name,
            force_full_sync=force_full_sync,
            force_bulk_api=force_bulk_api,
            existing_job_id=existing_job_id,
            delete_job=delete_job
        )
        
        # Display results
        print("\n" + "=" * 60)
        print("Sync Results")
        print("=" * 60)
        print(f"Sync Method: {result.get('sync_method', 'unknown')}")
        print(f"Estimated Records: {result.get('estimated_records', 0):,}")
        print(f"Actual Records: {result.get('actual_records', 0):,}")
        print(f"Duration: {result.get('sync_duration_seconds', 0):.2f} seconds")
        if result.get('last_modified_date'):
            print(f"Last Modified Date: {result.get('last_modified_date')}")
        print("=" * 60)
        
        if result.get('sync_method') == 'failed':
            print("\n✗ Sync failed")
            return 1
        else:
            print("\n✓ Sync completed successfully")
            return 0
            
    except KeyboardInterrupt:
        print("\n\n✗ Sync cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        return 1

