# args.py
import argparse

def retl_bulk_args(retl_parser):
    #retl_parser = argparse.ArgumentParser()
    #retl_parser = subparsers.add_parser('retl', help='Reverse ETL data into Salesforce')
    retl_parser.add_argument('--sobject', '--sobj', type=str, required=True, help='The name of the table to create')
    retl_parser.add_argument('--query', '--q',help='the file that holds the query')
    retl_parser.add_argument('--field', '--f', required=True, help='the table to load the data into')
    retl_parser.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    retl_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection') 
    retl_parser.add_argument('--instance_type','--instance', type=int, required=True, help='Salesforce Instance Type:  1 = Productio; 0 = Sandbox')
    return retl_parser  #.parse_args()

def retl_bulk_insert_args(retl_parser):
    retl_parser.add_argument('--sobject', '--sobj', type=str, required=True, help='The name of the table to create')
    retl_parser.add_argument('--query', '--q',help='the file that holds the query')
    retl_parser.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    retl_parser.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection') 
    retl_parser.add_argument('--instance_type','--instance', type=int, required=True, help='Salesforce Instance Type:  1 = Productio; 0 = Sandbox')
    return retl_parser  #.parse_args()

def retl_delete_args(retl_del):
    #retl_parser = argparse.ArgumentParser()
    #retl_parser = subparsers.add_parser('retl', help='Reverse ETL data into Salesforce')
    retl_del.add_argument('--sobject', '--sobj', type=str, required=True, help='The name of the table to create')
    retl_del.add_argument('--query', '--q',help='the file that holds the query')
    retl_del.add_argument('--field', '--f', help='the field to match the data against')
    retl_del.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    retl_del.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection') 
    retl_del.add_argument('--instance_type','--instance', type=int, required=True, help='Salesforce Instance Type:  1 = Productio; 0 = Sandbox')    
    return retl_del  #.parse_args()