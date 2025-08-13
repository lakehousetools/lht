#!/usr/bin/env python3
"""
Test script to identify the merge issue.
Copy this into your Snowflake notebook.
"""

print("🚀 Testing merge issue...")

# Test 1: Check session schema
print("\n🔍 Test 1: Check session schema")
try:
    if 'session' in globals():
        current_schema = session.get_current_schema()
        print(f"📋 Current schema: '{current_schema}'")
        print(f"📋 Schema type: {type(current_schema)}")
        print(f"📋 Schema length: {len(current_schema) if current_schema else 0}")
        
        if not current_schema:
            print("❌ WARNING: Current schema is empty/None!")
        else:
            print("✅ Current schema looks good")
    else:
        print("❌ session variable not found")
except Exception as e:
    print(f"❌ Error checking schema: {e}")

# Test 2: Test the problematic SQL query
print("\n🔍 Test 2: Test the problematic SQL query")
try:
    if 'session' in globals():
        current_schema = session.get_current_schema().replace('"','')
        print(f"📋 Processed schema: '{current_schema}'")
        
        # This is the exact query from merge.py that's likely failing
        test_query = "select COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'TEST_TABLE' AND TABLE_SCHEMA = '{}' ORDER BY ORDINAL_POSITION".format(current_schema)
        print(f"📋 Test query: {test_query}")
        
        if not current_schema:
            print("❌ ERROR: Schema is empty, this will cause SQL error!")
            print("❌ The query will be: select COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'TEST_TABLE' AND TABLE_SCHEMA = '' ORDER BY ORDINAL_POSITION")
        else:
            print("✅ Schema looks good for query")
            
    else:
        print("❌ session variable not found")
except Exception as e:
    print(f"❌ Error testing query: {e}")

# Test 3: Try to import and test merge function
print("\n🔍 Test 3: Test merge function")
try:
    from lht.util import merge
    print("✅ merge module imported")
    
    # Test the format_insert_upsert function directly
    if 'session' in globals():
        print("📋 Testing format_insert_upsert function...")
        # This will likely fail, but we'll see the exact error
        result = merge.format_insert_upsert(session, "TEST_SRC", "TEST_TGT", "test_condition")
        print(f"📋 Result: {result}")
    else:
        print("❌ session variable not found")
        
except Exception as e:
    print(f"❌ Error testing merge: {e}")
    print(f"❌ Error type: {type(e).__name__}")
    import traceback
    print(f"❌ Full traceback: {traceback.format_exc()}")

print("\n" + "="*80)
print("🏁 Test completed")
print("="*80)

print("\n📋 LIKELY ISSUE:")
print("The merge.py function uses session.get_current_schema() which might be empty.")
print("This causes the SQL query to be malformed with an empty schema name.")
print("Solution: Set the session schema before running the sync.") 