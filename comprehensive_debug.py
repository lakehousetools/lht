#!/usr/bin/env python3
"""
Comprehensive debug script to step through the intelligent sync process.
This will help identify exactly where the error is occurring.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def step_by_step_debug(session, access_info, sobject, schema, table, **kwargs):
    """
    Step through each part of the intelligent sync process to identify issues.
    """
    print("=" * 80)
    print("🔍 COMPREHENSIVE DEBUG - STEP BY STEP")
    print("=" * 80)
    
    try:
        from lht.salesforce.intelligent_sync import IntelligentSync
        
        print("✅ Step 1: Imported IntelligentSync successfully")
        
        # Create the sync object
        sync = IntelligentSync(session, access_info)
        print("✅ Step 2: Created IntelligentSync object")
        
        # Test schema existence
        print("\n🔍 Step 3: Testing schema existence...")
        schema_exists = sync._ensure_schema_exists(schema)
        print(f"📋 Schema {schema} exists: {schema_exists}")
        
        # Test table existence
        print("\n🔍 Step 4: Testing table existence...")
        table_exists = sync._table_exists(schema, table)
        print(f"📋 Table {schema}.{table} exists: {table_exists}")
        
        # Test last modified date (only if table exists)
        last_modified_date = None
        if table_exists:
            print("\n🔍 Step 5: Testing last modified date retrieval...")
            last_modified_date = sync._get_last_modified_date(schema, table)
            print(f"📅 Last modified date: {last_modified_date}")
        else:
            print("\n⏭️ Step 5: Skipping last modified date (table doesn't exist)")
        
        # Test record count estimation
        print("\n🔍 Step 6: Testing record count estimation...")
        try:
            estimated_records = sync._estimate_record_count(sobject, last_modified_date)
            print(f"📊 Estimated records: {estimated_records}")
        except Exception as e:
            print(f"❌ Error in record count estimation: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            return False
        
        # Test sync strategy determination
        print("\n🔍 Step 7: Testing sync strategy determination...")
        try:
            use_stage = kwargs.get('use_stage', False)
            stage_name = kwargs.get('stage_name', None)
            sync_strategy = sync._determine_sync_strategy(
                sobject, table_exists, last_modified_date, use_stage, stage_name
            )
            print(f"📋 Sync strategy: {sync_strategy}")
        except Exception as e:
            print(f"❌ Error in sync strategy determination: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            return False
        
        # Test sobjects.describe (this is called in bulk API sync)
        print("\n🔍 Step 8: Testing sobjects.describe...")
        try:
            from lht.salesforce import sobjects
            query_string, df_fields = sobjects.describe(access_info, sobject)
            print(f"📋 Query string: {query_string}")
            print(f"📋 Field descriptions count: {len(df_fields) if df_fields else 0}")
        except Exception as e:
            print(f"❌ Error in sobjects.describe: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            return False
        
        print("\n✅ All steps completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error in step-by-step debug: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return False

def test_salesforce_connection(access_info):
    """Test basic Salesforce connection."""
    print("🔍 Testing Salesforce connection...")
    
    try:
        import requests
        
        # Test basic API call
        headers = {
            "Authorization": f"Bearer {access_info['access_token']}",
            "Content-Type": "application/json"
        }
        url = f"{access_info['instance_url']}/services/data/v58.0/sobjects"
        
        print(f"🌐 Testing URL: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            print("✅ Salesforce connection successful!")
            return True
        else:
            print(f"❌ Salesforce connection failed: {response.status_code}")
            print(f"📋 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Salesforce connection: {e}")
        return False

# Example usage:
"""
# In your Snowflake notebook, use this:

from comprehensive_debug import step_by_step_debug, test_salesforce_connection

# First test Salesforce connection
connection_ok = test_salesforce_connection(sf_token)

if connection_ok:
    # Then run step-by-step debug
    success = step_by_step_debug(
        session=session,
        access_info=sf_token,
        sobject="Invoice__c",
        schema="SALESFORCE",
        table="INVOICE__C",
        use_stage=True,
        stage_name="@SALESFORCE_STAGE"
    )
    
    print(f"Step-by-step debug success: {success}")
else:
    print("❌ Salesforce connection failed - check your access token and instance URL")
""" 