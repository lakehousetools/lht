import pandas as pd
from . import sobjects as sobj, sobject_query as sobj_query
import os
import json
from util import merge

def new_changed_records(session, access_info, sobject, local_table, match_field, lmd=None):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(current_dir, '..', '.snowflake', 'token.json')

    """with open(creds_path, 'r') as file:
        file_str = file.read()
    access_info1 = file_str.replace("'", '"')
    access_info = json.loads(access_info1)
    print(type(access_info))"""

    if lmd is None:
        #get the most recent last modified date
        local_query = """Select max(LastModifiedDate::timestamp_ntz) as LastModifiedDate from {}""".format(local_table)

        results_df = session.sql(local_query).collect()
        lmd = pd.to_datetime(results_df[0]['LASTMODIFIEDDATE'])

    if lmd is not None:
        lmd_sf = str(pd.to_datetime(lmd))[:10]+'T'+str(pd.to_datetime(lmd))[11:19]+'.000z'
    else:
        lmd_sf = None
    tmp_table = 'TMP_{}'.format(local_table)
    session.sql("CREATE or REPLACE TABLE {} LIKE {}""".format(tmp_table,local_table)).collect()

    #get the columns from the local table.  There may be fields that are not in the local table
    #and the salesforce sync will need to skip them
    results = session.sql("SHOW COLUMNS IN TABLE TMP_{}".format(local_table)).collect()
    table_fields = []
    for field in results:
        table_fields.append(field[2]) 
 
    query, df_fields, create_table_fields = sobj.describe(session, access_info, sobject, lmd_sf)
    #print(query)

    sobj_query.query_records(session, access_info, query, sobject, local_table, df_fields, table_fields)

    merge.format_filter_condition(session, tmp_table, local_table,match_field, match_field)
    return query

