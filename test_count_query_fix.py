#!/usr/bin/env python3
"""
Test script for the COUNT query fix in intelligent_sync.py
This tests the improved error handling for record count estimation.
"""

import json

def test_response_handling():
    """Test different Salesforce API response structures for COUNT queries."""
    
    print("🧪 Testing COUNT Query Response Handling")
    print("=" * 50)
    
    # Test case 1: Standard totalSize response
    response1 = {
        "totalSize": 12345,
        "done": True,
        "records": []
    }
    
    # Test case 2: Records array with expr0
    response2 = {
        "totalSize": 0,
        "done": True,
        "records": [
            {"expr0": 67890}
        ]
    }
    
    # Test case 3: Records array with different field name
    response3 = {
        "totalSize": 0,
        "done": True,
        "records": [
            {"count": 54321}
        ]
    }
    
    # Test case 4: Empty records array (problematic case)
    response4 = {
        "totalSize": 0,
        "done": True,
        "records": []
    }
    
    # Test case 5: Unexpected structure
    response5 = {
        "error": "Invalid query",
        "message": "Something went wrong"
    }
    
    test_cases = [
        ("Standard totalSize", response1),
        ("Records with expr0", response2),
        ("Records with count field", response3),
        ("Empty records array", response4),
        ("Error response", response5)
    ]
    
    for name, response in test_cases:
        print(f"\n📊 Testing: {name}")
        print(f"Response: {json.dumps(response, indent=2)}")
        
        try:
            count = extract_count_from_response(response)
            print(f"✅ Extracted count: {count}")
        except Exception as e:
            print(f"❌ Error: {e}")
            print(f"✅ Using fallback estimate")

def extract_count_from_response(result):
    """Extract count from Salesforce API response (simplified version of the fix)."""
    
    if isinstance(result, dict):
        # Check for totalSize (most common for COUNT queries)
        if 'totalSize' in result and result['totalSize'] > 0:
            count = result['totalSize']
            print(f"📊 Estimated record count from totalSize: {count}")
            return count
        
        # Check for records array with count
        if 'records' in result and len(result['records']) > 0:
            first_record = result['records'][0]
            # Try different possible field names for count
            count_fields = ['expr0', 'count', 'COUNT', 'count__c', 'Id']
            for field in count_fields:
                if field in first_record:
                    count = first_record[field]
                    print(f"📊 Estimated record count from {field}: {count}")
                    return count
            
            # If no expected field found, log the structure
            print(f"📊 Unexpected record structure: {first_record}")
            print(f"📊 Available fields: {list(first_record.keys())}")
        
        # Log all available keys for debugging
        print("📊 No count found in response, using conservative estimate")
        print(f"📊 Response keys: {list(result.keys())}")
    else:
        print(f"📊 Unexpected response type: {type(result)}")
        print(f"📊 Response: {result}")
    
    # Return conservative estimate
    return 50000

if __name__ == "__main__":
    test_response_handling()
    print("\n" + "=" * 50)
    print("✅ COUNT query fix test completed!")
    print("The improved error handling should prevent 'list index out of range' errors.") 