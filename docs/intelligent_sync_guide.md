# Intelligent Salesforce Synchronization Guide

## Overview

The Intelligent Sync system orchestrates Salesforce data synchronization to Snowflake using Bulk API 2.0. The system automatically determines:

1. **Full vs Incremental Sync**: Based on whether the target table exists and has a LastModifiedDate value
2. **Stage Usage**: Optional use of Snowflake stages for large datasets when specified
3. **Data Processing**: Handles Salesforce data types and converts to Snowflake-compatible formats

**Note:** All synchronizations now use Salesforce Bulk API 2.0 exclusively. The regular API sync method has been removed for consistency and performance.

## How It Works

### Decision Matrix

The system uses the following logic to determine the sync method:

| Scenario | Method | Description |
|----------|--------|-------------|
| **First-time sync** (no stage) | `bulk_api_full` | Use Bulk API 2.0 for complete data extraction |
| **First-time sync** (with stage) | `bulk_api_stage_full` | Use Bulk API 2.0 with Snowflake stage |
| **Incremental sync** (no stage) | `bulk_api_incremental` | Use Bulk API 2.0 with MERGE logic for updates |
| **Incremental sync** (with stage) | `bulk_api_stage_incremental` | Use Bulk API 2.0 with stage and MERGE logic |

### Configuration

The system no longer uses threshold-based API selection. All syncs use Bulk API 2.0. You can still configure:

- **Stage usage**: Enable with `use_stage=True` and provide `stage_name`
- **Full sync**: Force with `force_full_sync=True`
- **WHERE clause**: Filter records with `where_clause` parameter

## Usage

### Simple Usage

```python
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Account",
    schema="RAW",
    table="ACCOUNTS",
    match_field="ID"
)
```

### Advanced Usage with Stage

```python
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Contact",
    schema="RAW",
    table="CONTACTS",
    match_field="ID",
    use_stage=True,
    stage_name="@SALESFORCE_STAGE"
)
```

### Force Full Sync

```python
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Account",
    schema="RAW",
    table="ACCOUNTS",
    match_field="ID",
    force_full_sync=True  # Overwrites entire table
)
```

## Sync Methods Explained

### Bulk API 2.0 Methods

**Use cases**: All datasets (small to very large)

**Advantages**:
- Consistent performance across all data volumes
- Handles large datasets efficiently
- Better performance for bulk operations
- Built-in retry logic
- Asynchronous processing
- Job management and monitoring

**Disadvantages**:
- Requires job management
- Asynchronous processing (not real-time)

### Stage-Based Methods

**Use cases**: Very large datasets in Snowflake Notebooks or when stage is preferred

**Advantages**:
- Handles massive datasets efficiently
- Better memory management
- Leverages Snowflake's stage capabilities
- Direct file uploads

**Disadvantages**:
- Requires stage setup
- Additional complexity
- Snowflake-specific

## Incremental Sync Logic

### How It Works

1. **Check Table Existence**: Determines if target table exists
2. **Get Last Modified Date**: Queries `MAX(LASTMODIFIEDDATE)` from existing table (if table exists)
3. **Estimate Record Count**: Counts records modified since last sync (for incremental)
4. **Determine Strategy**: Selects full vs incremental, and stage vs non-stage
5. **Execute Sync**: Runs Bulk API 2.0 sync with appropriate method

### Example Flow

```python
# First sync (table doesn't exist)
result = sync_sobject_intelligent(session, access_info, "Account", "RAW", "ACCOUNTS")
# Result: Uses bulk_api_full or bulk_api_stage_full (if use_stage=True)

# Subsequent syncs (table exists)
result = sync_sobject_intelligent(session, access_info, "Account", "RAW", "ACCOUNTS")
# Result: Uses bulk_api_incremental or bulk_api_stage_incremental (if use_stage=True)
# Automatically filters for records where LastModifiedDate > MAX(LastModifiedDate) from table
```

## Return Values

The sync functions return a dictionary with detailed information:

