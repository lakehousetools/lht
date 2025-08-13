# Release Notes - Version 0.0.60

## 🔧 FIX: Data Type Conversion in Stage Uploads

### **Problem**
When uploading CSV data to Snowflake stages, the system was encountering data type conversion errors:

```
❌ Error executing sync strategy: Failed to write DataFrame to stage @SALESFORCE_STAGE: 
("Could not convert '10' with type str: tried to convert to int64", 
'Conversion failed for column Store_Number__c with type object')

DtypeWarning: Columns (23) have mixed types. Specify dtype option on import or set low_memory=False.
```

### **Root Cause**
The issue occurred in the `put_csv_content_to_stage` function when:
1. **Reading CSV content:** pandas was trying to infer data types and encountering mixed types
2. **Writing to stage:** Snowflake was attempting to convert string values to numeric types
3. **Mixed data types:** Columns like `Store_Number__c` contained both string and numeric values

### **Fix**
**File:** `src/lht/util/stage.py` (lines 113 and 45-50)

**Before:**
```python
# Convert CSV string to DataFrame
csv_buffer = io.StringIO(csv_content)
df = pd.read_csv(csv_buffer)  # ← pandas tries to infer types

# Convert DataFrame to CSV string
csv_buffer = io.StringIO()
df.to_csv(csv_buffer, index=False)  # ← original data types preserved
```

**After:**
```python
# Convert CSV string to DataFrame with proper data type handling
csv_buffer = io.StringIO(csv_content)
df = pd.read_csv(csv_buffer, low_memory=False, dtype=str)  # ← Force all columns to string

# Convert DataFrame to CSV string with proper data type handling
# Convert all columns to string to avoid type conversion issues
df_string = df.astype(str)  # ← Ensure all data is string
csv_buffer = io.StringIO()
df_string.to_csv(csv_buffer, index=False)
```

### **Expected Results**

**Before (Version 0.0.59 and earlier):**
```
📤 Uploading to Snowflake stage: @SALESFORCE_STAGE
❌ Error executing sync strategy: Failed to write DataFrame to stage @SALESFORCE_STAGE: 
("Could not convert '10' with type str: tried to convert to int64", 
'Conversion failed for column Store_Number__c with type object')
✅ Sync completed: 0 records in 75.10s
```

**After (Version 0.0.60):**
```
📤 Uploading to Snowflake stage: @SALESFORCE_STAGE
✅ Successfully uploaded to stage: @SALESFORCE_STAGE
📦 Processing batch 1: 1000 records
📦 Processing batch 2: 1000 records
...
✅ Sync completed: 404739 records in 120.45s
```

### **Impact**
- ✅ **No more data type conversion errors** when uploading to stages
- ✅ **Consistent string handling** for all CSV data
- ✅ **Proper stage uploads** for large datasets
- ✅ **Eliminates DtypeWarning** messages

### **Technical Details**
The fix ensures that:
1. **All CSV data is read as strings** (`dtype=str`)
2. **All DataFrame data is converted to strings** before writing (`df.astype(str)`)
3. **No type inference** that could cause conversion conflicts
4. **Consistent data handling** across all stage upload operations

### **Installation**
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht==0.0.60 --upgrade
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
# Should complete successfully without data type errors
```

---

**This fix resolves the data type conversion issues that were preventing successful stage uploads. Update to version 0.0.60 for reliable stage-based sync operations.** 