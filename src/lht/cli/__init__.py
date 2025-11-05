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
  lht edit-connection                  Edit an existing connection
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
    
    # No command provided
    parser.print_help()
    return 1

