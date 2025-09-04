from snowflake.snowpark import Session
from snowflake.snowpark import functions as F

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

#method to transform temp table and match datatypes with permanent table
def transform_and_match_datatypes(session, temp_table, permanent_table, temp_schema=None, perm_schema=None):
  """
  Transform data types in temp table to match permanent table schema.

  Args:
      session: Snowpark session
      temp_table: Name of temporary table
      permanent_table: Name of permanent table  
      temp_schema: Schema of temp table (optional)
      perm_schema: Schema of permanent table (optional)

  Returns:
      Snowpark DataFrame with transformed data types
  """


  fields = ""
  # Get schema info for both tables
  temp_schema_info = session.sql(f"DESCRIBE TABLE {temp_table}").collect()

  perm_schema_info = session.sql(f"DESCRIBE TABLE {permanent_table}").collect()

  # Create mapping of column name to data type for permanent table
  perm_types = {row['name'].upper(): row['type'] for row in perm_schema_info}
  temp_types = {row['name'].upper(): row['type'] for row in temp_schema_info}

  for row in perm_schema_info:
      col_name = row['name'].upper()
      
      if col_name in temp_types:
          temp_type = temp_types[col_name]
          perm_type = perm_types[col_name]
      
          # If types don't match, add cast
          if temp_type != perm_type:
              # Handle common type conversions
              if 'VARCHAR' in perm_type or 'STRING' in perm_type:
                  expr = f"CASE WHEN TRIM({col_name}) = 'nan' THEN NULL ELSE CAST({col_name} AS {perm_type}) END as {col_name},\n"
              elif 'NUMBER' in perm_type or 'DECIMAL' in perm_type or 'FLOAT' in perm_type:
                  expr = f"CASE WHEN {col_name} ='nan' THEN NULL when trim({col_name}) = '' then NULL ELSE {col_name}::NUMBER END as {col_name},\n" 

              elif 'INTEGER' in perm_type or 'BIGINT' in perm_type:
                  expr = f"CASE WHEN {col_name} ='nan'  then NULL when {col_name} = '' then NULL ELSE {col_name}::NUMBER END as {col_name},\n" 
              elif 'TIMESTAMP' in perm_type or 'TIMESTAMP_NTZ' in perm_type:
                #expr = f"CASE WHEN {col_name} ='nan' then NULL when {col_name} = '' then NULL ELSE TO_TIMESTAMP_NTZ(REPLACE({col_name}, 'Z', ''), 'YYYY-MM-DD\"T\"HH24:MI:SS.FF3') END as {col_name},\n"
                expr = f"""CASE 
                    WHEN {col_name} = 'nan' THEN NULL 
                    WHEN {col_name} = '' THEN NULL 
                    ELSE 
                        TO_TIMESTAMP_NTZ(left({col_name},19), 'YYYY-MM-DD\"T\"HH24:MI:SS')
                END as {col_name},\n"""
              elif 'DATE' in perm_type:
                  expr = f"CASE WHEN {col_name} ='nan' then NULL when {col_name} = '' then NULL ELSE TO_DATE(SUBSTR({col_name}, 1, 10), 'YYYY-MM-DD') END as {col_name},\n"
          
              elif 'BOOLEAN' in perm_type:
                  expr = f"{col_name}::boolean AS {col_name},\n"
          
              fields = fields + expr
          else:
              fields = fields + f"CASE WHEN TRIM({col_name}) = 'nan' then NULL when {col_name} = '' THEN NULL ELSE CAST({col_name} AS {perm_type}) END as {col_name},\n"
      else:
          fields = fields + 'Null as ' + col_name+",\n"
  return fields