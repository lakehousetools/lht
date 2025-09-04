"""
Centralized table creation utility for Salesforce sync operations.
This module consolidates table creation logic that was previously duplicated
across multiple sync functions.
"""

import logging
from typing import Dict, Optional
from snowflake.snowpark import Session

logger = logging.getLogger(__name__)

def create_salesforce_table(
    session: Session,
    schema: str,
    table: str,
    snowflake_fields: Dict[str, str],
    force_full_sync: bool = False,
    database: Optional[str] = None
) -> bool:
    """
    Create a Snowflake table with the correct schema for Salesforce data.
    
    Args:
        session: Snowflake Snowpark session
        schema: Target schema name
        table: Target table name
        snowflake_fields: Dictionary mapping field names to Snowflake types
        force_full_sync: Whether to force table recreation (uses CREATE OR REPLACE)
        database: Target database name (auto-detected if not provided)
        
    Returns:
        bool: True if table was created successfully or already exists
        
    Raises:
        Exception: If table creation fails
    """
    try:
        print(f"🔍 create_salesforce_table called with force_full_sync={force_full_sync}")
        print(f"🔍 force_full_sync type: {type(force_full_sync)}")
        print(f"🔍 force_full_sync value: {repr(force_full_sync)}")
        
        # Auto-detect database if not provided
        if database is None:
            database = session.sql('SELECT CURRENT_DATABASE()').collect()[0][0]
            logger.debug(f"Auto-detected database: {database}")
        
        # Set the current database and schema context
        session.sql(f"USE DATABASE {database}").collect()
        session.sql(f"USE SCHEMA {schema}").collect()
        
        # Check if table already exists
        try:
            print(f"🔍 Checking if table {schema}.{table} exists...")
            print(f"🔍 force_full_sync parameter = {force_full_sync}")
            print(f"🔍 force_full_sync type = {type(force_full_sync)}")
            
            table_check = session.sql(f'SHOW TABLES IN SCHEMA "{schema}"').collect()
            print(f"🔍 Raw table_check result: {table_check}")
            table_names = [row['name'] for row in table_check]
            print(f"🔍 Tables in schema: {table_names}")
            print(f"🔍 Looking for table: {table}")
            print(f"🔍 Table exists: {table in table_names}")
            print(f"🔍 Table names types: {[type(name).__name__ for name in table_names]}")
            print(f"🔍 Target table type: {type(table).__name__}")
            
            if table in table_names:
                print(f"🔍 Table {table} EXISTS in schema {schema}")
                if force_full_sync:
                    print(f"🔍 force_full_sync is TRUE - will recreate table")
                    logger.info(f"Table {schema}.{table} exists and force_full_sync=True, recreating it...")
                    # Drop existing table first
                    print(f"🗑️ Dropping existing table {schema}.{table}...")
                    session.sql(f"DROP TABLE IF EXISTS {schema}.{table}").collect()
                    print(f"✅ Dropped existing table {schema}.{table}")
                    logger.info(f"Dropped existing table {schema}.{table}")
                else:
                    print(f"🔍 force_full_sync is FALSE - skipping table creation")
                    logger.info(f"Table {schema}.{table} already exists, skipping creation")
                    return True
            else:
                print(f"🔍 Table {table} does NOT exist in schema {schema}")
            
            # Create table with correct schema (either new or after dropping)
            logger.info(f"Creating table {schema}.{table}...")
            create_table_sql = _build_create_table_sql(schema, table, snowflake_fields, force_full_sync)
            
            # Make CREATE TABLE SQL highly visible
            print(f"\n{'='*80}")
            print(f"🔧 CREATING TABLE: {schema}.{table}")
            print(f"🔧 FORCE_FULL_SYNC: {force_full_sync}")
            print(f"{'='*80}")
            
            result = session.sql(create_table_sql).collect()
            logger.info(f"Table created successfully with correct schema")
            return True
                
        except Exception as table_check_error:
            logger.warning(f"Error checking/creating table: {table_check_error}")
            logger.info(f"Falling back to auto-created table, then recreating with correct schema")
            
            # Fallback: create table with write_pandas, then drop and recreate with correct schema
            try:
                # This is a temporary DataFrame just for table creation
                import pandas as pd
                temp_df = pd.DataFrame({field: [] for field in snowflake_fields.keys()})
                
                # Create table with auto_create_table=True using centralized data_writer
                from . import data_writer
                data_writer.write_dataframe_to_table(
                    session=session,
                    df=temp_df,
                    schema=schema,
                    table=table,
                    auto_create=True,
                    overwrite=False,
                    use_logical_type=False,
                    on_error="CONTINUE"
                )
                logger.info(f"Auto-created table {schema}.{table}")
                
                # Now drop it and recreate with correct schema
                logger.info(f"Dropping auto-created table to recreate with correct schema...")
                session.sql(f"DROP TABLE IF EXISTS {schema}.{table}").collect()
                
                # Create table with correct schema
                create_table_sql = _build_create_table_sql(schema, table, snowflake_fields, force_full_sync)
                
                # Make CREATE TABLE SQL highly visible (fallback path)
                print(f"\n{'='*80}")
                print(f"🔧 FORCE_FULL_SYNC: {force_full_sync}")
                print(f"{'='*80}")
                print(f"{'='*80}")
                
                result = session.sql(create_table_sql).collect()
                logger.info(f"Table recreated with correct schema")
                return True
                
            except Exception as fallback_error:
                logger.error(f"Fallback table creation also failed: {fallback_error}")
                raise Exception(f"Failed to create table {schema}.{table} even with fallback: {fallback_error}")
                
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        raise Exception(f"Failed to create table {schema}.{table}: {e}")


