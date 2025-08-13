# Lake House Tools (LHT) - Salesforce & Snowflake Integration

A comprehensive Python library for intelligent data synchronization between Salesforce and Snowflake, featuring automated method selection based on data volume and previous sync status.

## 🚀 Features

### Intelligent Synchronization
- **Automatic Method Selection**: Choose the best sync method based on data volume
- **Incremental Sync**: Smart detection of changed records since last sync
- **Bulk API 2.0 Integration**: Efficient handling of large datasets
- **Snowflake Stage Support**: Optimized for Snowflake Notebook environments

### Core Capabilities
- **Salesforce Bulk API 2.0**: Full support for bulk operations
- **Snowflake Integration**: Native Snowpark support
- **Data Type Mapping**: Automatic Salesforce to Snowflake type conversion
- **Error Handling**: Comprehensive error management and recovery
- **Performance Optimization**: Stage-based processing for large datasets

## 📦 Installation

```bash
pip install lht
```

## 🎯 Quick Start

### Basic Intelligent Sync

```python
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

# Sync Account object intelligently
result = sync_sobject_intelligent(
    session=session,
    access_info=access_info,
    sobject="Account",
    schema="RAW",
    table="ACCOUNTS",
    match_field="ID"
)

print(f"Synced {result['actual_records']} records using {result['sync_method']}")
```

### Advanced Sync with Stage

```python
# For large datasets in Snowflake Notebooks
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

## 🔧 How It Works

### Decision Matrix

The system automatically selects the optimal sync method:

| Scenario | Records | Method | Description |
|----------|---------|--------|-------------|
| **First-time sync** | < 1,000 | `regular_api_full` | Use regular Salesforce API |
| **First-time sync** | 1,000 - 49,999 | `bulk_api_full` | Use Bulk API 2.0 |
| **First-time sync** | ≥ 50,000 | `bulk_api_stage_full` | Use Bulk API 2.0 with Snowflake stage |
| **Incremental sync** | < 1,000 | `regular_api_incremental` | Use regular API with merge logic |
| **Incremental sync** | 1,000 - 49,999 | `bulk_api_incremental` | Use Bulk API 2.0 |
| **Incremental sync** | ≥ 50,000 | `bulk_api_stage_incremental` | Use Bulk API 2.0 with stage |

### Incremental Sync Logic

1. **Check Table Existence**: Determines if target table exists
2. **Get Last Modified Date**: Queries `MAX(LASTMODIFIEDDATE)` from existing table
3. **Estimate Record Count**: Counts records modified since last sync
4. **Choose Method**: Selects appropriate sync method based on count
5. **Execute Sync**: Runs the chosen method

## 📚 Documentation

- **[Intelligent Sync Guide](docs/intelligent_sync_guide.md)**: Comprehensive guide to the intelligent sync system
- **[Snowflake Stage Integration](docs/snowflake_stage_integration.md)**: Stage-based processing documentation
- **[Examples](examples/)**: Complete working examples

## 🔄 Sync Methods

### 1. Regular API Methods
- **Use cases**: Small datasets (< 1,000 records)
- **Advantages**: Fast for small datasets, real-time processing
- **Disadvantages**: API rate limits, memory intensive

### 2. Bulk API 2.0 Methods
- **Use cases**: Medium to large datasets (1,000+ records)
- **Advantages**: Handles large datasets efficiently, built-in retry logic
- **Disadvantages**: Requires job management, asynchronous processing

### 3. Stage-Based Methods
- **Use cases**: Very large datasets (50,000+ records) in Snowflake Notebooks
- **Advantages**: Handles massive datasets, better memory management
- **Disadvantages**: Requires stage setup, Snowflake-specific

## 🛠️ Configuration

### Custom Thresholds

```python
from lht.salesforce.intelligent_sync import IntelligentSync

sync_system = IntelligentSync(session, access_info)
sync_system.BULK_API_THRESHOLD = 5000    # Use Bulk API for 5K+ records
sync_system.STAGE_THRESHOLD = 25000      # Use stage for 25K+ records
```

### Environment Setup

```python
# Create stage for large datasets
session.sql("CREATE OR REPLACE STAGE @SALESFORCE_STAGE").collect()

# Set appropriate warehouse size
session.sql("USE WAREHOUSE LARGE_WH").collect()
```

## 📊 Return Values

Sync functions return detailed information:

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

## 🚨 Error Handling

The system includes comprehensive error handling for:
- Authentication errors
- Network issues
- Job failures
- Data errors

Errors are captured in the return value:

```python
{
    'success': False,
    'error': 'Bulk API job failed with state: Failed',
    'records_processed': 0
}
```

## 🔧 Advanced Usage

### Multiple Object Sync

```python
objects_to_sync = [
    {"sobject": "Account", "table": "ACCOUNTS"},
    {"sobject": "Contact", "table": "CONTACTS"},
    {"sobject": "Opportunity", "table": "OPPORTUNITIES"}
]

results = []
for obj in objects_to_sync:
    result = sync_sobject_intelligent(
        session=session,
        access_info=access_info,
        sobject=obj['sobject'],
        schema="RAW",
        table=obj['table'],
        match_field="ID"
    )
    results.append(result)
```

### Force Full Sync

```python
# Useful for data refresh or after schema changes
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

## 📈 Performance Considerations

### Memory Usage
- **Regular API**: Loads all data in memory
- **Bulk API**: Processes in batches
- **Stage-based**: Minimal memory usage

### Processing Time
- **Small datasets** (< 1K): Regular API fastest
- **Medium datasets** (1K-50K): Bulk API optimal
- **Large datasets** (> 50K): Stage-based best

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Documentation

- **[PyPI Upload Guide](UPLOAD_README.md)**: Instructions for uploading to PyPI
- **[NPI App Documentation](apps/npi/README_NPI_APP.md)**: NPI Streamlit application guide