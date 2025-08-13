# Release Notes - Version 0.0.65

## 🔧 FIX: Fully Qualified Table Names in write_pandas

### **Problem**
Even after setting the schema context, the system was still encountering schema access control errors:

```
PROCESSING BATCH 1
❌ Error executing sync strategy: 003001 (42501): SQL access control error:
Insufficient privileges to operate on schema 'SALESFORCE'
```

### **Root Cause**
The issue was that `session.write_pandas()` was not properly handling the table name context. Even though we were setting the schema with `USE SCHEMA`, the `write_pandas()` function needed the fully qualified table name to work correctly.

### **Fix**
**File:** `src/lht/salesforce/query_bapi20.py` (lines 196-199, 221-224)

**Before:**
```python
# Set the current schema and write to table
session.sql(f"USE SCHEMA {schema}").collect()
session.write_pandas(formatted_df, table, ...)  # ← Just table name
```

**After:**
```python
# Set the current database and schema context
if database:
    session.sql(f"USE DATABASE {database}").collect()
session.sql(f"USE SCHEMA {schema}").collect()

# Use fully qualified table name for write_pandas
fully_qualified_table = f"{schema}.{table}"
session.write_pandas(formatted_df, fully_qualified_table, ...)  # ← Fully qualified name
```

### **Expected Results**

**Before (Version 0.0.64):**
```
PROCESSING BATCH 1
❌ Error executing sync strategy: 003001 (42501): SQL access control error:
Insufficient privileges to operate on schema 'SALESFORCE'
✅ Sync completed: 0 records in 57.85s
```

**After (Version 0.0.65):**
```
PROCESSING BATCH 1
📦 Processing batch 1: 1000 records
📦 Processing batch 2: 1000 records
...
✅ Sync completed: 404739 records in 120.45s
```

### **Impact**
- ✅ **Fixes schema access control errors** by using fully qualified table names
- ✅ **Maintains performance optimization** from previous versions
- ✅ **Ensures proper table context** for write_pandas operations
- ✅ **Supports optional database parameter** for explicit database context

### **Technical Details**
The fix ensures that:
1. **Database context is set** (if provided) before schema operations
2. **Schema context is set** before table operations
3. **Fully qualified table names** are used in `write_pandas()` calls
4. **Proper Snowflake object hierarchy** is maintained

### **Installation**
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht==0.0.65 --upgrade
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
# Should complete successfully without schema access control errors
```

---

**This fix resolves the fully qualified table name issue in write_pandas calls and ensures proper Snowflake object context. Update to version 0.0.65 for reliable table operations.** 