# Stage Direct Write Fix for Snowflake Notebooks

## Problem
The original implementation was creating temporary files on the local filesystem and then using Snowflake's `PUT` command to upload them to the stage. However, in a Snowflake notebook environment, there's no persistent local filesystem - the temporary files are created in ephemeral storage that gets cleaned up, causing the upload to fail.

## Solution
Modified the code to write data directly to Snowflake stages without using temporary files by:

1. **Added new functions to `src/lht/util/stage.py`:**
   - `put_dataframe_to_stage()`: Writes a DataFrame directly to a Snowflake stage
   - `put_csv_content_to_stage()`: Writes CSV content directly to a Snowflake stage

2. **Updated `src/lht/salesforce/query_bapi20.py`:**
   - Modified `get_bulk_results_with_stage()` to use direct stage writing
   - Modified `get_bulk_results()` to use direct stage writing
   - Removed all temporary file operations
   - Added proper CSV content handling using `io.StringIO`

## Key Changes

### New Functions in `stage.py`

```python
def put_dataframe_to_stage(session, stage_name, df, filename=None):
    """
    Write a DataFrame directly to a Snowflake stage without using temporary files.
    Uses a temporary table approach with COPY INTO command.
    """

def put_csv_content_to_stage(session, stage_name, csv_content, filename=None):
    """
    Write CSV content directly to a Snowflake stage without using temporary files.
    Converts CSV string to DataFrame and uses the DataFrame method.
    """
```

### Updated Functions in `query_bapi20.py`

- **Before:** Created temporary files using `field_types.cache_data()`
- **After:** Process CSV content directly from memory using `io.StringIO()`

- **Before:** Used `stage.put_file()` with temporary file paths
- **After:** Used `stage.put_csv_content_to_stage()` with CSV content strings

## Benefits

1. **No Ephemeral Storage Dependency:** Works reliably in Snowflake notebook environments
2. **Memory Efficient:** Data flows directly from memory to Snowflake stage
3. **Cleaner Code:** Removed file system operations and cleanup logic
4. **Better Error Handling:** Proper cleanup of temporary tables on errors
5. **Consistent Approach:** Both stage and non-stage modes use the same data flow

## Usage

The fix is transparent to existing code. When using stage-based sync:

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

## Technical Details

The new approach uses Snowflake's `COPY INTO` command with a temporary table:

1. Write DataFrame to a temporary Snowflake table
2. Use `COPY INTO @stage/filename FROM temp_table` to copy data to stage
3. Clean up the temporary table
4. Handle errors with proper cleanup

This ensures data integrity while avoiding filesystem dependencies. 