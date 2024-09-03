
import toml
#from salesforce import sobject_create
from salesforce import sobject_create, sobject_sync
from snowflake.snowpark import Session
from user import auth
import argparse
import sys
from user import salesforce_login as sf_login

def snowflake_connection(connection_name):
    config = toml.load(".snowflake/connections.toml")
    print(connection_name)
    snowflake_config = config[connection_name]

    connection_parameters = {
        "account": snowflake_config["account"],
        "user": snowflake_config["user"],
        "password": snowflake_config["password"],
        "warehouse": snowflake_config["warehouse"],
        "database": snowflake_config["database"],
        "schema": snowflake_config["schema"]
    }
    sessionBuilder = Session.builder
    for key, value in connection_parameters.items():
        sessionBuilder.config(key, value)

    session = sessionBuilder.create()
    return session


def main():
    # Create the top-level parser
    parser = argparse.ArgumentParser(description='CLI tool for create and sync commands.')    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Define the "create" subcommand
    create_parser = subparsers.add_parser('create', help='Create something')
    create_parser.add_argument('--sobject','--sobj', type=str, required=True, help='The Salesforce sobject to create')
    create_parser.add_argument('--table', '--t', type=str, required=True, help='The name of the table to create')
    create_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection')

    # Define the "sync" subcommand
    sync_parser = subparsers.add_parser('sync', help='Sync something')
    sync_parser.add_argument('--sobject','--sobj', type=str, required=True, help='The Salesforce sobject to create')
    sync_parser.add_argument('--table', '--t', type=str, required=True, help='The name of the table to create')
    sync_parser.add_argument('--sync_field', '--field', type=str, required=True, help='The the sync field to match against')
    sync_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection')
    sync_parser.add_argument('--lastmodifieddate', '--lmd', type=str, required=False, help='The date and time for the most recent record after which records will be synchronized.  The format is YYYY-MM-DD HH:MM:SS')

    login_parser = subparsers.add_parser('login', help='Sync something')
 
    # Parse the arguments
    args = parser.parse_args()

    # Handle the subcommands
    if args.command == 'create':
        #print(f"Creating user with username: {args.username}")
        print(f"sObject: {args.sobject}")
        print(f"Table: {args.table}")
        print(f"{args.db_connect}")
        sobject_create.create(snowflake_connection(f"{args.db_connect}"), f"{args.sobject}", f"{args.table}")
    elif args.command == 'sync':
        #print(f"Syncing user with username: {args.username}")
        #print(f"Sync interval: {args.interval} minutes")
        sobject_sync.new_changed_records(snowflake_connection(f"{args.db_connect}"), f"{args.sobject}", f"{args.table}",f"{args.sync_field}",f"{args.lastmodifieddate}" )
    elif args.command == 'login':
        sf_login.authenticate()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()