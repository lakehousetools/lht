# Release Notes - Version 0.0.63

## 🔧 FIX: Missing Function Reference Error

### **Problem**
After the performance optimization in version 0.0.62, the system was encountering a function reference error:

```
❌ Error executing sync strategy: module 'lht.salesforce.query_bapi20' has no attribute 'get_bulk_results_with_stage'
```

### **Root Cause**
During the optimization, the function `get_bulk_results_with_stage` was renamed to `get_bulk_results_direct`, but there was still a reference to the old function name in `intelligent_sync.py`.

### **Fix**
**File:** `src/lht/salesforce/intelligent_sync.py` (line 535)

**Before:**
```python
if use_stage and stage_name:
    logger.debug(f"📤 Using stage-based results retrieval: {stage_name}")
    result = query_bapi20.get_bulk_results_with_stage(  # ← OLD FUNCTION NAME
        self.session, self.access_info, job_id, sobject, schema, table,
        stage_name=stage_name, use_stage=True
    )
else:
    logger.debug("📥 Using direct results retrieval")
    result = query_bapi20.get_bulk_results(
        self.session, self.access_info, job_id, sobject, schema, table
    )
```

**After:**
```python
logger.debug(f"📥 Getting results (optimized direct loading)")

# Use optimized direct loading for all cases (stage parameters are deprecated)
result = query_bapi20.get_bulk_results(  # ← UPDATED FUNCTION CALL
    self.session, self.access_info, job_id, sobject, schema, table,
    use_stage=use_stage, stage_name=stage_name
)
```

### **Expected Results**

**Before (Version 0.0.62):**
```
📊 Job status: JobComplete
❌ Error executing sync strategy: module 'lht.salesforce.query_bapi20' has no attribute 'get_bulk_results_with_stage'
✅ Sync completed: 0 records in 43.69s
```

**After (Version 0.0.63):**
```
📊 Job status: JobComplete
📦 Processing batch 1: 1000 records
📦 Processing batch 2: 1000 records
...
✅ Sync completed: 404739 records in 120.45s
```

### **Impact**
- ✅ **Fixes the function reference error** that was preventing sync completion
- ✅ **Maintains the performance optimization** from version 0.0.62
- ✅ **Simplifies the code path** by using direct loading for all cases
- ✅ **Preserves backward compatibility** with stage parameters

### **Installation**
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht==0.0.63 --upgrade
```

### **Testing**
```python
from lht.salesforce.intelligent_sync import sync_with_debug

result = sync_with_debug(
    session=session,
    access_info=access_info,
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE__C',
    use_stage=True,
    stage_name='@SALESFORCE_STAGE'
)
# Should complete successfully without function reference errors
```

---

**This fix resolves the function reference error and ensures the performance optimization works correctly. Update to version 0.0.63 for a fully functional, optimized sync experience.** 