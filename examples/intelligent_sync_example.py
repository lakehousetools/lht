"""
Intelligent Salesforce Synchronization Example

This example demonstrates how to use the intelligent sync system to automatically
determine the best synchronization method based on data volume and previous sync status.
"""

import os
from snowflake.snowpark import Session
from lht.salesforce.intelligent_sync import sync_sobject_intelligent, IntelligentSync

# Example 1: Simple intelligent sync
def example_simple_sync():
    """Example of simple intelligent sync for an Account object."""
    
    # Initialize Snowflake session (replace with your connection parameters)
    session = Session.builder.configs({
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA")
    }).create()
    
    # Salesforce access info
    access_info = {
        "access_token": os.getenv("SALESFORCE_ACCESS_TOKEN"),
        "instance_url": os.getenv("SALESFORCE_INSTANCE_URL")
    }
    
    # Sync Account object intelligently
    result = sync_sobject_intelligent(
        session=session,
        access_info=access_info,
        sobject="Account",
        schema="RAW",
        table="ACCOUNTS",
        match_field="ID"
    )
    
    print("Sync Result:", result)
    session.close()

# Example 2: Advanced sync with stage usage
def example_advanced_sync():
    """Example of advanced sync with stage usage for large datasets."""
    
    session = Session.builder.configs({
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA")
    }).create()
    
    access_info = {
        "access_token": os.getenv("SALESFORCE_ACCESS_TOKEN"),
        "instance_url": os.getenv("SALESFORCE_INSTANCE_URL")
    }
    
    # Create stage for large datasets
    session.sql("CREATE OR REPLACE STAGE @SALESFORCE_STAGE").collect()
    
    # Sync Contact object with stage usage
    result = sync_sobject_intelligent(
        session=session,
        access_info=access_info,
        sobject="Contact",
        schema="RAW",
        table="CONTACTS",
        match_field="ID",
        use_stage=True,
        stage_name="@SALESFORCE_STAGE"
    )
    
    print("Advanced Sync Result:", result)
    session.close()

# Example 3: Using the IntelligentSync class directly
def example_class_usage():
    """Example using the IntelligentSync class directly for more control."""
    
    session = Session.builder.configs({
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA")
    }).create()
    
    access_info = {
        "access_token": os.getenv("SALESFORCE_ACCESS_TOKEN"),
        "instance_url": os.getenv("SALESFORCE_INSTANCE_URL")
    }
    
    # Create sync system with custom thresholds
    sync_system = IntelligentSync(session, access_info)
    
    # Customize thresholds for your environment
    sync_system.BULK_API_THRESHOLD = 5000  # Use Bulk API for 5K+ records
    sync_system.STAGE_THRESHOLD = 25000    # Use stage for 25K+ records
    
    # Sync multiple objects
    objects_to_sync = [
        {"sobject": "Account", "table": "ACCOUNTS"},
        {"sobject": "Contact", "table": "CONTACTS"},
        {"sobject": "Opportunity", "table": "OPPORTUNITIES"},
        {"sobject": "Lead", "table": "LEADS"}
    ]
    
    results = []
    for obj in objects_to_sync:
        print(f"\n🔄 Syncing {obj['sobject']}...")
        result = sync_system.sync_sobject(
            sobject=obj['sobject'],
            schema="RAW",
            table=obj['table'],
            match_field="ID",
            use_stage=True,
            stage_name="@SALESFORCE_STAGE"
        )
        results.append(result)
    
    # Print summary
    print("\n📊 Sync Summary:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['sobject']}: {result['actual_records']} records "
              f"({result['sync_method']}) in {result['sync_duration_seconds']:.2f}s")
    
    session.close()

# Example 4: Force full sync
def example_force_full_sync():
    """Example of forcing a full sync regardless of previous sync status."""
    
    session = Session.builder.configs({
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA")
    }).create()
    
    access_info = {
        "access_token": os.getenv("SALESFORCE_ACCESS_TOKEN"),
        "instance_url": os.getenv("SALESFORCE_INSTANCE_URL")
    }
    
    # Force full sync (useful for data refresh or after schema changes)
    result = sync_sobject_intelligent(
        session=session,
        access_info=access_info,
        sobject="Account",
        schema="RAW",
        table="ACCOUNTS",
        match_field="ID",
        force_full_sync=True  # This will overwrite the entire table
    )
    
    print("Force Full Sync Result:", result)
    session.close()

# Example 5: Snowflake Notebook usage
def snowflake_notebook_example():
    """
    Example for use in Snowflake Notebooks.
    Copy this function into a Snowflake Notebook cell.
    """
    
    # In Snowflake Notebook, session is already available
    # session = snowpark_session  # This is available in Snowflake Notebooks
    
    # Salesforce access info (set these in your notebook)
    access_info = {
        "access_token": "your_access_token_here",
        "instance_url": "https://your-instance.salesforce.com"
    }
    
    # Create stage for large datasets
    session.sql("CREATE OR REPLACE STAGE @SALESFORCE_STAGE").collect()
    
    # Sync Account object
    result = sync_sobject_intelligent(
        session=session,
        access_info=access_info,
        sobject="Account",
        schema="RAW",
        table="ACCOUNTS",
        match_field="ID",
        use_stage=True,
        stage_name="@SALESFORCE_STAGE"
    )
    
    # Display results
    print("Sync completed successfully!")
    print(f"Method used: {result['sync_method']}")
    print(f"Records processed: {result['actual_records']}")
    print(f"Duration: {result['sync_duration_seconds']:.2f} seconds")
    
    return result

if __name__ == "__main__":
    # Run examples (uncomment the one you want to test)
    
    # example_simple_sync()
    # example_advanced_sync()
    # example_class_usage()
    # example_force_full_sync()
    
    print("Please uncomment the example you want to run and set up your environment variables.") 