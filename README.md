# Lake House Tools (LHT) - Salesforce & Snowflake Integration

Bring Salesforce into the fold of your data cloud. LHT is a robust Python library that makes it really easy to extract data from Salesforce and reverse-extract your updates and transformations back into Salesforce. LHT uses Salesforce Bulk API 2.0 for all data synchronizations, providing efficient and consistent data extraction regardless of data volume.

## 🚀 Features

### Intelligent Synchronization
- **Bulk API 2.0**: All syncs use Salesforce Bulk API 2.0 for efficient data extraction
- **Incremental Sync**: Smart detection of changed records since last sync based on LastModifiedDate
- **Full Sync**: Complete data synchronization for first-time syncs

### Core Capabilities
- **Salesforce Bulk API 2.0**: Full support for bulk operations
- **Snowflake Integration**: Native Snowpark support
- **Data Type Mapping**: Automatic Salesforce to Snowflake type conversion
- **Error Handling**: Comprehensive error management and recovery
- **Performance Optimization**: Efficient processing for large datasets

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

## 🔧 How It Works

### Sync Strategy

LHT uses Salesforce Bulk API 2.0 for all synchronizations, providing consistent and efficient data extraction regardless of data volume.

**Full Sync (First-time)**
- Performed when the target table doesn't exist
- Extracts all records from the Salesforce object
- Creates the target table in Snowflake

**Incremental Sync**
- Performed when the target table already exists
- Queries `MAX(LASTMODIFIEDDATE)` from the existing table
- Extracts only records modified since the last sync
- Uses MERGE logic to update existing records and insert new ones

### Sync Process

1. **Check Table Existence**: Determines if target table exists
2. **Get Last Modified Date**: Queries `MAX(LASTMODIFIEDDATE)` from existing table (for incremental syncs)
3. **Create Bulk API 2.0 Job**: Creates a query job in Salesforce
4. **Process Batches**: Downloads and processes CSV batches from Salesforce
5. **Write to Temp Table**: Loads data into a temporary Snowflake table
6. **MERGE to Target**: Merges data from temp table to target table using match field
7. **Cleanup**: Removes temporary table and Bulk API job

## 💻 Command Line Interface

LHT provides a comprehensive CLI for managing connections and synchronizing data.

### Connection Management

**Create a Snowflake Connection**

```bash
lht create-connection --snowflake
```

Prompts for:
- Account identifier (e.g., `xy12345.us-east-1`)
- Username
- Role (e.g., `ACCOUNTADMIN`, `SYSADMIN`)
- Warehouse (e.g., `COMPUTE_WH`)
- Private key file path (PEM format for JWT authentication)
- Private key passphrase (optional)
- Database (optional, can be overridden)
- Schema (optional, can be overridden)
- Connection name
- Set as primary connection (y/n)

**Create a Salesforce Connection**

```bash
lht create-connection --salesforce
```

Prompts for:
- Client ID (from Connected App)
- Client Key/Secret (from Connected App)
- My Domain (e.g., `mycompany`)
- Sandbox (y/n)
- Redirect URL (optional)
- Connection name
- Set as primary connection (y/n)

**Note:** The CLI requires an External App configured for OAuth2.0 Client Credentials flow. See [Salesforce documentation](https://help.salesforce.com/s/articleView?id=xcloud.remoteaccess_oauth_client_credentials_flow.htm) for setup instructions.

**List Connections**

```bash
lht list-connections
```

**Set Primary Connection**

```bash
lht set-primary CONNECTION_NAME
```

Sets a connection as the primary/default connection. `lht` commands will default to the primary connection if one is set.

**Edit Connection**

```bash
lht edit-connection
```

**Test Connection**

```bash
lht connect CONNECTION_NAME
```

### Data Synchronization

**Sync Salesforce Object to Snowflake**

```bash
lht sync --sobject Account --table ACCOUNT
```

**Required Arguments:**
- `--sobject`: Salesforce object name (e.g., `Account`, `Contact`)
- `--table`: Snowflake table name

**Optional Arguments:**
- `--schema`: Snowflake schema (defaults to connection if available)
- `--database`: Snowflake database (defaults to connection if available)
- `--snowflake NAME`: Snowflake connection name (defaults to primary)
- `--salesforce NAME`: Salesforce connection name (defaults to primary)
- `--match-field FIELD`: Field to use for matching records (default: `ID`)
- `--use-stage`: Use Snowflake stage for large datasets
- `--stage-name STAGE`: Snowflake stage name (required if `--use-stage` is specified)
- `--force-full-sync`: Force a full sync regardless of previous sync status
- `--where WHERE_CLAUSE`: SOQL WHERE clause to filter records (e.g., `"IsPersonAccount = False"`)

**Examples:**

```bash
# Basic sync
lht sync --sobject Account --table ACCOUNT

# Sync with custom schema and database
lht sync --sobject Contact --table CONTACT --schema RAW --database SALESFORCE_DB

# Sync with WHERE clause filter
lht sync --sobject Account --table ACCOUNT --where "IsPersonAccount = False"

# Force full sync
lht sync --sobject Account --table ACCOUNT --force-full-sync

# Use specific connections
lht sync --sobject Account --table ACCOUNT --snowflake my_snowflake --salesforce my_salesforce
```

### Bulk API 2.0 Job Management

**List All Jobs**

```bash
lht list-jobs [--salesforce NAME] [--api-version VERSION]
```

Displays all Bulk API 2.0 query jobs with:
- Job ID
- Operation
- Object
- Created By
- Created Date
- State
- Concurrency Mode
- Content Type
- API Version
- Job Type

**Show Job Details**

```bash
lht show-job <JOB_ID> [--salesforce NAME] [--api-version VERSION]
```

Displays detailed information about a specific job including:
- Job ID, Operation, Object
- Created By, Created Date
- State, API Version, Job Type
- Number of Records Processed
- Retries
- Total Processing Time
- PK Chunking Support

**Delete Job**

```bash
lht delete-job <JOB_ID> [--salesforce NAME] [--api-version VERSION]
```

Deletes a specific Bulk API 2.0 job from Salesforce.

**Examples:**

```bash
# List all jobs
lht list-jobs

# Show details for a specific job
lht show-job 750xx000000abcDAAQ

# Delete a job
lht delete-job 750xx000000abcDAAQ
```

## 📚 Documentation

- **[Intelligent Sync Guide](docs/intelligent_sync_guide.md)**: Comprehensive guide to the intelligent sync system
- **[Salesforce Sync Guide](docs/salesforce_sync_guide.md)**: Detailed Salesforce synchronization guide
- **[API Documentation](docs/_build/html/index.html)**: Full API reference (build with `make html` in `docs/` directory)
- **[Examples](examples/)**: Complete working examples

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

### Bulk API 2.0 Benefits
- **Efficient Processing**: Processes data in batches, reducing memory usage
- **Scalability**: Handles datasets of any size efficiently
- **Consistency**: All syncs use the same method, ensuring predictable behavior
- **Built-in Retry Logic**: Automatic retry handling for transient failures

### Optimization Tips
- Use appropriate warehouse size for large datasets
- Consider using `--use-stage` for very large datasets
- Monitor Bulk API job status using `lht list-jobs` and `lht show-job`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
