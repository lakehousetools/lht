# Release Notes - Version 0.0.56

## 🚨 CRITICAL FIX: COUNT Query Parsing

### **Problem**
The COUNT query was incorrectly parsing Salesforce API responses, causing:
- **Wrong record count estimates** (returning 1 instead of actual count like 404,739)
- **Incorrect sync strategy selection** (choosing `regular_api_full` instead of `bulk_api_stage_full`)
- **Schema errors** due to wrong method being used

### **Root Cause**
The Salesforce COUNT query response structure:
```json
{
  "totalSize": 1,           // ← This is ALWAYS 1 for COUNT queries
  "done": true,
  "records": [
    {
      "attributes": {"type": "AggregateResult"},
      "expr0": 404739       // ← This contains the actual count
    }
  ]
}
```

The code was incorrectly prioritizing `totalSize` (which is always 1 for COUNT queries) over the actual count value in `expr0`.

### **Fix**
**File:** `src/lht/salesforce/intelligent_sync.py` (lines 355-375)

**Before:**
```python
# Check for totalSize (most common for COUNT queries)
if 'totalSize' in result and result['totalSize'] > 0:
    count = result['totalSize']  # ← Always returns 1 for COUNT queries
    return count

# Check for records array with count
if 'records' in result and len(result['records']) > 0:
    # ... check expr0, etc.
```

**After:**
```python
# For COUNT queries, check records array first (totalSize is always 1 for COUNT queries)
if 'records' in result and len(result['records']) > 0:
    first_record = result['records'][0]
    count_fields = ['expr0', 'count', 'COUNT', 'count__c', 'Id']
    for field in count_fields:
        if field in first_record:
            count = first_record[field]  # ← Now correctly gets 404739 from expr0
            return count

# Fallback to totalSize (though this should not be used for COUNT queries)
if 'totalSize' in result and result['totalSize'] > 0:
    count = result['totalSize']
    return count
```

### **Expected Results**

**Before (Version 0.0.55 and earlier):**
```
🔍 Executing Salesforce record count query: SELECT COUNT(Id) FROM Invoice__c
📊 Salesforce API response: {'totalSize': 1, 'done': True, 'records': [{'attributes': {'type': 'AggregateResult'}, 'expr0': 404739}]}
📊 Estimated record count from totalSize: 1  ← WRONG!
🎯 Sync strategy: regular_api_full  ← WRONG!
❌ Error executing sync strategy: Insufficient privileges to operate on schema 'PUBLIC'
```

**After (Version 0.0.56):**
```
🔍 Executing Salesforce record count query: SELECT COUNT(Id) FROM Invoice__c
📊 Salesforce API response: {'totalSize': 1, 'done': True, 'records': [{'attributes': {'type': 'AggregateResult'}, 'expr0': 404739}]}
📊 Estimated record count from expr0: 404739  ← CORRECT!
🎯 Sync strategy: bulk_api_stage_full  ← CORRECT!
🚀 Executing sync strategy: bulk_api_stage_full
📦 Using Bulk API sync method: bulk_api_stage_full
📤 Uploading to Snowflake stage: @SALESFORCE_STAGE
✅ Successfully uploaded to stage: @SALESFORCE_STAGE
```

### **Impact**
- ✅ **Correct record count estimation** for all SObjects
- ✅ **Proper sync strategy selection** (Bulk API for large datasets)
- ✅ **Correct schema usage** (SALESFORCE instead of PUBLIC)
- ✅ **Stage-based uploads** for large datasets in notebook environments

### **Installation**
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht==0.0.56 --upgrade
```

### **Testing**
```python
from lht.salesforce.intelligent_sync import IntelligentSync

sync = IntelligentSync(session, access_info)
count = sync._estimate_record_count('Invoice__c', None)
print(f"Count: {count}")  # Should show 404739, not 1
```

---

**This fix resolves the core issue that was preventing proper sync strategy selection and causing schema errors. Update to version 0.0.56 immediately for correct behavior.** 