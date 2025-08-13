#!/usr/bin/env python3
"""
Debug script for sync_sobject_intelligent to identify SQL errors.
Run this in your Snowflake notebook to get detailed debugging output.
"""

import logging
import sys

def setup_debug_logging():
    """Setup comprehensive logging for debugging."""
    # Configure logging to show all debug messages
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
        force=True
    )
    
    # Create a custom handler to ensure logs go to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Get the logger and add our handler
    logger = logging.getLogger('lht.salesforce.intelligent_sync')
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    print("🚀 Debug logging configured for sync operation...")

def run_sync_with_debug(session, access_info, sobject, schema, table, **kwargs):
    """
    Run sync_sobject_intelligent with comprehensive debugging.
    
    Args:
        session: Snowflake Snowpark session
        access_info: Dictionary containing Salesforce access details
        sobject: Salesforce SObject name
        schema: Snowflake schema name
        table: Snowflake table name
        **kwargs: Additional arguments for sync_sobject_intelligent
    """
    try:
        # Setup logging
        setup_debug_logging()
        
        print("=" * 80)
        print("🔍 STARTING DEBUG SYNC OPERATION")
        print("=" * 80)
        print(f"📋 Parameters:")
        print(f"   - SObject: {sobject}")
        print(f"   - Schema: {schema}")
        print(f"   - Table: {table}")
        print(f"   - Additional args: {kwargs}")
        print("=" * 80)
        
        # Import and run the sync function
        from lht.salesforce.intelligent_sync import sync_sobject_intelligent
        
        print("📦 Imported sync_sobject_intelligent successfully")
        
        result = sync_sobject_intelligent(
            session=session,
            access_info=access_info,
            sobject=sobject,
            schema=schema,
            table=table,
            **kwargs
        )
        
        print("=" * 80)
        print("✅ SYNC OPERATION COMPLETED")
        print("=" * 80)
        print(f"📊 Result: {result}")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print("=" * 80)
        print("❌ SYNC OPERATION FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        print("=" * 80)
        raise

# Example usage (uncomment and modify for your use case):
"""
# In your Snowflake notebook, use this:

from debug_sync import run_sync_with_debug

result = run_sync_with_debug(
    session=session,
    access_info=sf_token,
    sobject="Invoice__c",
    schema="SALESFORCE",
    table="INVOICE",
    match_field="ID",
    use_stage=True,
    stage_name="@SALESFORCE_STAGE"
)
""" 