```python
{
    'sobject': 'Account',
    'target_table': 'RAW.ACCOUNTS',
    'sync_method': 'bulk_api_incremental',
    'estimated_records': 1500,
    'actual_records': 1487,
    'sync_duration_seconds': 45.23,
    'last_modified_date': Timestamp('2024-01-15 10:30:00'),
    'sync_timestamp': Timestamp('2024-01-16 14:20:00'),
    'success': True,
    'error': None
}
```

## Error Handling

The system includes comprehensive error handling:

- **Authentication errors**: Invalid Salesforce credentials
- **Network errors**: Connection issues
- **Job failures**: Bulk API job failures
- **Data errors**: Malformed data or schema issues

Errors are captured in the return value:

```python
{
    'success': False,
    'error': 'Bulk API job failed with state: Failed',
    'records_processed': 0
}
```

## Best Practices

### 1. Environment Setup

```python
# Create stage for large datasets
session.sql("CREATE OR REPLACE STAGE @SALESFORCE_STAGE").collect()

# Set appropriate warehouse size
session.sql("USE WAREHOUSE LARGE_WH").collect()
```

### 2. Monitoring

```python
# Monitor sync results
results = []
for sobject in ['Account', 'Contact', 'Opportunity']:
    result = sync_sobject_intelligent(session, access_info, sobject, "RAW", f"{sobject.upper()}S")
    results.append(result)
    
    if not result['success']:
        print(f"❌ Failed to sync {sobject}: {result['error']}")
```

### 3. Scheduling

```python
# For regular syncs, use incremental mode
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Account",
    schema="RAW",
    table="ACCOUNTS",
    match_field="ID"
)

# For data refresh, use force_full_sync
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Account",
    schema="RAW",
    table="ACCOUNTS",
    match_field="ID",
    force_full_sync=True
)
```

## Troubleshooting

### Common Issues

1. **"Table doesn't exist" error**
   - Ensure the schema exists
   - Check table name spelling
   - Verify permissions

2. **"Bulk API job failed"**
   - Check Salesforce API limits
   - Verify query syntax
   - Monitor job status manually

3. **"Stage not found" error**
   - Create the stage first
   - Check stage name spelling
   - Verify stage permissions

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Sync with detailed output
result = sync_sobject_intelligent(session, access_info, "Account", "RAW", "ACCOUNTS")
```

## Performance Considerations

### Memory Usage

- **Bulk API 2.0**: Processes in batches, efficient memory usage
- **Stage-based**: Minimal memory usage, direct file uploads

### Network Usage

- **Bulk API 2.0**: Fewer, larger API calls, efficient data transfer
- **Stage-based**: Direct file uploads to Snowflake stage

### Processing Time

- **All datasets**: Bulk API 2.0 provides consistent performance
- **Large datasets**: Stage-based methods offer optimal performance for very large volumes

## Migration from Existing Code

### Before (Manual Method Selection)

```python
# Old way - manual decision making
if record_count > 10000:
    # Use Bulk API
    job_id = create_batch_query(access_info, query)
    get_bulk_results(session, access_info, job_id, sobject, schema, table)
else:
    # Use regular API (now removed)
    for batch in query_records(access_info, query):
        session.write_pandas(batch, f"{schema}.{table}")
```

### After (Intelligent Sync - Bulk API 2.0 Only)

```python
# New way - automatic sync orchestration with Bulk API 2.0
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject=sobject,
    schema=schema,
    table=table
)
# All syncs now use Bulk API 2.0 automatically
```

## Advanced Configuration

### Stage Configuration

```python
# Enable stage-based loading for large datasets
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Account",
    schema="RAW",
    table="ACCOUNTS",
    use_stage=True,
    stage_name="@SALESFORCE_STAGE"
)
```

### Custom Match Fields

```python
# For custom objects or different matching logic
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="CustomObject__c",
    schema="RAW",
    table="CUSTOM_OBJECTS",
    match_field="External_Id__c"  # Use custom field for matching
)
```

This intelligent sync system provides a robust, automated solution for Salesforce data synchronization that adapts to your data volume and environment requirements. 