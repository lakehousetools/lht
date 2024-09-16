import os
from . import sobjects as sobj
import json

def create(session, access_info, sobject, local_table):
    #current_dir = os.path.dirname(os.path.abspath(__file__))
    #creds_path = os.path.join(current_dir, '..', '.snowflake', 'token.json')

    #with open(creds_path, 'r') as file:
    #    file_str = file.read()
    #access_info = file_str.replace("'", '"')
    query, fields, snowflake_fields = sobj.describe(session, access_info, sobject)

    print("\n\FIELDS {}".format(fields.keys()))
    #print("\n\SNOWFLAKE FIELDS {}".format(snowflake_fields))
    query = "CREATE OR REPLACE TABLE {} ({})".format(local_table, snowflake_fields)
    session.sql(query).collect()