# LHT Package Release 0.0.50

## 🚀 Published to Test PyPI
**Package:** `lht`  
**Version:** `0.0.50`  
**Repository:** https://test.pypi.org/project/lht/0.0.50/

## 🔧 Major Fix: Snowflake Notebook Stage Writing

### Problem Solved
Fixed ephemeral storage issues in Snowflake notebook environments where temporary files were being created and then cleaned up before they could be uploaded to Snowflake stages.

### Changes Made

#### 1. Enhanced `src/lht/util/stage.py`
- **Added:** `put_dataframe_to_stage()` - Writes DataFrames directly to Snowflake stages
- **Added:** `put_csv_content_to_stage()` - Writes CSV content directly to Snowflake stages
- **Improved:** Uses `COPY INTO @stage FROM temp_table` instead of `PUT file://`

#### 2. Updated `src/lht/salesforce/query_bapi20.py`
- **Modified:** `get_bulk_results_with_stage()` - Now uses direct stage writing
- **Modified:** `get_bulk_results()` - Now uses direct stage writing  
- **Removed:** All temporary file operations (`field_types.cache_data()`)
- **Added:** Memory-based CSV processing using `io.StringIO()`

### Key Benefits
- ✅ **No ephemeral storage dependency** - Works reliably in Snowflake notebooks
- ✅ **Memory efficient** - Data flows directly from memory to Snowflake stage
- ✅ **Cleaner code** - Removed file system operations and cleanup logic
- ✅ **Better error handling** - Proper cleanup of temporary tables on errors
- ✅ **Transparent to existing code** - No changes needed to existing sync calls

### Technical Implementation
The new approach uses Snowflake's `COPY INTO` command with a temporary table:
1. Write DataFrame to a temporary Snowflake table
2. Use `COPY INTO @stage/filename FROM temp_table` to copy data to stage
3. Clean up the temporary table
4. Handle errors with proper cleanup

## 📦 Installation from Test PyPI

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht==0.0.50
```

## 🧪 Testing

The package includes test scripts to verify functionality:
- `snowflake_notebook_test.py` - Tests direct stage writing in notebook environments
- `test_stage_direct_write.py` - Tests the new stage writing functions

## 🔄 Usage

No changes required to existing code:

```python
# This will now work reliably in Snowflake notebooks
result = sync_sobject_intelligent(
    session, 
    access_info, 
    'Account', 
    'RAW', 
    'ACCOUNT', 
    use_stage=True, 
    stage_name='SALESFORCE_STAGE'
)
```

## 📋 Files Changed
- `src/lht/util/stage.py` - Added direct stage writing functions
- `src/lht/salesforce/query_bapi20.py` - Updated to use direct stage writing
- `pyproject.toml` - Updated version to 0.0.50

## 🎯 Next Steps
1. Test the package in your Snowflake notebook environment
2. Verify that stage uploads work without ephemeral storage issues
3. If testing is successful, consider publishing to production PyPI 