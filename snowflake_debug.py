#!/usr/bin/env python3
"""
Snowflake notebook-compatible debug scripts for intelligent sync.
These functions are designed to work directly in Snowflake notebooks.
"""

def test_salesforce_connection(access_info):
    """Test basic Salesforce connection in Snowflake notebook."""
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

def test_salesforce_api_call(access_info, sobject):
    """Test the Salesforce API call that's used in _estimate_record_count."""
    import requests
    
    print(f"🔍 Testing Salesforce API call for {sobject}")
    print(f"📋 Access info keys: {list(access_info.keys())}")
    
    # Build the same query as in _estimate_record_count
    query = f"SELECT COUNT() FROM {sobject}"
    print(f"📋 Query: {query}")
    
    # Use the same headers and URL construction
    headers = {
        "Authorization": f"Bearer {access_info['access_token']}",
        "Content-Type": "application/json"
    }
    url = f"{access_info['instance_url']}/services/data/v58.0/query?q={query}"
    
    print(f"🌐 URL: {url}")
    
    try:
        print("🚀 Making API request...")
        response = requests.get(url, headers=headers)
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Error response: {response.text}")
            return False
        
        result = response.json()
        print(f"📊 Response keys: {list(result.keys())}")
        
        # For COUNT() queries, Salesforce returns the count in totalSize field
        if 'totalSize' in result:
            count = result['totalSize']
            print(f"✅ Success! Record count: {count}")
            return True
        elif 'records' in result and len(result['records']) > 0:
            count = result['records'][0]['expr0']
            print(f"✅ Success! Record count: {count}")
            return True
        else:
            print(f"❌ Unexpected response format: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during API call: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return False

def test_sobjects_describe(access_info, sobject):
    """Test the sobjects.describe function."""
    print(f"🔍 Testing sobjects.describe for {sobject}")
    
    try:
        from lht.salesforce import sobjects
        
        print("🚀 Calling sobjects.describe...")
        query_string, df_fields = sobjects.describe(access_info, sobject)
        
        print(f"📋 Query string: {query_string}")
        print(f"📋 Field descriptions count: {len(df_fields) if df_fields else 0}")
        
        if query_string and df_fields:
            print("✅ sobjects.describe successful!")
            return True
        else:
            print("❌ sobjects.describe returned empty results")
            return False
            
    except Exception as e:
        print(f"❌ Exception in sobjects.describe: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return False

def step_by_step_debug(session, access_info, sobject, schema, table, **kwargs):
    """
    Step through each part of the intelligent sync process to identify issues.
    Snowflake notebook compatible version.
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

def run_complete_debug(session, access_info, sobject, schema, table, **kwargs):
    """
    Run complete debug sequence for Snowflake notebook.
    This is the main function you should call.
    """
    print("🚀 Starting complete debug sequence...")
    
    # Step 1: Test Salesforce connection
    print("\n" + "="*50)
    print("STEP 1: Testing Salesforce Connection")
    print("="*50)
    connection_ok = test_salesforce_connection(access_info)
    
    if not connection_ok:
        print("❌ Salesforce connection failed - stopping debug")
        return False
    
    # Step 2: Test specific API calls
    print("\n" + "="*50)
    print("STEP 2: Testing Specific API Calls")
    print("="*50)
    api_success = test_salesforce_api_call(access_info, sobject)
    describe_success = test_sobjects_describe(access_info, sobject)
    
    print(f"📊 API call success: {api_success}")
    print(f"📊 Describe success: {describe_success}")
    
    # Step 3: Test intelligent sync components
    print("\n" + "="*50)
    print("STEP 3: Testing Intelligent Sync Components")
    print("="*50)
    sync_success = step_by_step_debug(session, access_info, sobject, schema, table, **kwargs)
    
    print(f"📊 Sync components success: {sync_success}")
    
    # Summary
    print("\n" + "="*50)
    print("DEBUG SUMMARY")
    print("="*50)
    print(f"✅ Salesforce Connection: {connection_ok}")
    print(f"✅ API Call: {api_success}")
    print(f"✅ SObject Describe: {describe_success}")
    print(f"✅ Sync Components: {sync_success}")
    
    overall_success = connection_ok and api_success and describe_success and sync_success
    print(f"\n🎯 Overall Debug Success: {overall_success}")
    
    return overall_success

# Usage in Snowflake notebook:
"""
# Copy and paste this into your Snowflake notebook:

# First, make sure you have the lht package installed and imported
# Then run:

from snowflake_debug import run_complete_debug

# Run the complete debug sequence
success = run_complete_debug(
    session=session,
    access_info=sf_token,  # Your Salesforce access info
    sobject="Invoice__c",
    schema="SALESFORCE",
    table="INVOICE__C",
    use_stage=True,
    stage_name="@SALESFORCE_STAGE"
)

print(f"Final result: {success}")
""" 