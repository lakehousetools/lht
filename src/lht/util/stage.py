import io
import os
import pandas as pd

def put_file(session, stage, file, filename=None):
    # Create an in-memory file object
    file_obj = io.BytesIO(file)

    # Create a temporary file in the filesystem and upload it
    import tempfile
    import shutil

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        shutil.copyfileobj(file_obj, temp_file)
        temp_file_path = temp_file.name

    # Use Snowflake's PUT command to upload the temporary file to the stage
    if filename:
        put_command = f"PUT file://{temp_file_path} @{stage}/{filename}"
    else:
        put_command = f"PUT file://{temp_file_path} @{stage}"

    # Use the correct Snowflake session method
    try:
        # Use Snowpark's sql().collect() method
        session.sql(put_command).collect()
    except Exception as e:
        raise Exception(f"Failed to execute PUT command: {put_command}. Error: {e}")

    # Clean up temporary file
    os.remove(temp_file_path)

    # Note: Removed session.close() to allow reuse of session for multiple operations

def put_dataframe_to_stage(session, stage_name, df, filename=None, schema=None):
    """
    Write a DataFrame directly to a Snowflake stage without using temporary files.
    This is designed for notebook environments where ephemeral storage is not reliable.
    
    Args:
        session: Snowflake Snowpark session
        stage_name: Name of the Snowflake stage (without @ symbol)
        df: pandas DataFrame to write
        filename: Optional filename for the stage file
        schema: Optional schema name for temporary table creation
    
    Returns:
        str: The filename that was written to the stage
    """
    if filename is None:
        import uuid
        filename = f"data_{uuid.uuid4().hex[:8]}.csv"
    
    # Convert DataFrame to CSV string with proper data type handling
    # Convert all columns to string to avoid type conversion issues
    df_string = df.astype(str)
    csv_buffer = io.StringIO()
    df_string.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    
    # Create a Snowflake DataFrame from the CSV content
    # We'll use a temporary table approach to get the data into the stage
    temp_table_name = f"TEMP_{filename.replace('.csv', '').replace('-', '_')}"
    
    # Get current database for fully qualified table name
    current_db = session.sql('SELECT CURRENT_DATABASE()').collect()[0][0]
    
    # Use schema if provided, otherwise use current schema
    if schema:
        full_temp_table_name = f"{current_db}.{schema}.{temp_table_name}"
    else:
        full_temp_table_name = f"{current_db}.{temp_table_name}"
    
    try:
        # Write DataFrame to a temporary table using centralized data_writer
        from . import data_writer
        data_writer.write_dataframe_to_table(
            session=session,
            df=df,
            schema=schema if schema else "PUBLIC",
            table=temp_table_name,
            auto_create=True,
            overwrite=True,
            use_logical_type=True,
            on_error="CONTINUE"
        )
        
        # Copy from temporary table to stage
        copy_command = f"""
        COPY INTO @{stage_name}/{filename}
        FROM {full_temp_table_name}
        FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER = ',' FIELD_OPTIONALLY_ENCLOSED_BY = '"' 
                      NULL_IF = ('NULL', 'null') EMPTY_FIELD_AS_NULL = TRUE)
        HEADER = TRUE
        OVERWRITE = TRUE
        """
        
        session.sql(copy_command).collect()
        
        # Clean up temporary table
        session.sql(f"DROP TABLE IF EXISTS {full_temp_table_name}").collect()
        
        return filename
        
    except Exception as e:
        # Clean up temporary table on error
        try:
            session.sql(f"DROP TABLE IF EXISTS {full_temp_table_name}").collect()
        except:
            pass
        raise Exception(f"Failed to write DataFrame to stage {stage_name}: {e}")

def put_csv_content_to_stage(session, stage_name, csv_content, filename=None, schema=None):
    """
    Write CSV content directly to a Snowflake stage without using temporary files.
    This is designed for notebook environments where ephemeral storage is not reliable.
    
    Args:
        session: Snowflake Snowpark session
        stage_name: Name of the Snowflake stage (without @ symbol)
        csv_content: String containing CSV data
        filename: Optional filename for the stage file
        schema: Optional schema name for temporary table creation
    
    Returns:
        str: The filename that was written to the stage
    """
    if filename is None:
        import uuid
        filename = f"data_{uuid.uuid4().hex[:8]}.csv"
    
    # Convert CSV string to DataFrame with proper data type handling
    csv_buffer = io.StringIO(csv_content)
    df = pd.read_csv(csv_buffer, low_memory=False, dtype=str)
    
    # Use the DataFrame method to write to stage
    return put_dataframe_to_stage(session, stage_name, df, filename, schema)