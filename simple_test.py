#!/usr/bin/env python3
"""
Simple test script to debug the sync issue.
Copy this into your Snowflake notebook and run it.
"""

print("🚀 Starting simple test...")

try:
    print("📦 Attempting to import lht...")
    import lht
    print("✅ Successfully imported lht")
    
    print("📦 Attempting to import sync_with_debug...")
    from lht.salesforce import sync_with_debug
    print("✅ Successfully imported sync_with_debug")
    
    print("📦 Attempting to import IntelligentSync...")
    from lht.salesforce import IntelligentSync
    print("✅ Successfully imported IntelligentSync")
    
    print("📦 Attempting to import sync_sobject_intelligent...")
    from lht.salesforce import sync_sobject_intelligent
    print("✅ Successfully imported sync_sobject_intelligent")
    
    print("\n" + "="*80)
    print("✅ ALL IMPORTS SUCCESSFUL")
    print("="*80)
    
    # Test if we can create an IntelligentSync instance
    print("\n🔍 Testing IntelligentSync creation...")
    print("Note: This will fail if session/access_info are not defined, but that's expected")
    
except ImportError as e:
    print(f"❌ IMPORT ERROR: {e}")
    print(f"❌ Error type: {type(e).__name__}")
    import traceback
    print(f"❌ Full traceback: {traceback.format_exc()}")
    
except Exception as e:
    print(f"❌ UNEXPECTED ERROR: {e}")
    print(f"❌ Error type: {type(e).__name__}")
    import traceback
    print(f"❌ Full traceback: {traceback.format_exc()}")

print("\n" + "="*80)
print("🏁 Test completed")
print("="*80)

# Instructions for the user
print("\n📋 NEXT STEPS:")
print("1. If imports worked, try creating your session and access_info")
print("2. Then run: sync_with_debug(session, access_info, 'Invoice__c', 'SALESFORCE', 'INVOICE', ...)")
print("3. If imports failed, check your package installation") 