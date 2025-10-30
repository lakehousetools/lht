import pandas as pd
import logging
from . import sobjects as sobj, sobject_query as sobj_query
from lht.util import merge, data_writer as dw

logger = logging.getLogger(__name__)

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
    # Temporary table will be created by data_writer.write_batch_to_temp_table()

 
    #method returns the salesforce sobject query and the fields from the sobject
    query, df_fields, snowflake_fields = sobj.describe(access_info, sobject, lmd_sf)

    sobject_data = sobj_query.query_records(access_info, query)
    
    data_list = list(sobject_data)  # Convert generator to list of DataFrames
    logger.info(f"Processing {len(data_list)} batches")
    for i, batch_df in enumerate(data_list):
        logger.debug(f"📊 Processing batch {i+1} of data")
        
        # DEBUG: Check the DataFrame structure before writing
        logger.debug(f"🔍 DEBUG: batch_df type: {type(batch_df)}, shape: {batch_df.shape if isinstance(batch_df, pd.DataFrame) else 'N/A'}")
        
        if not isinstance(batch_df, pd.DataFrame):
            logger.error(f"❌ batch_df is not a DataFrame! Type: {type(batch_df)}")
            continue
        
        # Write to temp table using data_writer (handles null values properly)
        # Let the session handle schema context - don't override it
        sd = batch_df.head(1).to_dict()
        logger.error(f"   here is the batch_df data: {str(sd)[:500]}")
        dw.write_batch_to_temp_table(
            session=session,
            df=batch_df,  # Use original DataFrame, not string version
            schema=None,  # Let session use current schema context
            temp_table=tmp_table,  # Use the tmp_table variable (TMP_ prefix)
            df_fields=df_fields,
            validate_types=True,
            main_table=local_table,
            snowflake_fields=snowflake_fields  # Add missing snowflake_fields parameter
        )
        logger.debug(f"📊 data written to temporary table")
        transformed_data = merge.transform_and_match_datatypes(session, tmp_table, local_table)
        
        # INCREMENTAL SYNC: Use MERGE logic instead of INSERT
        logger.info("🔄 Performing incremental sync with MERGE logic")
        #merge_condition = merge.format_filter_condition(session, tmp_table, local_table, match_field, match_field)
        #merge_statement = merge.format_insert_upsert(session, tmp_table, local_table, merge_condition)
        merge_statement = merge.format_filter_condition(session, tmp_table, local_table, match_field, match_field)
        
        # DEBUG: Print the merge statement before execution
        logger.info("🔍 MERGE STATEMENT TO BE EXECUTED:")
        logger.info("=" * 80)
        logger.info(merge_statement)
        logger.info("=" * 80)
        
        session.sql(merge_statement).collect()
        logger.info(f"✅ Batch {i+1} merged successfully")

    #merge.format_filter_condition(session, tmp_table, local_table,match_field, match_field)
    return query