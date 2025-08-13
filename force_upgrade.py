#!/usr/bin/env python3
"""
Force upgrade script for Snowflake notebook.
Copy this into your notebook to force upgrade to the latest version.
"""

print("🚀 Starting force upgrade...")

# Step 1: Check current version
print("\n🔍 Step 1: Check current version")
try:
    import pkg_resources
    lht_versions = [d.version for d in pkg_resources.working_set if d.project_name == 'lht']
    print(f"📦 Current lht version: {lht_versions}")
except Exception as e:
    print(f"❌ Version check failed: {e}")

# Step 2: Uninstall current version
print("\n🔍 Step 2: Uninstall current version")
try:
    import subprocess
    import sys
    
    # Uninstall current version
    result = subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "lht"], 
                          capture_output=True, text=True)
    print(f"📦 Uninstall result: {result.returncode}")
    if result.stdout:
        print(f"📦 Uninstall stdout: {result.stdout}")
    if result.stderr:
        print(f"📦 Uninstall stderr: {result.stderr}")
except Exception as e:
    print(f"❌ Uninstall failed: {e}")

# Step 3: Install latest version
print("\n🔍 Step 3: Install latest version")
try:
    result = subprocess.run([
        sys.executable, "-m", "pip", "install", 
        "--index-url", "https://test.pypi.org/simple/",
        "--extra-index-url", "https://pypi.org/simple/",
        "lht==0.0.45"
    ], capture_output=True, text=True)
    print(f"📦 Install result: {result.returncode}")
    if result.stdout:
        print(f"📦 Install stdout: {result.stdout}")
    if result.stderr:
        print(f"📦 Install stderr: {result.stderr}")
except Exception as e:
    print(f"❌ Install failed: {e}")

# Step 4: Verify installation
print("\n🔍 Step 4: Verify installation")
try:
    import pkg_resources
    lht_versions = [d.version for d in pkg_resources.working_set if d.project_name == 'lht']
    print(f"📦 New lht version: {lht_versions}")
except Exception as e:
    print(f"❌ Version check failed: {e}")

# Step 5: Test imports
print("\n🔍 Step 5: Test imports")
try:
    import lht
    print("✅ lht imported")
    
    from lht.salesforce import sync_with_debug
    print("✅ sync_with_debug imported")
    
    from lht.salesforce import sync_sobject_intelligent
    print("✅ sync_sobject_intelligent imported")
    
    from lht.salesforce import IntelligentSync
    print("✅ IntelligentSync imported")
    
    print("\n" + "="*80)
    print("✅ ALL IMPORTS SUCCESSFUL!")
    print("="*80)
    
except Exception as e:
    print(f"❌ Import test failed: {e}")
    print(f"❌ Error type: {type(e).__name__}")
    import traceback
    print(f"❌ Full traceback: {traceback.format_exc()}")

print("\n" + "="*80)
print("🏁 Force upgrade completed")
print("="*80) 