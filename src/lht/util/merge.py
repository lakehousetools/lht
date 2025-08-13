from snowflake.snowpark import Session

def format_filter_condition(snowpark_session, src_table, tgt_table,src_filter, tgt_filter):
  filter_cond = list()
  split_src = src_filter.split(',')
  split_tgt = tgt_filter.split(',')
  
  # -- Check Both source and targer filter condition are same length
  # -- Note : Filter condition order matters here:
  if len(split_src) == len(split_tgt):
    for i in range(len(split_src)):
        #print(i)
        filter_cond.append('src.'+ '"' + split_src[i]+ '"' + '= tgt.'+ '"' +split_tgt[i]+ '"')
  else:
    return "Error"
  
  s_filter_cond = " AND ".join(filter_cond)
  
  # -- Call the function to generate the merge statement
  s_merge_stament = format_insert_upsert(snowpark_session, src_table, tgt_table, s_filter_cond)
  
  # -- Execute the Merge Statement
  s_final_result = ""
  #if s_merge_stament.upper() != 'ERROR':
  if s_merge_stament != 'Error':
    #print("\n\n@@@ {}".format(s_merge_stament))
    src_table_col = snowpark_session.sql(s_merge_stament).collect()
    s_final_result = "Number of Rows Inserted: {0} Updated:{1}".format(str(src_table_col[0][0]), str(src_table_col[0][1]))
    
  else:
    print("error")
    s_final_result = "Error"
  
  return s_final_result;
 
def format_insert_upsert(snowpark_session, src_table, tgt_table, s_filter_cond):
    """
        Function query the snowflake metadata and generate the Merge
    """
    sel_colum = list()
    update_col = list()
    insert_sel = list()
    insert_val = list()
    # Get current database and schema for proper table references
    current_db = snowpark_session.sql("SELECT CURRENT_DATABASE()").collect()[0][0]
    schema_name = snowpark_session.get_current_schema().replace('"','')
    
    # Use fully qualified table names for temporary table queries
    src_table_col = snowpark_session.sql("select COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{0}' AND TABLE_SCHEMA = \'{1}\' ORDER BY ORDINAL_POSITION".format(src_table, schema_name)).collect()
    tgt_table_col = snowpark_session.sql("select COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{0}' AND TABLE_SCHEMA = \'{1}\' ORDER BY ORDINAL_POSITION".format(tgt_table, schema_name)).collect()

    if len(src_table_col) != 0:
        for idx_value in range(len(src_table_col)):
            sel_colum.append('"'+src_table_col[idx_value][0]+'"')
            insert_val.append("src." + '"' + str(src_table_col[idx_value][0]) + '"')
            insert_sel.append("tgt." + '"' + str(tgt_table_col[idx_value][0]) + '"')
            update_col.append("tgt." + '"' + str(tgt_table_col[idx_value][0]) + '"' + ' = ' + "src." + '"' + str(src_table_col[idx_value][0]) + '"')

        s_merge_stmt = """
                    MERGE INTO
                       {0} tgt
                    USING
                        (SELECT {1} FROM {2}) src
                    ON
                        {3}
                    WHEN MATCHED THEN UPDATE SET
                        {4}
                    WHEN NOT MATCHED THEN INSERT
                         ({5})
                    VALUES
                        ({6})
                """.format(
                    tgt_table,
                    ",".join(sel_colum),
                    src_table,
                    s_filter_cond,
                    ",".join(update_col),
                    ",".join(insert_sel),
                    ",".join(insert_val)
                )   
    else:
        return "Error"
    return s_merge_stmt