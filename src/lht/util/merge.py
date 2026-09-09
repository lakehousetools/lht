from snowflake.snowpark import Session
from snowflake.snowpark import functions as F
import logging

logger = logging.getLogger(__name__)

def merge_into_target(session, temp_table, target_table, match_field):
    """
    Merge casted rows from temp_table into target_table, keyed on match_field.

    Rows whose match_field value already exists in target_table are updated in
    place; rows that don't are inserted. This is what keeps a sync from
    appending a duplicate row every time a record it has already loaded shows
    up again (e.g. re-synced because it changed in Salesforce).

    All identifiers are assumed uppercase and are never quoted, so they match
    however the target table's columns were actually created.
    """
    match_field = match_field.upper()

    # Casted, aliased SELECT list against temp_table, one expression per
    # target column - this is what makes the merge tolerant of temp_table
    # loading everything as strings (see get_bulk_results_direct).
    casted_columns = transform_and_match_datatypes(session, temp_table, target_table)
    casted_columns = casted_columns.strip().rstrip(',')

    target_schema_info = session.sql(f"DESCRIBE TABLE {target_table}").collect()
    target_columns = [row['name'].upper() for row in target_schema_info]

    if match_field not in target_columns:
        raise ValueError(f"match_field '{match_field}' is not a column of {target_table}")

    update_set = ",\n    ".join(f"{col} = src.{col}" for col in target_columns if col != match_field)
    insert_cols = ", ".join(target_columns)
    insert_vals = ", ".join(f"src.{col}" for col in target_columns)

    merge_sql = f"""
MERGE INTO {target_table} tgt
USING (SELECT {casted_columns} FROM {temp_table}) src
ON tgt.{match_field} = src.{match_field}
WHEN MATCHED THEN UPDATE SET
    {update_set}
WHEN NOT MATCHED THEN INSERT ({insert_cols})
VALUES ({insert_vals})
"""
    logger.debug(f"🔍 Executing merge into {target_table} on {match_field}:\n{merge_sql}")
    return session.sql(merge_sql).collect()

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
                  expr = f"CASE WHEN {col_name} ='nan' THEN NULL when trim({col_name}) = '' then NULL ELSE {col_name} END as {col_name},\n" 

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