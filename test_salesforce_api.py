#!/usr/bin/env python3
"""
Test script to isolate Salesforce API issues in the intelligent sync.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

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
    print(f"🔑 Headers: {headers}")
    
    try:
        print("🚀 Making API request...")
        response = requests.get(url, headers=headers)
        print(f"📊 Response status: {response.status_code}")
        print(f"📊 Response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"❌ Error response: {response.text}")
            return False
        
        result = response.json()
        print(f"📊 Response JSON: {result}")
        
        if 'records' in result and len(result['records']) > 0:
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
        print(f"📋 Field descriptions: {df_fields}")
        
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

# Example usage:
"""
# In your Snowflake notebook, use this:

from test_salesforce_api import test_salesforce_api_call, test_sobjects_describe

# Test the API call
api_success = test_salesforce_api_call(sf_token, "Invoice__c")

# Test sobjects.describe
describe_success = test_sobjects_describe(sf_token, "Invoice__c")

print(f"API call success: {api_success}")
print(f"Describe success: {describe_success}")
""" 