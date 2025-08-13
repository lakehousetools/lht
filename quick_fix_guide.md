# Quick Fix Guide for Current Issues

## Issues Identified

1. **COUNT Query Still Using Old Syntax:** Debug shows `SELECT COUNT() FROM Invoice__c` instead of `SELECT COUNT(Id) FROM Invoice__c`
2. **Session Method Error:** `'Session' object has no attribute 'execute'` when uploading to stage

## Root Cause
You're likely running an older version of the package that doesn't include the fixes.

## Solution

### Step 1: Update to Latest Version
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht==0.0.52 --upgrade
```

### Step 2: Verify Installation
```python
import lht
print(lht.__version__)  # Should show 0.0.52
```

### Step 3: Test the Fix
```python
# Test COUNT query fix
from lht.salesforce.intelligent_sync import IntelligentSync

# This should now use SELECT COUNT(Id) instead of SELECT COUNT()
sync = IntelligentSync(session, access_info)
count = sync._estimate_record_count('Invoice__c', None)
print(f"Count: {count}")
```

## Alternative: Manual Fix

If you can't update the package, here are the manual fixes:

### Fix 1: COUNT Query Syntax
In `src/lht/salesforce/intelligent_sync.py` around line 336:
```python
# Change from:
query = f"SELECT COUNT() FROM {sobject}"

# To:
query = f"SELECT COUNT(Id) FROM {sobject}"
```

### Fix 2: Stage Upload Method
In `src/lht/util/stage.py`, ensure you're using the new method:
```python
# Use this method instead of put_file:
stage.put_csv_content_to_stage(session, stage_name, csv_content, filename)
```

## Expected Behavior After Fix

1. **COUNT Query:** Should show `SELECT COUNT(Id) FROM Invoice__c` in debug output
2. **Stage Upload:** Should work without session.execute() errors
3. **Debug Output:** Should show successful stage uploads

## Verification

After applying the fix, you should see:
```
🔍 Executing Salesforce record count query: SELECT COUNT(Id) FROM Invoice__c
📤 Uploading to Snowflake stage: @SALESFORCE_STAGE
✅ Successfully uploaded to stage: @SALESFORCE_STAGE
```

Instead of:
```
🔍 Executing Salesforce record count query: SELECT COUNT() FROM Invoice__c
❌ Error executing sync strategy: 'Session' object has no attribute 'execute'
``` 