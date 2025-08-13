#!/usr/bin/env python3
"""
Direct import test - bypass __init__.py issues.
Copy this into your Snowflake notebook.
"""

print("🚀 Starting direct import test...")

# Test 1: Check what's actually in the __init__.py
print("\n🔍 Test 1: Check __init__.py contents")
try:
    import lht.salesforce
    print(f"📦 lht.salesforce module: {lht.salesforce}")
    print(f"📦 dir(lht.salesforce): {dir(lht.salesforce)}")
except Exception as e:
    print(f"❌ Error checking __init__.py: {e}")

# Test 2: Try direct import from the module file
print("\n🔍 Test 2: Direct import from intelligent_sync module")
try:
    from lht.salesforce.intelligent_sync import sync_with_debug
    print("✅ sync_with_debug imported directly from intelligent_sync")
except Exception as e:
    print(f"❌ Direct import failed: {e}")

try:
    from lht.salesforce.intelligent_sync import sync_sobject_intelligent
    print("✅ sync_sobject_intelligent imported directly from intelligent_sync")
except Exception as e:
    print(f"❌ Direct import failed: {e}")

try:
    from lht.salesforce.intelligent_sync import IntelligentSync
    print("✅ IntelligentSync imported directly from intelligent_sync")
except Exception as e:
    print(f"❌ Direct import failed: {e}")

# Test 3: Check if the file exists
print("\n🔍 Test 3: Check if intelligent_sync.py exists")
try:
    import lht.salesforce.intelligent_sync
    print("✅ intelligent_sync.py module exists")
    print(f"📦 dir(intelligent_sync): {dir(lht.salesforce.intelligent_sync)}")
except Exception as e:
    print(f"❌ intelligent_sync.py not found: {e}")

# Test 4: Try to use the functions if they were imported
print("\n🔍 Test 4: Test function availability")
try:
    if 'sync_with_debug' in globals():
        print("✅ sync_with_debug is available")
    else:
        print("❌ sync_with_debug not available")
        
    if 'sync_sobject_intelligent' in globals():
        print("✅ sync_sobject_intelligent is available")
    else:
        print("❌ sync_sobject_intelligent not available")
        
    if 'IntelligentSync' in globals():
        print("✅ IntelligentSync is available")
    else:
        print("❌ IntelligentSync not available")
        
except Exception as e:
    print(f"❌ Function availability check failed: {e}")

# Test 5: Try to create a simple wrapper if imports worked
print("\n🔍 Test 5: Create wrapper if imports worked")
try:
    if 'sync_with_debug' in globals():
        print("✅ Can use sync_with_debug function")
        # Test if we can call it (will fail without session/access_info, but that's expected)
        print("📋 Function signature:", sync_with_debug.__doc__)
    else:
        print("❌ sync_with_debug not available for use")
        
except Exception as e:
    print(f"❌ Function test failed: {e}")

print("\n" + "="*80)
print("🏁 Direct import test completed")
print("="*80)

print("\n📋 NEXT STEPS:")
print("1. If direct imports worked, use them directly:")
print("   from lht.salesforce.intelligent_sync import sync_with_debug")
print("2. If they didn't work, we need to fix the package installation")
print("3. Copy the output of this test and share it") 