#!/usr/bin/env python3
"""
Direct test script - copy this into your Snowflake notebook.
This will help us see if the issue is with imports or execution.
"""

print("🚀 Starting direct test...")

# Test 1: Basic Python functionality
print("\n🔍 Test 1: Basic Python functionality")
print("✅ Python is working")

# Test 2: Check if we can import basic modules
print("\n🔍 Test 2: Basic module imports")
try:
    import pandas as pd
    print("✅ pandas imported")
except Exception as e:
    print(f"❌ pandas import failed: {e}")

try:
    import requests
    print("✅ requests imported")
except Exception as e:
    print(f"❌ requests import failed: {e}")

# Test 3: Check package installation
print("\n🔍 Test 3: Package installation check")
try:
    import pkg_resources
    installed_packages = [d.project_name for d in pkg_resources.working_set]
    lht_versions = [d.version for d in pkg_resources.working_set if d.project_name == 'lht']
    print(f"✅ Found lht package: {lht_versions}")
except Exception as e:
    print(f"❌ Package check failed: {e}")

# Test 4: Try to import lht
print("\n🔍 Test 4: LHT import test")
try:
    import lht
    print("✅ lht imported successfully")
    print(f"📦 lht version: {getattr(lht, '__version__', 'unknown')}")
except Exception as e:
    print(f"❌ lht import failed: {e}")
    print(f"❌ Error type: {type(e).__name__}")

# Test 5: Try to import specific functions
print("\n🔍 Test 5: Specific function imports")
try:
    from lht.salesforce import sync_with_debug
    print("✅ sync_with_debug imported")
except Exception as e:
    print(f"❌ sync_with_debug import failed: {e}")

try:
    from lht.salesforce import sync_sobject_intelligent
    print("✅ sync_sobject_intelligent imported")
except Exception as e:
    print(f"❌ sync_sobject_intelligent import failed: {e}")

try:
    from lht.salesforce import IntelligentSync
    print("✅ IntelligentSync imported")
except Exception as e:
    print(f"❌ IntelligentSync import failed: {e}")

# Test 6: Check if session exists
print("\n🔍 Test 6: Session check")
try:
    if 'session' in globals():
        print("✅ session variable exists")
        print(f"📋 session type: {type(session)}")
    else:
        print("❌ session variable not found")
except Exception as e:
    print(f"❌ session check failed: {e}")

# Test 7: Check if access_info exists
print("\n🔍 Test 7: Access info check")
try:
    if 'sf_token' in globals():
        print("✅ sf_token variable exists")
        print(f"📋 sf_token type: {type(sf_token)}")
    elif 'access_info' in globals():
        print("✅ access_info variable exists")
        print(f"📋 access_info type: {type(access_info)}")
    else:
        print("❌ No access info variables found")
except Exception as e:
    print(f"❌ access info check failed: {e}")

print("\n" + "="*80)
print("🏁 Direct test completed")
print("="*80)

print("\n📋 WHAT TO DO NEXT:")
print("1. If all imports worked, try running your sync function")
print("2. If imports failed, try: !pip install --upgrade --index-url https://test.pypi.org/simple/ lht==0.0.45")
print("3. If session/access_info are missing, create them first")
print("4. Copy the output of this test and share it") 