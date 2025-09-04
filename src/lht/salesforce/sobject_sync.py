import pandas as pd
from . import sobjects as sobj, sobject_query as sobj_query
from lht.util import merge, data_writer as dw

def new_changed_records(session, access_info, sobject, local_table, match_field, lmd=None):

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
    session.sql("CREATE or REPLACE TEMPORARY TABLE {} LIKE {}""".format(tmp_table,local_table)).collect()

    #get the columns from the local table.  There may be fields that are not in the local table
    #and the salesforce sync will need to skip them
    results = session.sql("SHOW COLUMNS IN TABLE TMP_{}".format(local_table)).collect()
    table_fields = []
    for field in results:
        try:
            table_fields.append(field[2]) 
        except:
            print("field {} not present.  Skipping".format(field[2]))
            continue
 
    #method returns the salesforce sobject query and the fields from the sobject
    query, df_fields, snowflake_fields = sobj.describe(access_info, sobject, lmd_sf)

    sobject_data = sobj_query.query_records(access_info, query)
    data_list = list(sobject_data)  # Convert generator to list
    print(f"OBJECT DATA: Got {len(data_list)} batches")
    for i, batch_df in enumerate(data_list):
        df_str = batch_df.astype(str)
        batch_df = None
        print(f"📊 Processing first batch of data")
        session.write_pandas(df_str, table_name="tmp_"+local_table, auto_create_table=True, overwrite=True, table_type="temporary", quote_identifiers=False)
        df_str = None
        transformed_data = merge.transform_and_match_datatypes(session, "tmp_"+local_table, local_table)
        
        session.sql(f"Insert into {local_table} select {transformed_data} from tmp_{local_table}").collect()

    #merge.format_filter_condition(session, tmp_table, local_table,match_field, match_field)
    return query