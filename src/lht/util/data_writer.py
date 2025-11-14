import logging
from typing import Optional, Dict, Any
from snowflake.snowpark import Session
from snowflake.snowpark.dataframe import DataFrame
import pandas as pd
import numpy as np
from . import table_creator

logger = logging.getLogger(__name__)

def validate_dataframe_types(df: pd.DataFrame, expected_types: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Validate DataFrame data types and identify potential casting issues.
    
    Args:
        df: DataFrame to validate
        expected_types: Optional dict of column_name: expected_type pairs
        
    Returns:
        Dict containing validation results and recommendations
    """
    validation_result = {
        'is_valid': True,
        'issues': [],
        'recommendations': [],
        'column_analysis': {}
    }
    
    for column in df.columns:
        col_data = df[column]
        col_analysis = {
            'dtype': str(col_data.dtype),
            'null_count': col_data.isnull().sum(),
            'unique_count': col_data.nunique(),
            'sample_values': col_data.dropna().head(5).tolist(),
            'mixed_types': False,
            'potential_issues': []
        }
        
        # Check for mixed types in the column
        if col_data.dtype == 'object':
            # Check if object column contains mixed types
            non_null_values = col_data.dropna()
            if len(non_null_values) > 0:
                # Check if all values can be converted to the same type
                try:
                    # Try to convert to numeric
                    pd.to_numeric(non_null_values, errors='raise')
                    col_analysis['potential_issues'].append("Object column contains numeric data - consider converting to numeric type")
                except (ValueError, TypeError):
                    # Check if all values are strings
                    if not all(isinstance(x, str) for x in non_null_values):
                        col_analysis['mixed_types'] = True
                        col_analysis['potential_issues'].append("Mixed data types detected - may cause Snowflake casting issues")
        
        # Check for specific problematic patterns
        if col_data.dtype == 'object':
            # Look for numeric strings that might cause casting issues
            numeric_strings = 0
            total_non_null = len(col_data.dropna())
            
            for value in col_data.dropna():
                if isinstance(value, str) and value.replace('.', '').replace('-', '').replace('e', '').replace('E', '').isdigit():
                    numeric_strings += 1
            
            if numeric_strings > 0 and numeric_strings < total_non_null:
                col_analysis['potential_issues'].append(f"Mixed string/numeric values: {numeric_strings}/{total_non_null} are numeric strings")
        
        validation_result['column_analysis'][column] = col_analysis
        
        # Check for critical issues
        if col_analysis['mixed_types'] or len(col_analysis['potential_issues']) > 0:
            validation_result['is_valid'] = False
            validation_result['issues'].append(f"Column '{column}': {', '.join(col_analysis['potential_issues'])}")
    
    # Generate recommendations
    if not validation_result['is_valid']:
        validation_result['recommendations'].extend([
            "Consider using explicit data type conversion before writing to Snowflake",
            "Use the 'use_logical_type=False' option in write_pandas for more lenient type handling",
            "Check for mixed data types in problematic columns and standardize them",
            "Consider using the 'on_error=ABORT' option to fail fast on type issues"
        ])
    
    return validation_result

def write_dataframe_to_table(
    session: Session, 
    df: pd.DataFrame, 
    schema: str, 
    table: str, 
    overwrite: bool = False, 
    auto_create: bool = True,
    temp_table: Optional[str] = None,
    validate_types: bool = True,
    use_logical_type: bool = True,
    on_error: str = "CONTINUE",
    df_fields: Optional[dict] = None,
    snowflake_fields: Optional[dict] = None,
    force_full_sync: bool = False
) -> bool:
    """
    Centralized function for writing DataFrames to Snowflake tables.
    
    Args:
        session: Snowflake Snowpark session
        df: DataFrame to write
        schema: Target schema name
        table: Target table name
        overwrite: Whether to overwrite existing data
        auto_create: Whether to auto-create the table if it doesn't exist
        temp_table: Optional temporary table name for batch operations
        validate_types: Whether to validate DataFrame types before writing
        use_logical_type: Whether to use logical types (set to False for lenient type handling)
        on_error: Error handling strategy ("CONTINUE", "ABORT", "SKIP_FILE")
        df_fields: Optional dictionary of field types for formatting (uses field_types.format_sync_file if provided)
        
    Returns:
        bool: True if successful, False otherwise
        
    Raises:
        Exception: If the write operation fails
    """
    try:
        # DEBUG: Log input DataFrame information
        logger.debug(f"🔍 DEBUG: Input DataFrame - Type: {type(df).__name__}, Is DataFrame: {isinstance(df, pd.DataFrame)}")
        if isinstance(df, pd.DataFrame):
            logger.debug(f"   Shape: {df.shape}")
        else:
            logger.debug(f"   Value: {df}")

        sd = df.head(1).to_dict()
        logger.error(f"   here is the sample data: {str(sd)[:500]}")


        # Format DataFrame using field_types.format_sync_file if df_fields provided
        if df_fields is not None:
            try:
                from lht.util import field_types
                df = field_types.format_sync_file(df, df_fields)
                logger.debug(f"🔍 DEBUG: After format_sync_file - Type: {type(df).__name__}, Shape: {df.shape if isinstance(df, pd.DataFrame) else 'N/A'}")
                
                # VALIDATION: Ensure snowflake_fields is provided when df_fields is available
                if snowflake_fields is None or len(snowflake_fields) == 0:
                    logger.error(f"❌ CRITICAL: df_fields provided but snowflake_fields is missing!")
                    logger.error(f"   This means sobjects.describe() failed or wasn't called")
                    logger.error(f"   Cannot proceed without proper Salesforce field type definitions")
                    raise Exception(f"Missing snowflake_fields when df_fields is provided for {schema}.{table}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to format DataFrame with field_types: {e}")
                logger.warning(f"   Continuing with original DataFrame")
        
        # Validate DataFrame types if requested
        if validate_types:
            validation_result = validate_dataframe_types(df)
            if not validation_result['is_valid']:
            #     logger.warning("⚠️ DataFrame type validation found potential issues:")
            #     for issue in validation_result['issues']:
            #         logger.warning(f"   - {issue}")
            #     for recommendation in validation_result['recommendations']:
            #         logger.info(f"   💡 {recommendation}")
                
                # If there are critical issues, consider using more lenient settings
                if use_logical_type and any("Mixed data types" in issue for issue in validation_result['issues']):
                    logger.info("🔄 Switching to lenient type handling due to mixed data types")
                    use_logical_type = False
                    on_error = "CONTINUE"  # Be more permissive with errors
        
        # Get current database for fully qualified table name
        current_db = session.sql('SELECT CURRENT_DATABASE()').collect()[0][0]
        
        # Determine the target table name
        if temp_table:
            target_table = temp_table
        else:
            target_table = table
            
        full_table_name = f"{current_db}.{schema}.{target_table}"
        
        logger.debug(f"💾 Writing DataFrame to table: {full_table_name}")
        logger.debug(f"   - Records: {len(df)}")
        logger.debug(f"   - Overwrite: {overwrite}")
        logger.debug(f"   - Auto-create: {auto_create}")
        logger.debug(f"   - Use logical types: {use_logical_type}")
        logger.debug(f"   - On error: {on_error}")
        
        # If we have field definitions and need to create a table, use centralized table creation
        if auto_create and df_fields is not None and len(df_fields) > 0:
            try:
                # The DataFrame has already been processed by field_types.format_sync_file above
                # No need to process it again - use the already-processed DataFrame
                
                # Use provided snowflake_fields if available, otherwise infer from DataFrame
                if snowflake_fields is not None and len(snowflake_fields) > 0:
                    # Use the Salesforce field types directly (correct approach)
                    pass
                else:
                    # No Salesforce field types provided - this should not happen in normal operation
                    logger.error(f"❌ CRITICAL: No Salesforce field types provided for table creation!")
                    logger.error(f"   This means sobjects.describe() failed or wasn't called")
                    logger.error(f"   Cannot create table without proper field type definitions")
                    raise Exception(f"No Salesforce field types provided for table {schema}.{table}")
                

                # Use centralized table creation
                table_creator.ensure_table_exists_for_dataframe(
                    session=session,
                    schema=schema,
                    table=target_table,
                    df_fields=df_fields,
                    snowflake_fields=snowflake_fields,
                    force_full_sync=force_full_sync,  # Pass through the force_full_sync parameter
                    database=current_db
                )
                logger.info(f"✅ Table creation completed, now writing data with overwrite={overwrite}")
                
                # Now write to the existing table using the already-processed DataFrame
                # Convert all datetime fields to timezone-naive for Snowflake compatibility
                for col in df.columns:
                    if col.upper() in ['CREATEDDATE', 'LASTMODIFIEDDATE', 'SYSTEMMODSTAMP', 'LASTACTIVITYDATE', 'LASTVIEWEDDATE', 'LASTREFERENCEDDATE']:
                        if 'UTC' in str(df[col].dtype) or 'timezone' in str(df[col].dtype):
                            try:
                                df[col] = df[col].dt.tz_localize(None)
                            except Exception as e:
                                logger.error(f"❌ Failed to convert {col} to timezone-naive: {e}")
                
                #df['CREATEDDATE'] = pd.to_datetime(df['CREATEDDATE'], errors='coerce')
                # DEBUG: Log df before creating Snowpark DataFrame
                logger.debug(f"🔍 DEBUG: Before create_dataframe (primary) - Type: {type(df).__name__}, Shape: {df.shape if isinstance(df, pd.DataFrame) else 'N/A'}")
                
                # Convert to Snowpark DataFrame and use save_as_table instead of write_pandas
                snowpark_df = session.create_dataframe(df)
                df = None
                snowpark_df.write.mode("overwrite" if overwrite else "append").save_as_table(full_table_name)
                snowpark_df = None
                logger.info(f"✅ Data written successfully with mode: {'overwrite' if overwrite else 'append'}")
                result = True  # save_as_table doesn't return a result object like write_pandas
            except Exception as table_error:
                logger.warning(f"Centralized table creation failed, falling back to auto-create: {table_error}")
                # CRITICAL FIX: Use the processed DataFrame for fallback, not the original
                logger.info(f"🔧 Using processed DataFrame for fallback write...")
                try:
                    from lht.util import field_types
                    df_fallback = field_types.format_sync_file(df, df_fields)
                    logger.info(f"✅ DataFrame processing completed for fallback write")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to process DataFrame with field_types for fallback: {e}")
                    df_fallback = df
                
                # TEST: Keeping all datetime fields for debugging (fallback path)
                logger.info(f"🧪 TEST: Keeping all datetime fields to debug the issue (fallback path)")
                logger.info(f"✅ TEST: All columns preserved in fallback: {list(df_fallback.columns)}")
                
                # Convert all datetime fields to timezone-naive for Snowflake compatibility
                # for col in df_fallback.columns:
                #     if col.upper() in ['CREATEDDATE', 'LASTMODIFIEDDATE', 'SYSTEMMODSTAMP', 'LASTACTIVITYDATE', 'LASTVIEWEDDATE', 'LASTREFERENCEDDATE']:
                #         if 'UTC' in str(df_fallback[col].dtype) or 'timezone' in str(df_fallback[col].dtype):
                #             try:
                #                 df_fallback[col] = df_fallback[col].dt.tz_localize(None)
                #             except Exception as e:
                #                 logger.error(f"❌ Failed to convert {col} to timezone-naive: {e}")
                
                # DEBUG: Log df_fallback before creating Snowpark DataFrame
                logger.debug(f"🔍 DEBUG: Before create_dataframe (fallback) - Type: {type(df_fallback).__name__}, Shape: {df_fallback.shape if isinstance(df_fallback, pd.DataFrame) else 'N/A'}")
                
                # Convert to Snowpark DataFrame and use save_as_table instead of write_pandas
                snowpark_df = session.create_dataframe(df_fallback)
                df_fallback = None
                snowpark_df.write.mode("overwrite" if overwrite else "append").save_as_table(full_table_name)
                snowpark_df = None
                logger.info(f"✅ Fallback data written successfully with mode: {'overwrite' if overwrite else 'append'}")
                result = True  # save_as_table doesn't return a result object like write_pandas
        else:
            # Use original behavior, but ensure DataFrame is properly processed
            if df_fields is not None and len(df_fields) > 0:
                try:
                    from lht.util import field_types
                    df_processed = field_types.format_sync_file(df, df_fields)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to process DataFrame with field_types: {e}")
                    df_processed = df
            else:
                df_processed = df
            
            # Convert all datetime fields to timezone-naive for Snowflake compatibility
            for col in df_processed.columns:
                if col.upper() in ['CREATEDDATE', 'LASTMODIFIEDDATE', 'SYSTEMMODSTAMP', 'LASTACTIVITYDATE', 'LASTVIEWEDDATE', 'LASTREFERENCEDDATE']:
                    if 'UTC' in str(df_processed[col].dtype) or 'timezone' in str(df_processed[col].dtype):
                        try:
                            df_processed[col] = df_processed[col].dt.tz_localize(None)
                        except Exception as e:
                            logger.error(f"❌ Failed to convert {col} to timezone-naive: {e}")
            
            # DEBUG: Log df_processed before creating Snowpark DataFrame
            logger.debug(f"🔍 DEBUG: Before create_dataframe (processed) - Type: {type(df_processed).__name__}, Shape: {df_processed.shape if isinstance(df_processed, pd.DataFrame) else 'N/A'}")
            logger.debug(f"🔍 DEBUG: df_processed columns count: {len(df_processed.columns)}")
            logger.debug(f"🔍 DEBUG: df_processed type check - isinstance DataFrame: {isinstance(df_processed, pd.DataFrame)}")
            
            # Ensure DataFrame is properly reset and clean for Snowflake
            df_processed = df_processed.copy()
            df_processed.reset_index(drop=True, inplace=True)
            logger.debug(f"🔍 DEBUG: df_processed shape: {df_processed.shape}")
            logger.debug(f"🔍 DEBUG: df_processed empty check: {df_processed.empty}")
            
            # Check for problematic dtypes
            logger.debug(f"🔍 DEBUG: Checking for problematic dtypes...")
            for col in df_processed.columns:
                dtype = df_processed[col].dtype
                if str(dtype) == 'object':
                    # Check if any values are not basic types
                    sample = df_processed[col].dropna().head(3)
                    for val in sample:
                        if val is not None and not pd.isna(val):
                            val_type = type(val).__name__
                            if val_type not in ['str', 'int', 'float', 'bool', 'Timestamp', 'datetime', 'date']:
                                logger.debug(f"🔍 DEBUG: Found unusual type in {col}: {val_type} - {str(val)[:100]}")

            # Convert to Snowpark DataFrame and use save_as_table instead of write_pandas
            try:
                # Final validation - ensure it's a proper pandas DataFrame
                if not isinstance(df_processed, pd.DataFrame):
                    raise TypeError(f"df_processed is not a pandas DataFrame, got {type(df_processed)}")
                
                # Ensure DataFrame is in a clean state
                if df_processed.index.name is not None:
                    df_processed.reset_index(drop=True, inplace=True)
                
                logger.debug(f"🔍 DEBUG: Attempting create_dataframe with type: {type(df_processed)}")
                logger.debug(f"🔍 DEBUG: DataFrame has index: {df_processed.index.tolist()[:5]}")
                
                # DEBUG: Try write_pandas first to a temporary table to validate DataFrame
                try:
                    debug_temp_table = f"{temp_table}_DEBUG" if temp_table else f"{table}_DEBUG"
                    logger.debug(f"🔍 DEBUG: Testing DataFrame with write_pandas to {schema}.{debug_temp_table}")
                    
                    session.write_pandas(
                        df_processed, 
                        table_name=debug_temp_table,
                        schema=schema,
                        auto_create_table=True,
                        overwrite=True
                    )
                    logger.debug(f"✅ DEBUG: write_pandas succeeded - DataFrame is valid")
                    logger.debug(f"🔍 DEBUG: Table {schema}.{debug_temp_table} created for inspection - NOT dropping")
                    # Table will remain for manual inspection - you can drop it manually after reviewing
                except Exception as wp_error:
                    logger.error(f"❌ DEBUG: write_pandas also failed: {wp_error}")
                    logger.error(f"   This suggests the DataFrame itself has structural issues")
                
                snowpark_df = session.create_dataframe(df_processed)
            except Exception as create_error:
                logger.error(f"❌ create_dataframe failed: {create_error}")
                logger.error(f"   DataFrame type: {type(df_processed)}")
                logger.error(f"   DataFrame shape: {df_processed.shape}")
                logger.error(f"   DataFrame columns: {list(df_processed.columns)[:10]}...")
                # Try to identify the problematic data
                try:
                    import json
                    # Try to convert to dict to see what's actually in there
                    sample_dict = df_processed.head(1).to_dict()
                    logger.error(f"   First row sample: {str(sample_dict)[:500]}")
                except Exception as dict_error:
                    logger.error(f"   Could not convert to dict: {dict_error}")
                raise
            
            # DEBUG: Display DataFrame contents before write
            logger.debug(f"\n🔍 DEBUG: DataFrame contents before write (line 367):")
            logger.debug(f"   Shape: {df_processed.shape}")
            logger.debug(f"   Columns: {list(df_processed.columns)}")
            logger.debug(f"   Dtypes:\n{df_processed.dtypes.to_string()}")
            logger.debug(f"   DataFrame type: {type(df_processed)}")
            logger.debug(f"   Is pandas DataFrame: {isinstance(df_processed, pd.DataFrame)}")
            if len(df_processed) > 0:
                logger.debug(f"   First row data:\n{df_processed.head(1).to_string()}")
            # Show each column's dtype in detail
            for col in df_processed.columns:
                dtype_str = str(df_processed[col].dtype)
                sample_val = df_processed[col].iloc[0] if len(df_processed) > 0 else None
                logger.debug(f"   Column '{col}': dtype={dtype_str}, sample_value={sample_val} (type: {type(sample_val).__name__})")
            
            df_processed = None
            snowpark_df.write.mode("overwrite" if overwrite else "append").save_as_table(full_table_name)
            snowpark_df = None
            logger.info(f"✅ Processed data written successfully with mode: {'overwrite' if overwrite else 'append'}")
            result = True  # save_as_table doesn't return a result object like write_pandas
        
        logger.debug(f"✅ Successfully wrote {len(df)} records to {full_table_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to write DataFrame to {schema}.{table}: {e}")
        logger.error(f"   - Error type: {type(e).__name__}")
        
        # Provide specific guidance for common errors
        if "Failed to cast" in str(e):
            logger.error("   🔍 This appears to be a data type casting issue.")
            logger.error("   💡 Try using validate_types=True and use_logical_type=False")
            logger.error("   💡 Check for mixed data types in your DataFrame columns")
        
        raise Exception(f"DataFrame write operation failed: {e}")




def standardize_dataframe_types(df: pd.DataFrame, type_strategy: str = "auto") -> pd.DataFrame:
    """
    Standardize DataFrame data types to prevent Snowflake casting issues.
    
    Args:
        df: DataFrame to standardize
        type_strategy: Strategy for type conversion ("auto", "string", "numeric", "lenient")
        
    Returns:
        DataFrame with standardized types
    """
    logger.info(f"🔧 Standardizing DataFrame types using strategy: {type_strategy}")
    
    df_standardized = df.copy()
    
    for column in df_standardized.columns:
        col_data = df_standardized[column]
        original_dtype = str(col_data.dtype)
        
        if type_strategy == "string":
            # Convert everything to string
            df_standardized[column] = col_data.astype(str)
            
        elif type_strategy == "numeric":
            # Try to convert to numeric where possible, string otherwise
            try:
                df_standardized[column] = pd.to_numeric(col_data, errors='coerce')
            except (ValueError, TypeError):
                df_standardized[column] = col_data.astype(str)
                
        elif type_strategy == "lenient":
            # More intelligent type conversion
            if col_data.dtype == 'object':
                # Check if column contains mostly numeric data
                non_null_values = col_data.dropna()
                if len(non_null_values) > 0:
                    numeric_count = 0
                    total_count = len(non_null_values)
                    
                    for value in non_null_values:
                        if isinstance(value, str):
                            # Check if string represents a number
                            try:
                                float(value)
                                numeric_count += 1
                            except ValueError:
                                pass
                        elif isinstance(value, (int, float)) or (hasattr(value, 'is_integer') and value.is_integer()):
                            numeric_count += 1
                    
                    # If more than 80% are numeric, convert the whole column
                    if numeric_count / total_count > 0.8:
                        try:
                            df_standardized[column] = pd.to_numeric(col_data, errors='coerce')
                        except (ValueError, TypeError):
                            df_standardized[column] = col_data.astype(str)
                    else:
                        df_standardized[column] = col_data.astype(str)
                        
        else:  # "auto" strategy
            # Smart type inference
            if col_data.dtype == 'object':
                # Try to infer the best type
                non_null_values = col_data.dropna()
                if len(non_null_values) > 0:
                    # Check if all values can be converted to the same type
                    all_numeric = True
                    all_strings = True
                    
                    for value in non_null_values:
                        if isinstance(value, str):
                            try:
                                float(value)
                            except ValueError:
                                all_numeric = False
                        elif not isinstance(value, (int, float)):
                            all_numeric = False
                            all_strings = False
                    
                    if all_numeric:
                        try:
                            df_standardized[column] = pd.to_numeric(col_data, errors='coerce')
                        except (ValueError, TypeError):
                            df_standardized[column] = col_data.astype(str)
                    elif all_strings:
                        df_standardized[column] = col_data.astype(str)
                    else:
                        # Mixed types - convert to string to be safe
                        df_standardized[column] = col_data.astype(str)
    
    logger.info(f"✅ DataFrame type standardization completed")
    return df_standardized

def write_dataframe_with_type_handling(
    session: Session,
    df: pd.DataFrame,
    schema: str,
    table: str,
    type_strategy: str = "auto",
    **kwargs
) -> bool:
    """
    Write DataFrame to Snowflake with automatic type handling and validation.
    
    Args:
        session: Snowflake Snowpark session
        df: DataFrame to write
        schema: Target schema name
        table: Target table name
        type_strategy: Strategy for type standardization ("auto", "string", "numeric", "lenient")
        **kwargs: Additional arguments for write_dataframe_to_table
        
    Returns:
        bool: True if successful
    """
    try:
        # Standardize types first
        df_standardized = standardize_dataframe_types(df, type_strategy)
        
        # Use lenient settings for problematic data
        if type_strategy in ["string", "lenient"]:
            kwargs.setdefault('use_logical_type', False)
            kwargs.setdefault('on_error', 'CONTINUE')
        
        # Write the standardized DataFrame
        return write_dataframe_to_table(
            session=session,
            df=df_standardized,
            schema=schema,
            table=table,
            **kwargs
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to write DataFrame with type handling: {e}")
        raise

def write_batch_to_temp_table(
    session: Session,
    df: pd.DataFrame,
    schema: Optional[str],
    temp_table: str,
    df_fields: dict,
    validate_types: bool = True,
    force_full_sync: bool = False,
    main_table: str = None,
    snowflake_fields: Optional[dict] = None
) -> bool:
    """
    Write a batch DataFrame to a temporary table for incremental sync operations.
    
    Args:
        session: Snowflake Snowpark session
        df: DataFrame to write
        schema: Target schema name (None to use session's current schema)
        temp_table: Temporary table name
        df_fields: List of field names for validation
        validate_types: Whether to validate DataFrame types before writing
        force_full_sync: Whether this is a full sync operation
        main_table: Main table name to copy schema from (for temp table creation)
        snowflake_fields: Salesforce field type definitions
        
    Returns:
        bool: True if successful
    """
    # Get current schema if not provided
    if schema is None:
        current_schema = session.sql('SELECT CURRENT_SCHEMA()').collect()[0][0]
        logger.debug(f"📦 Using current schema: {current_schema}")
    else:
        current_schema = schema
        
    logger.debug(f"📦 Writing batch to temp table: {current_schema}.{temp_table}")
    
    # Create temporary table with schema copied from main table if provided
    if main_table:
        try:
            create_temp_query = f"CREATE OR REPLACE TEMPORARY TABLE {temp_table} LIKE {main_table}"
            logger.debug(f"🔍 Creating temp table with schema copy: {create_temp_query}")
            session.sql(create_temp_query).collect()
            logger.debug(f"✅ Temp table created with schema from {main_table}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to create temp table with schema copy: {e}")
            logger.warning(f"⚠️ Falling back to auto-create mode")
            main_table = None  # Fall back to auto-create
    
    try:
        return write_dataframe_to_table(
            session=session,
            df=df,
            schema=current_schema,
            table=temp_table,
            overwrite=False,
            auto_create=main_table is None,  # Only auto-create if we didn't create with LIKE
            temp_table=temp_table,
            validate_types=validate_types,
            use_logical_type=False,  # More lenient for temp tables
            on_error="CONTINUE",
            df_fields=df_fields,  # Pass field definitions for proper formatting
            snowflake_fields=snowflake_fields,  # Pass Salesforce field types
            force_full_sync=force_full_sync  # Pass through force_full_sync parameter
        )
    except Exception as e:
        error_msg = str(e)
        if any(phrase in error_msg for phrase in ["Failed to cast", "cast", "variant", "FIXED"]):
            logger.warning(f"⚠️ Casting error detected in temp table write: {error_msg[:100]}...")
            logger.warning(f"⚠️ Retrying with type standardization...")
            
                        # Standardize types and retry
            df_standardized = standardize_dataframe_types(df, "string")
            return write_dataframe_to_table(
                session=session,
                df=df_standardized,
                schema=current_schema,
                table=temp_table,
                overwrite=False,
                auto_create=False,
                temp_table=temp_table,
                validate_types=False,
                use_logical_type=False,
                on_error="CONTINUE",
                df_fields=df_fields,  # Pass field definitions for proper formatting
                snowflake_fields=snowflake_fields,  # Pass Salesforce field types
                force_full_sync=force_full_sync  # Pass through force_full_sync parameter
            )
        else:
            logger.error(f"❌ Non-casting error in temp table write: {error_msg}")
            raise

def write_batch_to_main_table(
    session: Session,
    df: pd.DataFrame,
    schema: str,
    table: str,
    is_first_batch: bool = False,
    validate_types: bool = True,
    use_logical_type: bool = True,
    df_fields: Optional[dict] = None,
    snowflake_fields: Optional[dict] = None,
    force_full_sync: bool = False
) -> bool:
    """
    Write a batch DataFrame to the main table (overwrite for first batch, append for subsequent).
    
    Args:
        session: Snowflake Snowpark session
        df: DataFrame to write
        schema: Target schema name
        table: Target table name
        is_first_batch: Whether this is the first batch (determines overwrite behavior)
        validate_types: Whether to validate DataFrame types before writing
        use_logical_type: Whether to use logical types (set to False for lenient type handling)
        
    Returns:
        bool: True if successful
    """
    # Handle overwrite logic based on force_full_sync and batch type
    if force_full_sync and is_first_batch:
        # Force full sync: drop and recreate table, then overwrite first batch
        overwrite = True
        logger.debug(f"💾 Force full sync: overwriting first batch to recreate table")
    elif is_first_batch:
        # Regular first batch: append to existing or new table
        overwrite = False
        logger.debug(f"💾 Regular first batch: appending to table")
    else:
        # Subsequent batches: always append
        overwrite = False
        logger.debug(f"💾 Subsequent batch: appending to table")
    
    logger.debug(f"💾 Writing batch to main table: {schema}.{table} (overwrite={overwrite}, is_first_batch={is_first_batch}, force_full_sync={force_full_sync})")
    
    return write_dataframe_to_table(
        session=session,
        df=df,
        schema=schema,
        table=table,
        overwrite=overwrite,
        auto_create=True,
        validate_types=validate_types,
        use_logical_type=use_logical_type,
        on_error="CONTINUE",
        df_fields=df_fields,  # Pass field definitions for proper formatting
        snowflake_fields=snowflake_fields,  # Pass Salesforce field types for proper table creation
        force_full_sync=force_full_sync  # Pass through force_full_sync parameter
    )
