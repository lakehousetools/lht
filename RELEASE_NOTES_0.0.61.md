# Release Notes - Version 0.0.61

## 🔧 FIX: Schema Context in Stage Uploads

### **Problem**
When uploading CSV data to Snowflake stages, the system was encountering schema access control errors:

```
📤 Uploading to Snowflake stage: @SALESFORCE_STAGE
❌ Error executing sync strategy: Failed to write DataFrame to stage @SALESFORCE_STAGE: 
003001 (42501): SQL access control error:
Insufficient privileges to operate on schema 'PUBLIC'
```

### **Root Cause**
The issue occurred in the `put_dataframe_to_stage` function when:
1. **Creating temporary tables:** The function was creating temporary tables in the `PUBLIC` schema instead of the target schema
2. **Missing schema parameter:** The stage upload functions weren't receiving the schema information from the calling code
3. **Default schema behavior:** Snowflake was defaulting to `PUBLIC` schema when no schema was specified

### **Fix**
**Files:** 
- `src/lht/util/stage.py` (lines 33-118)
- `src/lht/salesforce/query_bapi20.py` (lines 195, 220)

**Before:**
```python
def put_dataframe_to_stage(session, stage_name, df, filename=None):
    # ...
    temp_table_name = f"TEMP_{filename.replace('.csv', '').replace('-', '_')}"
    
    # Write DataFrame to a temporary table (defaults to PUBLIC schema)
    session.write_pandas(df, temp_table_name, ...)
    
    # Copy from temporary table to stage
    copy_command = f"""
    COPY INTO @{stage_name}/{filename}
    FROM {temp_table_name}  # ← Uses PUBLIC schema
    """
```

**After:**
```python
def put_dataframe_to_stage(session, stage_name, df, filename=None, schema=None):
    # ...
    temp_table_name = f"TEMP_{filename.replace('.csv', '').replace('-', '_')}"
    
    # Use schema if provided, otherwise use current schema
    if schema:
        full_temp_table_name = f"{schema}.{temp_table_name}"
    else:
        full_temp_table_name = temp_table_name
    
    # Write DataFrame to a temporary table in correct schema
    session.write_pandas(df, full_temp_table_name, ...)
    
    # Copy from temporary table to stage
    copy_command = f"""
    COPY INTO @{stage_name}/{filename}
    FROM {full_temp_table_name}  # ← Uses SALESFORCE schema
    """
```

**Calling Code Update:**
```python
# Before
stage.put_csv_content_to_stage(session, stage_name, csv_content, filename=stage_filename)

# After  
stage.put_csv_content_to_stage(session, stage_name, csv_content, filename=stage_filename, schema=schema)
```

### **Expected Results**

**Before (Version 0.0.60 and earlier):**
```
📤 Uploading to Snowflake stage: @SALESFORCE_STAGE
❌ Error: Failed to write DataFrame to stage @SALESFORCE_STAGE: 
003001 (42501): SQL access control error:
Insufficient privileges to operate on schema 'PUBLIC'
✅ Sync completed: 0 records in 57.38s
```

**After (Version 0.0.61):**
```
📤 Uploading to Snowflake stage: @SALESFORCE_STAGE
✅ Successfully uploaded to stage: @SALESFORCE_STAGE
📦 Processing batch 1: 1000 records
📦 Processing batch 2: 1000 records
...
✅ Sync completed: 404739 records in 120.45s
```

### **Impact**
- ✅ **Correct schema usage** for temporary table creation
- ✅ **No more access control errors** when uploading to stages
- ✅ **Proper stage uploads** for large datasets
- ✅ **Schema-aware operations** throughout the stage upload process

### **Technical Details**
The fix ensures that:
1. **Schema parameter is passed** from Bulk API functions to stage upload functions
2. **Temporary tables are created** in the correct schema (SALESFORCE, not PUBLIC)
3. **COPY commands reference** the correct schema-qualified table names
4. **Cleanup operations** use the correct schema-qualified table names

### **Installation**
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht==0.0.61 --upgrade
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

**This fix resolves the schema context issues that were preventing successful stage uploads. Update to version 0.0.61 for proper schema handling in stage-based sync operations.** 