def _build_create_table_sql(schema: str, table: str, snowflake_fields: Dict[str, str], force_full_sync: bool = False) -> str:
    """
    Build CREATE TABLE SQL statement based on Salesforce field definitions.
    
    Args:
        schema: Snowflake schema name
        table: Snowflake table name
        snowflake_fields: Dictionary mapping field names to Snowflake types
        force_full_sync: Whether to force table recreation
        
    Returns:
        str: CREATE TABLE SQL statement
    """
    # Build column definitions
    columns = []
    for field_name, snowflake_type in snowflake_fields.items():
        # Convert field name to uppercase to match DataFrame
        field_upper = field_name.upper()
        
        # Use the Snowflake type directly (already mapped from Salesforce field types)
        columns.append(f'"{field_upper}" {snowflake_type}')
    
    # Build CREATE TABLE statement
    column_defs = ',\n\t'.join(columns)
    # Always use CREATE TABLE (not CREATE OR REPLACE) since we handle DROP separately
    create_sql = f"""CREATE TABLE "{schema}"."{table}" (
	{column_defs}
)"""
    
    return create_sql


def ensure_table_exists_for_dataframe(
    session: Session,
    schema: str,
    table: str,
    df_fields: Dict[str, str],
    snowflake_fields: Dict[str, str],
    force_full_sync: bool = False,
    database: Optional[str] = None
) -> bool:
    """
    Ensure a table exists with the correct schema for a DataFrame.
    This is a convenience function that handles the common case of
    creating tables for Salesforce sync operations.
    
    Args:
        session: Snowflake Snowpark session
        schema: Target schema name
        table: Target table name
        df_fields: Dictionary of field names from the DataFrame
        snowflake_fields: Dictionary mapping field names to Snowflake types
        force_full_sync: Whether to force table recreation
        database: Target database name (auto-detected if not provided)
        
    Returns:
        bool: True if table is ready for data insertion
        
    Raises:
        Exception: If table creation fails
    """
    try:
        # Ensure table exists for DataFrame
        
        # Filter snowflake_fields to only include fields we're actually using
        missing_in_snowflake = [k for k in df_fields.keys() if k not in snowflake_fields]
        if missing_in_snowflake:
            logger.warning(f"Fields missing from snowflake_fields: {missing_in_snowflake}")
        
        filtered_snowflake_fields = {k: snowflake_fields.get(k, 'VARCHAR(16777216)') for k in df_fields.keys()}
        
        # Create the table
        print(f"🚀 Calling create_salesforce_table with force_full_sync={force_full_sync}")
        return create_salesforce_table(
            session=session,
            schema=schema,
            table=table,
            snowflake_fields=filtered_snowflake_fields,
            force_full_sync=force_full_sync,
            database=database
        )
        
    except Exception as e:
        logger.error(f"Failed to ensure table exists: {e}")
        raise
