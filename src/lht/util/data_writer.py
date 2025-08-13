import logging
from typing import Optional, Dict, Any
from snowflake.snowpark import Session
from snowflake.snowpark.dataframe import DataFrame
import pandas as pd
import numpy as np

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
    df_fields: Optional[dict] = None
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
        # Format DataFrame using field_types.format_sync_file if df_fields provided
        if df_fields is not None:
            try:
                from lht.util import field_types
                logger.info(f"🔧 Formatting DataFrame using field_types.format_sync_file with {len(df_fields)} field definitions")
                df = field_types.format_sync_file(df, df_fields)
                logger.info(f"✅ DataFrame formatting completed")
            except Exception as e:
                logger.warning(f"⚠️ Failed to format DataFrame with field_types: {e}")
                logger.warning(f"   Continuing with original DataFrame")
        
        # Validate DataFrame types if requested
        if validate_types:
            validation_result = validate_dataframe_types(df)
            if not validation_result['is_valid']:
                logger.warning("⚠️ DataFrame type validation found potential issues:")
                for issue in validation_result['issues']:
                    logger.warning(f"   - {issue}")
                for recommendation in validation_result['recommendations']:
                    logger.info(f"   💡 {recommendation}")
                
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
        
        # Write DataFrame to table
        result = session.write_pandas(
            df, 
            full_table_name,
            quote_identifiers=False, 
            auto_create_table=auto_create,
            overwrite=overwrite, 
            use_logical_type=use_logical_type, 
            on_error=on_error
        )
        
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
            logger.debug(f"   Column '{column}': {original_dtype} → string")
            
        elif type_strategy == "numeric":
            # Try to convert to numeric where possible, string otherwise
            try:
                df_standardized[column] = pd.to_numeric(col_data, errors='coerce')
                logger.debug(f"   Column '{column}': {original_dtype} → numeric")
            except (ValueError, TypeError):
                df_standardized[column] = col_data.astype(str)
                logger.debug(f"   Column '{column}': {original_dtype} → string (numeric conversion failed)")
                
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
                            logger.debug(f"   Column '{column}': {original_dtype} → numeric (80%+ numeric values)")
                        except (ValueError, TypeError):
                            df_standardized[column] = col_data.astype(str)
                            logger.debug(f"   Column '{column}': {original_dtype} → string (numeric conversion failed)")
                    else:
                        df_standardized[column] = col_data.astype(str)
                        logger.debug(f"   Column '{column}': {original_dtype} → string (mixed types)")
                        
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
                            logger.debug(f"   Column '{column}': {original_dtype} → numeric (all values numeric)")
                        except (ValueError, TypeError):
                            df_standardized[column] = col_data.astype(str)
                            logger.debug(f"   Column '{column}': {original_dtype} → string (numeric conversion failed)")
                    elif all_strings:
                        df_standardized[column] = col_data.astype(str)
                        logger.debug(f"   Column '{column}': {original_dtype} → string (all values strings)")
                    else:
                        # Mixed types - convert to string to be safe
                        df_standardized[column] = col_data.astype(str)
                        logger.debug(f"   Column '{column}': {original_dtype} → string (mixed types detected)")
    
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
    schema: str,
    temp_table: str,
    df_fields: dict,
    validate_types: bool = True
) -> bool:
    """
    Write a batch DataFrame to a temporary table for incremental sync operations.
    
    Args:
        session: Snowflake Snowpark session
        df: DataFrame to write
        schema: Target schema name
        temp_table: Temporary table name
        df_fields: List of field names for validation
        validate_types: Whether to validate DataFrame types before writing
        
    Returns:
        bool: True if successful
    """
    logger.debug(f"📦 Writing batch to temp table: {schema}.{temp_table}")
    
    try:
        return write_dataframe_to_table(
            session=session,
            df=df,
            schema=schema,
            table=temp_table,
            overwrite=False,
            auto_create=False,
            temp_table=temp_table,
            validate_types=validate_types,
            use_logical_type=False,  # More lenient for temp tables
            on_error="CONTINUE",
            df_fields=df_fields  # Pass field definitions for proper formatting
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
                schema=schema,
                table=temp_table,
                overwrite=False,
                auto_create=False,
                temp_table=temp_table,
                validate_types=False,
                use_logical_type=False,
                on_error="CONTINUE",
                df_fields=df_fields  # Pass field definitions for proper formatting
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
    df_fields: Optional[dict] = None
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
    # CRITICAL FIX: Never use overwrite=True for first batch
    # This prevents write_pandas from inferring wrong column types
    overwrite = False  # Always append, never overwrite
    logger.debug(f"💾 Writing batch to main table: {schema}.{table} (overwrite={overwrite}, is_first_batch={is_first_batch})")
    
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
        df_fields=df_fields  # Pass field definitions for proper formatting
    )
