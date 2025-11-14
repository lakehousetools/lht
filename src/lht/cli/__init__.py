"""
Command Line Interface for LHT.

This module provides argument parsing and command routing for the LHT CLI.
"""

import argparse
from typing import List, Optional
from lht.cli.commands.create_connection import snowflake
from lht.cli.commands.list_connections import list_connections as list_connections_cmd
from lht.cli.commands.edit_connection import edit_connection


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='lht',
        description='Lakehouse Tools for Snowflake and Salesforce',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lht create-connection --snowflake    Create a new Snowflake connection
  lht create-connection --salesforce   Create a new Salesforce connection
  lht list-connections                 List all saved connections
  lht connect CONNECTION                Verify a connection works
  lht edit-connection                  Edit an existing connection
  lht set-primary CONNECTION           Set a connection as primary
  lht sync --sobject Account --table ACCOUNT  Sync Salesforce Account to Snowflake
        """
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        metavar='COMMAND'
    )
    
    # create-connection command
    create_conn_parser = subparsers.add_parser(
        'create-connection',
        help='Create a new connection configuration',
        description='Create and save a new connection configuration'
    )
    
    # Connection type flags (mutually exclusive group)
    conn_type_group = create_conn_parser.add_mutually_exclusive_group(required=True)
    conn_type_group.add_argument(
        '--snowflake',
        action='store_true',
        help='Create a Snowflake connection'
    )
    conn_type_group.add_argument(
        '--salesforce',
        action='store_true',
        help='Create a Salesforce connection'
    )
    
    # list-connections command
    subparsers.add_parser(
        'list-connections',
        help='List all saved connections',
        description='Display all saved connection configurations'
    )
    
    # edit-connection command
    subparsers.add_parser(
        'edit-connection',
        help='Edit an existing connection',
        description='Edit an existing connection configuration'
    )
    
    # set-primary command
    set_primary_parser = subparsers.add_parser(
        'set-primary',
        help='Set a connection as the primary connection for its type',
        description='Set a connection as the primary/default connection for Snowflake or Salesforce'
    )
    set_primary_parser.add_argument(
        'connection_name',
        help='Name of the connection to set as primary'
    )
    
    # connect command
    connect_parser = subparsers.add_parser(
        'connect',
        help='Verify a connection works',
        description='Verify a saved connection by attempting to connect and perform a basic operation'
    )
    connect_parser.add_argument(
        'connection_name',
        help='Name of the connection to verify'
    )
    
    # sync command
    sync_parser = subparsers.add_parser(
        'sync',
        help='Sync a Salesforce object to Snowflake',
        description='Synchronize a Salesforce SObject to a Snowflake table'
    )
    
    # Required arguments
    sync_parser.add_argument(
        '--sobject',
        required=True,
        help='Salesforce object name (e.g., Account, Contact)'
    )
    sync_parser.add_argument(
        '--table',
        required=True,
        help='Snowflake table name'
    )
    
    # Optional arguments with defaults from connection
    sync_parser.add_argument(
        '--schema',
        help='Snowflake schema (defaults to connection if available)'
    )
    sync_parser.add_argument(
        '--database',
        help='Snowflake database (defaults to connection if available)'
    )
    
    # Connection arguments
    sync_parser.add_argument(
        '--snowflake',
        metavar='NAME',
        help='Snowflake connection name (defaults to primary connection)'
    )
    sync_parser.add_argument(
        '--salesforce',
        metavar='NAME',
        help='Salesforce connection name (defaults to primary connection)'
    )
    
    # Sync options
    sync_parser.add_argument(
        '--match-field',
        default='ID',
        help='Field to use for matching records (default: ID)'
    )
    sync_parser.add_argument(
        '--use-stage',
        action='store_true',
        help='Use Snowflake stage for large datasets'
    )
    sync_parser.add_argument(
        '--stage-name',
        help='Snowflake stage name (required if --use-stage is specified)'
    )
    sync_parser.add_argument(
        '--force-full-sync',
        action='store_true',
        help='Force a full sync regardless of previous sync status'
    )
    sync_parser.add_argument(
        '--force-bulk-api',
        action='store_true',
        help='Force use of Bulk API 2.0 instead of regular API'
    )
    sync_parser.add_argument(
        '--existing-job-id',
        help='Optional existing Bulk API job ID to use'
    )
    sync_parser.add_argument(
        '--no-delete-job',
        action='store_true',
        help='Do not delete the Bulk API job after completion'
    )
    
    return parser


def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for CLI.
    
    Args:
        args: Optional command line arguments (for testing). If None, uses sys.argv.
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    # Route to appropriate command handler
    if parsed_args.command == 'create-connection':
        if parsed_args.snowflake:
            return snowflake()
        elif parsed_args.salesforce:
            from lht.cli.commands.create_connection import salesforce
            return salesforce()
        else:
            parser.error("Connection type required. Use --snowflake or --salesforce")
    elif parsed_args.command == 'list-connections':
        return list_connections_cmd()
    elif parsed_args.command == 'edit-connection':
        return edit_connection()
    elif parsed_args.command == 'set-primary':
        from lht.cli.commands.set_primary import set_primary
        return set_primary(parsed_args.connection_name)
    elif parsed_args.command == 'connect':
        from lht.cli.commands.connect import connect
        return connect(parsed_args.connection_name)
    elif parsed_args.command == 'sync':
        from lht.cli.commands.sync_sobject import sync_sobject
        return sync_sobject(
            sobject=parsed_args.sobject,
            table=parsed_args.table,
            schema=parsed_args.schema,
            database=parsed_args.database,
            snowflake_connection=parsed_args.snowflake,
            salesforce_connection=parsed_args.salesforce,
            match_field=parsed_args.match_field,
            use_stage=parsed_args.use_stage,
            stage_name=parsed_args.stage_name,
            force_full_sync=parsed_args.force_full_sync,
            force_bulk_api=parsed_args.force_bulk_api,
            existing_job_id=parsed_args.existing_job_id,
            delete_job=not parsed_args.no_delete_job
        )
    
    # No command provided
    parser.print_help()
    return 1

