# Lake House Tools (LHT) - Salesforce & Snowflake Integration

Bring Salesforce into the fold of your data cloud. LHT is a robust Python library that makes it really easy to extract data from Salesforce and reverse-extract your updates and transformations back into Salesforce.

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

### Prerequisites

#### 1. Salesforce Setup

**Option A: Developer Org (Recommended for Testing)**
- Sign up for a [Salesforce Developer Org](https://developer.salesforce.com/signup) (free)
- **Important**: Developer Pro or above is preferred for testing LHT
- **Do NOT use your production Salesforce instance or production data**

**Option B: Trial Org**
- Sign up for a [Salesforce Trial](https://www.salesforce.com/trailhead/) (free)
- Choose a trial that includes the features you want to test

**Option C: Sandbox**
- If you have a Developer Pro+ license, create a sandbox from your production org
- **Never test LHT in production**

**⚠️ Critical Requirements:**
- **Administrative access** to the Salesforce instance

**🔧 OAuth2.0 Setup Required:**
1. **Configure a Connected App** for the OAuth2.0 Client Credentials Flow
   - [Detailed Connected App Setup Instructions](https://help.salesforce.com/s/articleView?id=xcloud.connected_app_client_credentials_setup.htm&type=5)
   - **Callback URL**: Enter `https://localhost/callback` (not used in this flow but required)
   - **Scopes**: Add "Full" scopes for testing (modify for production use)
2. **Retrieve Credentials**: Once configured, get the Client ID and Client Secret and store them securely
3. **Get Your Domain**: From Setup, search for "My Domain" and copy the subdomain (everything before '.my.salesforce.com')
   - **Note**: Sandbox instances will include 'sandbox' in the subdomain
4. **Store Securely**: Keep Client ID, Client Secret, and subdomain together - you'll need them for LHT configuration

**🚨 Salesforce Limitations:**
Since Salesforce was never really architected to deal with any meaningful amount of data, there will be limitations on what you can do:
- **API rate limits**: 15,000 API calls per 24-hour period (Enterprise), 100,000 (Unlimited)
- **Bulk API limits**: 10,000 records per batch, 10 concurrent jobs
- **Query limits**: SOQL queries limited to 50,000 records
- **Storage limits**: Varies by org type and edition
  - [Salesforce Storage Limits](https://help.salesforce.com/s/articleView?id=xcloud.overview_storage.htm&type=5)
  - [Sandbox Storage Limits](https://help.salesforce.com/s/articleView?id=platform.data_sandbox_environments.htm&type=5)

**This is why we introduced LHT** - to bridge these limitations and provide robust data integration capabilities.



#### 2. Snowflake Setup

**Free Trial Registration:**
- Sign up for a [Snowflake free trial](https://www.snowflake.com/free-trial/) (free)
- Choose a cloud provider (AWS, Azure, or GCP)
- Select a region close to your Salesforce org

**⚠️ Critical Requirements:**
- **Account Admin privileges** (required for initial setup)
- **Security Admin privileges** (required for user and role management)
- **Database creation permissions**
- **Warehouse creation permissions**
- **Stage creation permissions**

**🔑 Minimum Snowflake Roles Needed:**
```sql
-- Account Admin (automatically granted)
-- Security Admin
-- Database Admin
-- Warehouse Admin
```

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
    schema="WAREHOUSE",
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
