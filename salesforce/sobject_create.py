import os
from . import sobjects as sobj
import json

def create(session,sobject, local_table):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(current_dir, '..', '.snowflake', 'token.json')

    with open(creds_path, 'r') as file:
        file_str = file.read()
    access_info = file_str.replace("'", '"')
    query, fields, snowflake_fields = sobj.describe(session, json.loads(access_info), sobject)
    query = "CREATE OR REPLACE TABLE {} ({})".format(local_table, snowflake_fields)
    session.sql(query).collect()