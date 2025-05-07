import os
from . import sobjects as sobj

def create(session, access_info, sobject, local_table):
    query, fields, snowflake_fields = sobj.describe(session, access_info, sobject)

    #print("\n\FIELDS {}".format(fields.keys()))

    query = "CREATE OR REPLACE TABLE {} ({})".format(local_table, snowflake_fields)
    session.sql(query).collect()