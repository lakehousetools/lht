# COUNT Query Fix for Intelligent Sync

## Problem
The `_estimate_record_count` method in `intelligent_sync.py` was throwing a "list index out of range" error when trying to access `result['records'][0]['expr0']` from Salesforce API responses.

## Root Cause
The error occurred because:
1. The code expected `result['records']` to always contain at least one record
2. For COUNT queries, Salesforce sometimes returns an empty `records` array
3. The code didn't properly handle different response structures from Salesforce

## Solution Implemented

### 1. Fixed COUNT Query Syntax
- **Before:** `SELECT COUNT() FROM {sobject}`
- **After:** `SELECT COUNT(Id) FROM {sobject}`
- This ensures more consistent response structure from Salesforce

### 2. Improved Response Handling
Added robust error handling that checks multiple possible response structures:

```python
# Check for totalSize (most common for COUNT queries)
if 'totalSize' in result and result['totalSize'] > 0:
    count = result['totalSize']
    return count

# Check for records array with count
if 'records' in result and len(result['records']) > 0:
    first_record = result['records'][0]
    # Try different possible field names for count
    count_fields = ['expr0', 'count', 'COUNT', 'count__c', 'Id']
    for field in count_fields:
        if field in first_record:
            count = first_record[field]
            return count
```

### 3. Enhanced Error Handling
- Added comprehensive logging to understand response structure
- Added fallback to conservative estimates when count can't be determined
- Added response debugging information in error cases

### 4. Better Debugging
- Logs response structure when count can't be found
- Shows available fields in unexpected record structures
- Provides detailed error information for troubleshooting

## Key Improvements

1. **No More Index Errors:** Properly checks array length before accessing elements
2. **Multiple Field Support:** Tries different possible field names for count values
3. **Graceful Degradation:** Falls back to conservative estimates when count can't be determined
4. **Better Debugging:** Provides detailed logging for troubleshooting
5. **Robust Handling:** Works with various Salesforce API response structures

## Testing

The fix has been tested with various response structures:
- ✅ Standard `totalSize` responses
- ✅ Records array with `expr0` field
- ✅ Records array with different field names
- ✅ Empty records arrays (the problematic case)
- ✅ Error responses

## Files Changed
- `src/lht/salesforce/intelligent_sync.py` - Updated `_estimate_record_count` method
- `test_count_query_fix.py` - Added test script to verify the fix

## Usage
No changes required to existing code. The fix is transparent and will prevent the "list index out of range" error while providing better debugging information. 