# Intelligent Salesforce Synchronization Guide

## Overview

The Intelligent Sync system automatically determines the best method to synchronize Salesforce data to Snowflake based on:

1. **Data Volume**: Number of records to be synced
2. **Previous Sync Status**: Whether the table exists and when it was last synced
3. **Environment**: Whether running in Snowflake Notebooks with stage access

## How It Works

### Decision Matrix

The system uses the following logic to determine the sync method:

| Scenario | Records | Method | Description |
|----------|---------|--------|-------------|
| **First-time sync** | < 1,000 | `regular_api_full` | Use regular Salesforce API |
| **First-time sync** | 1,000 - 49,999 | `bulk_api_full` | Use Bulk API 2.0 |
| **First-time sync** | ≥ 50,000 | `bulk_api_stage_full` | Use Bulk API 2.0 with Snowflake stage |
| **Incremental sync** | < 1,000 | `regular_api_incremental` | Use regular API with merge logic |
| **Incremental sync** | 1,000 - 49,999 | `bulk_api_incremental` | Use Bulk API 2.0 |
| **Incremental sync** | ≥ 50,000 | `bulk_api_stage_incremental` | Use Bulk API 2.0 with stage |

### Thresholds

You can customize the thresholds in the `IntelligentSync` class:

```python
sync_system = IntelligentSync(session, access_info)
sync_system.BULK_API_THRESHOLD = 5000    # Use Bulk API for 5K+ records
sync_system.STAGE_THRESHOLD = 25000      # Use stage for 25K+ records
```

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

### 1. Regular API Methods

**Use cases**: Small datasets (< 1,000 records)

**Advantages**:
- Fast for small datasets
- Real-time processing
- No job management required

**Disadvantages**:
- API rate limits
- Slower for large datasets
- Memory intensive

### 2. Bulk API 2.0 Methods

**Use cases**: Medium to large datasets (1,000+ records)

**Advantages**:
- Handles large datasets efficiently
- Better performance for bulk operations
- Built-in retry logic

**Disadvantages**:
- Requires job management
- Asynchronous processing
- More complex error handling

### 3. Stage-Based Methods

**Use cases**: Very large datasets (50,000+ records) in Snowflake Notebooks

**Advantages**:
- Handles massive datasets
- Better memory management
- Leverages Snowflake's stage capabilities

**Disadvantages**:
- Requires stage setup
- Additional complexity
- Snowflake-specific

## Incremental Sync Logic

### How It Works

1. **Check Table Existence**: Determines if target table exists
2. **Get Last Modified Date**: Queries `MAX(LASTMODIFIEDDATE)` from existing table
3. **Estimate Record Count**: Counts records modified since last sync
4. **Choose Method**: Selects appropriate sync method based on count
5. **Execute Sync**: Runs the chosen method

### Example Flow

```python
# First sync (table doesn't exist)
result = sync_sobject_intelligent(session, access_info, "Account", "RAW", "ACCOUNTS")
# Result: Uses bulk_api_full or bulk_api_stage_full

# Subsequent syncs (table exists)
result = sync_sobject_intelligent(session, access_info, "Account", "RAW", "ACCOUNTS")
# Result: Uses incremental method based on changed record count
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

- **Regular API**: Loads all data in memory
- **Bulk API**: Processes in batches
- **Stage-based**: Minimal memory usage

### Network Usage

- **Regular API**: Multiple API calls
- **Bulk API**: Fewer, larger calls
- **Stage-based**: Direct file uploads

### Processing Time

- **Small datasets** (< 1K): Regular API fastest
- **Medium datasets** (1K-50K): Bulk API optimal
- **Large datasets** (> 50K): Stage-based best

## Migration from Existing Code

### Before (Manual Method Selection)

```python
# Old way - manual decision making
if record_count > 10000:
    # Use Bulk API
    job_id = create_batch_query(access_info, query)
    get_bulk_results(session, access_info, job_id, sobject, schema, table)
else:
    # Use regular API
    for batch in query_records(access_info, query):
        session.write_pandas(batch, f"{schema}.{table}")
```

### After (Intelligent Sync)

```python
# New way - automatic method selection
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject=sobject,
    schema=schema,
    table=table
)
```

## Advanced Configuration

### Custom Thresholds

```python
sync_system = IntelligentSync(session, access_info)

# Adjust for your environment
sync_system.BULK_API_THRESHOLD = 2000   # More aggressive Bulk API usage
sync_system.STAGE_THRESHOLD = 10000     # Earlier stage usage
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