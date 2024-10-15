
import toml
#from salesforce import sobject_create
from salesforce import sobject_create, sobject_sync, query_bapi20 as bapi20
from util import soql_query as soql
from snowflake.snowpark import Session
from user import auth
import argparse
#from user import salesforce_login as sf_login
import json

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
    create_parser = subparsers.add_parser('create', help='Create a table based on a Salesforce sobject')
    create_parser.add_argument('--sobject','--sobj', type=str, required=True, help='The Salesforce sobject to create')
    create_parser.add_argument('--table', '--t', type=str, required=True, help='The name of the table to create')
    create_parser.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    create_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection')

    # Define the "sync" subcommand
    sync_parser = subparsers.add_parser('sync', help='Sync something')
    sync_parser.add_argument('--sobject','--sobj', type=str, required=True, help='This command synchronizes Salesforce sobjects with a table is Snowflake. Ideal for tables that are not bulk enabled or for frequent synchronization jobs')
    sync_parser.add_argument('--table', '--t', type=str, required=True, help='The name of the table to create')
    sync_parser.add_argument('--sync_field', '--field', type=str, required=True, help='The the sync field to match against')
    sync_parser.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    sync_parser.add_argument('--db_connect','--db', type=str, required=True, help='The Snowflake database connection')
    sync_parser.add_argument('--lastmodifieddate', '--lmd', type=str, required=False, help='The date and time for the most recent record after which records will be synchronized.  The format is YYYY-MM-DD HH:MM:SS')

    #   Define the "bulk query 2.0" subcommand
    bulk_query_parser = subparsers.add_parser('query', help='Bulk query an sobject')
    bulk_query_parser.add_argument('--bapi20','--b20', required=True, action='store_true', help='The Salesforce sobject to create')
    bulk_query_parser.add_argument('--sobject', '--sobj', type=str, required=True, help='The name of the table to create')
    bulk_query_parser.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    bulk_query_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection')

    bulk_status_parser = subparsers.add_parser('bulk_status', help='Get the status of bulk jobs')
    bulk_status_parser.add_argument('--job_id','--id', help='Get the status of a job.  If omitted, it will return the status of all jobs')
    bulk_status_parser.add_argument('--job_type','--type', required=False, help='Filter by the type of job. Options are Classic, V2Ingest, V2Query.  If blank, will return all')
    bulk_status_parser.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    bulk_status_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection')
    #job types include:
    #BigObjectIngest: BigObjects job
    #Classic: Bulk API 1.0 job
    #V2Ingest: Bulk API 2.0 job
    #V2Query—Bulk API 2.0 query jobs.

    bulk_results_parser = subparsers.add_parser('bulk_results', help='Get the files from a bulk job')
    bulk_results_parser.add_argument('--job_id','--id', help='Get the status of a job.  If omitted, it will return the status of all jobs')
    bulk_results_parser.add_argument('--sobject', '--sobj', type=str, required=True, help='The name of the table to create')
    bulk_results_parser.add_argument('--schema',help='schema')
    bulk_results_parser.add_argument('--table', help='the table to load the data into')
    bulk_results_parser.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    bulk_results_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection')

    subparsers.add_parser('login', help='Sync something')

    sfdc_info = 'radnet_salesforce_sandbox'
    #sandbox is radnet_salesforce_sandbox
    #prod is salesforce_prod]
 
    # Parse the arguments
    args = parser.parse_args()

    # Handle the subcommands
    if args.command == 'create':
        session = snowflake_connection(f"{args.db_connect}")
        # access_token = auth.get_access_token()
        sobject_create.create(session,auth.get_salesforce_token(session,sfdc_info, f"{args.username}"), f"{args.sobject}", f"{args.table}")
    elif args.command == 'sync':
        session = snowflake_connection(f"{args.db_connect}")
        if args.lastmodifieddate is None:
            sobject_sync.new_changed_records(session, auth.get_salesforce_token(session,sfdc_info, f"{args.username}"), f"{args.sobject}", f"{args.table}",f"{args.sync_field}")
        else:
            sobject_sync.new_changed_records(session, auth.get_salesforce_token(session,sfdc_info, f"{args.username}"), f"{args.sobject}", f"{args.table}",f"{args.sync_field}",f"{args.lastmodifieddate}" )
    elif args.command == 'query':
        #access_token = auth.get_access_token()
        session = snowflake_connection(f"{args.db_connect}")
        access_token = auth.get_salesforce_token(session,sfdc_info, f"{args.username}")
        query = soql.build_soql(session,access_token, f"{args.sobject}")
        bapi20_request = bapi20.create_batch_query(access_token, query)
        print(bapi20_request)
    elif args.command == 'bulk_results':
        #access_token = auth.get_access_token()
        session = snowflake_connection(f"{args.db_connect}")
        bapi20.get_bulk_results(session, auth.get_salesforce_token(session,sfdc_info, f"{args.username}"),  f"{args.job_id}",  f"{args.sobject}", f"{args.schema}", f"{args.table}")

    elif args.command == 'bulk_status':
        #access_token = auth.get_access_token()
        session = snowflake_connection(f"{args.db_connect}")
        if args.job_type == 'None':
            job_type = None
        else:
            job_type = args.job_type
        bapi20_info = bapi20.query_status(auth.get_salesforce_token(session,sfdc_info, f"{args.username}"), job_type, f"{args.job_id}")
        print(bapi20_info)
    elif args.command == 'login':
        sf_login.authenticate()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()