# Salesforce to Snowflake Synchronization Guide

This guide explains how to synchronize Salesforce SObjects to Snowflake using the LHT package in a Snowflake notebook environment.

## Prerequisites

- ✅ Snowflake notebook environment with LHT package installed
- ✅ Salesforce access token (`access_info`) already established
- ✅ Snowflake session (`session`) already configured
- ✅ Appropriate Snowflake permissions (CREATE TABLE, INSERT, etc.)

## Quick Start

### Basic Synchronization

```python
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

# Perform intelligent synchronization
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE',
    match_field='ID'
)

print(f"Sync completed: {result}")
```

### What Happens Automatically

1. **Sync Strategy Selection**: System determines whether to perform full or incremental sync
2. **API Selection**: Chooses between Regular API, Bulk API 2.0, or Stage-based loading
3. **Data Processing**: Handles Salesforce data types and converts to Snowflake-compatible formats
4. **Table Management**: Creates/updates tables with proper schemas
5. **Data Loading**: Loads data into Snowflake with error handling

## Configuration Options

### Basic Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session` | SnowparkSession | Yes | Active Snowflake session |
| `access_info` | dict | Yes | Salesforce access token/credentials |
| `sobject` | str | Yes | Salesforce SObject name (e.g., 'Account', 'Invoice__c') |
| `schema` | str | Yes | Snowflake schema name |
| `table` | str | Yes | Snowflake table name |
| `match_field` | str | No | Field for record matching (default: 'ID') |

### Advanced Parameters

```python
from lht.salesforce.intelligent_sync import IntelligentSync

# Create sync instance with custom configuration
sync = IntelligentSync(session, sf_token)

# Configure thresholds
sync.BULK_API_THRESHOLD = 5000      # Use Bulk API for >= 5000 records
sync.REGULAR_API_THRESHOLD = 500    # Use Regular API for >= 500 records
sync.STAGE_THRESHOLD = 25000        # Use Stage for >= 25000 records

# Perform sync with custom settings
result = sync.sync_sobject(
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE',
    match_field='ID',
    use_stage=False,              # Force non-stage loading
    force_full_sync=False         # Force full sync regardless of last sync
)
```

## Sync Methods

### 1. Intelligent Sync (Recommended)

```python
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE'
)
```

**Features:**
- Automatically selects best sync method based on data volume
- Handles incremental vs. full sync decisions
- Chooses appropriate Salesforce API (Regular vs. Bulk API 2.0)
- Manages temporary tables and data merging

### 2. Direct Bulk API 2.0

```python
from lht.salesforce.query_bapi20 import SalesforceBulkAPI20

# Create Bulk API handler
bulk_api = SalesforceBulkAPI20(session, sf_token)

# Query and load data directly
result = bulk_api.query_and_load(
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE',
    query_fields=['Id', 'Name', 'Amount__c', 'CreatedDate'],
    where_clause="CreatedDate >= 2023-01-01"
)
```

**Use Cases:**
- Large datasets (>10,000 records)
- Custom SOQL queries
- Specific date ranges or filters
- Direct table creation with custom schema

### 3. Stage-Based Loading

```python
from lht.salesforce.intelligent_sync import IntelligentSync

sync = IntelligentSync(session, sf_token)

# Force stage-based loading for very large datasets
result = sync.sync_sobject(
    sobject='Account',
    schema='SALESFORCE',
    table='ACCOUNT',
    use_stage=True,
    stage_name='@SALESFORCE_STAGE'
)
```

**Use Cases:**
- Very large datasets (>50,000 records)
- When you want to use Snowflake stages
- Better performance for massive data loads

## Data Type Handling

### Automatic Type Conversion

The system automatically handles Salesforce data types:

| Salesforce Type | Snowflake Type | Notes |
|-----------------|----------------|-------|
| `string` | `VARCHAR(16777216)` | Text fields, IDs, references |
| `int` | `NUMBER(38,0)` | Integer fields |
| `double` | `DOUBLE` | Decimal/numeric fields |
| `boolean` | `BOOLEAN` | True/false fields |
| `datetime` | `TIMESTAMP_NTZ` | Date/time fields |
| `date` | `VARCHAR` | Date-only fields (as strings) |

### Custom Type Handling

```python
from lht.util.field_types import format_sync_file

# Force all datetime fields to be strings (VARCHAR)
formatted_df = format_sync_file(
    df, 
    df_fields, 
    force_datetime_to_string=True
)
```

## Error Handling and Debugging

### Enable SQL Debug Output

```python
from lht.salesforce.intelligent_sync import set_sql_debug_mode

# Enable detailed SQL logging
set_sql_debug_mode(True)

# Run your sync
result = sync_sobject_intelligent(...)

# Disable debug when done
set_sql_debug_mode(False)
```

### Handle Specific Errors

```python
try:
    result = sync_sobject_intelligent(
        session=session,
        access_info=sf_token,
        sobject='Invoice__c',
        schema='SALESFORCE',
        table='INVOICE'
    )
    print(f"✅ Sync successful: {result}")
    
except Exception as e:
    print(f"❌ Sync failed: {e}")
    
    # Check specific error types
    if "Failed to cast variant value" in str(e):
        print("💡 Data type casting issue - try force_datetime_to_string=True")
    elif "Table does not exist" in str(e):
        print("💡 Table creation issue - check permissions")
    elif "Authentication failed" in str(e):
        print("💡 Salesforce token issue - refresh credentials")
```

## Common Use Cases

### 1. Full SObject Sync

```python
# Sync entire SObject (creates table if it doesn't exist)
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Account',
    schema='SALESFORCE',
    table='ACCOUNT'
)
```

### 2. Incremental Sync

```python
# System automatically detects last sync and only syncs changes
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Contact',
    schema='SALESFORCE',
    table='CONTACT'
)
```

### 3. Custom Field Selection

```python
from lht.salesforce.sobjects import SalesforceSObject

# Get SObject metadata
sobject = SalesforceSObject(sf_token)
fields = sobject.describe('Invoice__c')

# Filter to specific fields
custom_fields = [f for f in fields if f['custom']]
print(f"Custom fields: {[f['name'] for f in custom_fields]}")
```

### 4. Scheduled Syncs

```python
import schedule
import time

def sync_invoices():
    try:
        result = sync_sobject_intelligent(
            session=session,
            access_info=sf_token,
            sobject='Invoice__c',
            schema='SALESFORCE',
            table='INVOICE'
        )
        print(f"✅ Scheduled sync completed: {result}")
    except Exception as e:
        print(f"❌ Scheduled sync failed: {e}")

# Schedule sync every hour
schedule.every().hour.do(sync_invoices)

# Keep running
while True:
    schedule.run_pending()
    time.sleep(60)
```

## Performance Optimization

### 1. Batch Size Control

```python
from lht.util.data_writer import DataWriter

# Configure batch sizes
writer = DataWriter(session)
writer.BATCH_SIZE = 5000  # Process 5000 records at a time
```

### 2. Warehouse Selection

```python
# Use larger warehouse for big syncs
session.sql("USE WAREHOUSE LARGE_WH").collect()

# Run sync
result = sync_sobject_intelligent(...)

# Return to default warehouse
session.sql("USE WAREHOUSE DEFAULT_WH").collect()
```

### 3. Parallel Processing

```python
# Sync multiple SObjects in parallel
import concurrent.futures

sobjects = ['Account', 'Contact', 'Opportunity', 'Invoice__c']

def sync_sobject(sobject_name):
    return sync_sobject_intelligent(
        session=session,
        access_info=sf_token,
        sobject=sobject_name,
        schema='SALESFORCE',
        table=sobject_name.upper()
    )

# Run parallel syncs
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(sync_sobject, name): name for name in sobjects}
    
    for future in concurrent.futures.as_completed(futures):
        sobject_name = futures[future]
        try:
            result = future.result()
            print(f"✅ {sobject_name} sync completed: {result}")
        except Exception as e:
            print(f"❌ {sobject_name} sync failed: {e}")
```

## Monitoring and Logging

### Check Sync Status

```python
# Check if table exists and has data
def check_sync_status(schema, table):
    try:
        # Check table existence
        table_check = session.sql(f"SHOW TABLES IN SCHEMA {schema}").collect()
        table_exists = any(row['name'] == table for row in table_check)
        
        if table_exists:
            # Check record count
            count_result = session.sql(f"SELECT COUNT(*) as record_count FROM {schema}.{table}").collect()
            record_count = count_result[0]['record_count']
            print(f"✅ Table {schema}.{table} exists with {record_count} records")
            return True
        else:
            print(f"❌ Table {schema}.{table} does not exist")
            return False
            
    except Exception as e:
        print(f"❌ Error checking sync status: {e}")
        return False

# Check your sync
check_sync_status('SALESFORCE', 'INVOICE')
```

### View Sync History

```python
# Check last modified dates
def get_last_sync_info(schema, table):
    try:
        query = f"""
        SELECT 
            MAX(CREATEDDATE) as last_created,
            MAX(LASTMODIFIEDDATE) as last_modified,
            COUNT(*) as total_records
        FROM {schema}.{table}
        """
        result = session.sql(query).collect()
        
        if result:
            row = result[0]
            print(f"📊 {schema}.{table} Sync Info:")
            print(f"   Last Created: {row['last_created']}")
            print(f"   Last Modified: {row['last_modified']}")
            print(f"   Total Records: {row['total_records']}")
        
    except Exception as e:
        print(f"❌ Error getting sync info: {e}")

get_last_sync_info('SALESFORCE', 'INVOICE')
```

## Troubleshooting

### Common Issues and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Data Type Casting** | "Failed to cast variant value" | Use `force_datetime_to_string=True` |
| **Authentication** | "Invalid session" | Refresh Salesforce token |
| **Permissions** | "Insufficient privileges" | Check Snowflake role permissions |
| **Table Not Found** | "Table does not exist" | Ensure schema exists and check permissions |
| **Memory Issues** | "Out of memory" | Reduce batch size or use stage loading |
| **Timeout** | "Query timeout" | Use larger warehouse or stage loading |

### Debug Mode

```python
# Enable comprehensive debugging
set_sql_debug_mode(True)

# Run sync with full visibility
result = sync_sobject_intelligent(...)

# Check specific issues
print(f"Sync result: {result}")
print(f"Sync method used: {result.get('sync_method')}")
print(f"Records processed: {result.get('records_processed')}")
print(f"Errors: {result.get('errors', [])}")
```

## Best Practices

### 1. **Test First**
```python
# Test with small dataset first
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Account',
    schema='SALESFORCE',
    table='ACCOUNT_TEST'  # Use test table first
)
```

### 2. **Monitor Performance**
```python
import time

start_time = time.time()
result = sync_sobject_intelligent(...)
end_time = time.time()

print(f"⏱️ Sync completed in {end_time - start_time:.2f} seconds")
print(f"📊 {result.get('records_processed', 0)} records processed")
```

### 3. **Handle Errors Gracefully**
```python
def safe_sync(sobject, schema, table, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = sync_sobject_intelligent(
                session=session,
                access_info=sf_token,
                sobject=sobject,
                schema=schema,
                table=table
            )
            print(f"✅ Sync successful on attempt {attempt + 1}")
            return result
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"💥 All {max_retries} attempts failed")
                raise

# Use safe sync
result = safe_sync('Invoice__c', 'SALESFORCE', 'INVOICE')
```

### 4. **Regular Maintenance**
```python
# Check for orphaned temporary tables
def cleanup_temp_tables(schema):
    try:
        temp_tables = session.sql(f"SHOW TABLES IN SCHEMA {schema}").collect()
        for table in temp_tables:
            if table['name'].startswith('TMP_'):
                print(f"🧹 Dropping temporary table: {table['name']}")
                session.sql(f"DROP TABLE IF EXISTS {schema}.{table['name']}").collect()
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

# Run cleanup periodically
cleanup_temp_tables('SALESFORCE')
```

## Complete Example

```python
# Complete Salesforce to Snowflake sync workflow
from lht.salesforce.intelligent_sync import sync_sobject_intelligent, set_sql_debug_mode
import time

def sync_salesforce_to_snowflake():
    print("🚀 Starting Salesforce to Snowflake synchronization...")
    
    # Configuration
    sobjects = ['Account', 'Contact', 'Invoice__c']
    schema = 'SALESFORCE'
    
    # Enable debug for troubleshooting
    set_sql_debug_mode(True)
    
    results = {}
    
    for sobject in sobjects:
        table_name = sobject.upper()
        print(f"\n🔄 Syncing {sobject} to {schema}.{table_name}")
        
        try:
            start_time = time.time()
            
            result = sync_sobject_intelligent(
                session=session,
                access_info=sf_token,
                sobject=sobject,
                schema=schema,
                table=table_name,
                match_field='ID'
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            results[sobject] = {
                'status': 'success',
                'duration': duration,
                'records': result.get('records_processed', 0),
                'method': result.get('sync_method', 'unknown')
            }
            
            print(f"✅ {sobject} sync completed in {duration:.2f}s")
            print(f"   Records: {results[sobject]['records']}")
            print(f"   Method: {results[sobject]['method']}")
            
        except Exception as e:
            results[sobject] = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"❌ {sobject} sync failed: {e}")
    
    # Summary
    print(f"\n📊 Sync Summary:")
    for sobject, result in results.items():
        if result['status'] == 'success':
            print(f"   ✅ {sobject}: {result['records']} records in {result['duration']:.2f}s")
        else:
            print(f"   ❌ {sobject}: {result['error']}")
    
    # Disable debug
    set_sql_debug_mode(False)
    
    return results

# Run the complete sync
sync_results = sync_salesforce_to_snowflake()
```

## Support

For additional help:
- Check the troubleshooting section above
- Enable debug mode to see detailed execution information
- Review error messages for specific guidance
- Ensure all prerequisites are met

---
# Salesforce to Snowflake Synchronization Guide

This guide explains how to synchronize Salesforce SObjects to Snowflake using the LHT package in a Snowflake notebook environment.

## Prerequisites

- ✅ Snowflake notebook environment with LHT package installed
- ✅ Salesforce access token (`access_info`) already established
- ✅ Snowflake session (`session`) already configured
- ✅ Appropriate Snowflake permissions (CREATE TABLE, INSERT, etc.)

## Quick Start

### Basic Synchronization

```python
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

# Perform intelligent synchronization
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE',
    match_field='ID'
)

print(f"Sync completed: {result}")
```

### What Happens Automatically

1. **Sync Strategy Selection**: System determines whether to perform full or incremental sync
2. **API Selection**: Chooses between Regular API, Bulk API 2.0, or Stage-based loading
3. **Data Processing**: Handles Salesforce data types and converts to Snowflake-compatible formats
4. **Table Management**: Creates/updates tables with proper schemas
5. **Data Loading**: Loads data into Snowflake with error handling

## Configuration Options

### Basic Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session` | SnowparkSession | Yes | Active Snowflake session |
| `access_info` | dict | Yes | Salesforce access token/credentials |
| `sobject` | str | Yes | Salesforce SObject name (e.g., 'Account', 'Invoice__c') |
| `schema` | str | Yes | Snowflake schema name |
| `table` | str | Yes | Snowflake table name |
| `match_field` | str | No | Field for record matching (default: 'ID') |

### Advanced Parameters

```python
from lht.salesforce.intelligent_sync import IntelligentSync

# Create sync instance with custom configuration
sync = IntelligentSync(session, sf_token)

# Configure thresholds
sync.BULK_API_THRESHOLD = 5000      # Use Bulk API for >= 5000 records
sync.REGULAR_API_THRESHOLD = 500    # Use Regular API for >= 500 records
sync.STAGE_THRESHOLD = 25000        # Use Stage for >= 25000 records

# Perform sync with custom settings
result = sync.sync_sobject(
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE',
    match_field='ID',
    use_stage=False,              # Force non-stage loading
    force_full_sync=False         # Force full sync regardless of last sync
)
```

## Sync Methods

### 1. Intelligent Sync (Recommended)

```python
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE'
)
```

**Features:**
- Automatically selects best sync method based on data volume
- Handles incremental vs. full sync decisions
- Chooses appropriate Salesforce API (Regular vs. Bulk API 2.0)
- Manages temporary tables and data merging

### 2. Direct Bulk API 2.0

```python
from lht.salesforce.query_bapi20 import SalesforceBulkAPI20

# Create Bulk API handler
bulk_api = SalesforceBulkAPI20(session, sf_token)

# Query and load data directly
result = bulk_api.query_and_load(
    sobject='Invoice__c',
    schema='SALESFORCE',
    table='INVOICE',
    query_fields=['Id', 'Name', 'Amount__c', 'CreatedDate'],
    where_clause="CreatedDate >= 2023-01-01"
)
```

**Use Cases:**
- Large datasets (>10,000 records)
- Custom SOQL queries
- Specific date ranges or filters
- Direct table creation with custom schema

### 3. Stage-Based Loading

```python
from lht.salesforce.intelligent_sync import IntelligentSync

sync = IntelligentSync(session, sf_token)

# Force stage-based loading for very large datasets
result = sync.sync_sobject(
    sobject='Account',
    schema='SALESFORCE',
    table='ACCOUNT',
    use_stage=True,
    stage_name='@SALESFORCE_STAGE'
)
```

**Use Cases:**
- Very large datasets (>50,000 records)
- When you want to use Snowflake stages
- Better performance for massive data loads

## Data Type Handling

### Automatic Type Conversion

The system automatically handles Salesforce data types:

| Salesforce Type | Snowflake Type | Notes |
|-----------------|----------------|-------|
| `string` | `VARCHAR(16777216)` | Text fields, IDs, references |
| `int` | `NUMBER(38,0)` | Integer fields |
| `double` | `DOUBLE` | Decimal/numeric fields |
| `boolean` | `BOOLEAN` | True/false fields |
| `datetime` | `TIMESTAMP_NTZ` | Date/time fields |
| `date` | `VARCHAR` | Date-only fields (as strings) |

### Custom Type Handling

```python
from lht.util.field_types import format_sync_file

# Force all datetime fields to be strings (VARCHAR)
formatted_df = format_sync_file(
    df, 
    df_fields, 
    force_datetime_to_string=True
)
```

## Error Handling and Debugging

### Enable SQL Debug Output

```python
from lht.salesforce.intelligent_sync import set_sql_debug_mode

# Enable detailed SQL logging
set_sql_debug_mode(True)

# Run your sync
result = sync_sobject_intelligent(...)

# Disable debug when done
set_sql_debug_mode(False)
```

### Handle Specific Errors

```python
try:
    result = sync_sobject_intelligent(
        session=session,
        access_info=sf_token,
        sobject='Invoice__c',
        schema='SALESFORCE',
        table='INVOICE'
    )
    print(f"✅ Sync successful: {result}")
    
except Exception as e:
    print(f"❌ Sync failed: {e}")
    
    # Check specific error types
    if "Failed to cast variant value" in str(e):
        print("💡 Data type casting issue - try force_datetime_to_string=True")
    elif "Table does not exist" in str(e):
        print("💡 Table creation issue - check permissions")
    elif "Authentication failed" in str(e):
        print("💡 Salesforce token issue - refresh credentials")
```

## Common Use Cases

### 1. Full SObject Sync

```python
# Sync entire SObject (creates table if it doesn't exist)
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Account',
    schema='SALESFORCE',
    table='ACCOUNT'
)
```

### 2. Incremental Sync

```python
# System automatically detects last sync and only syncs changes
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Contact',
    schema='SALESFORCE',
    table='CONTACT'
)
```

### 3. Custom Field Selection

```python
from lht.salesforce.sobjects import SalesforceSObject

# Get SObject metadata
sobject = SalesforceSObject(sf_token)
fields = sobject.describe('Invoice__c')

# Filter to specific fields
custom_fields = [f for f in fields if f['custom']]
print(f"Custom fields: {[f['name'] for f in custom_fields]}")
```

### 4. Scheduled Syncs

```python
import schedule
import time

def sync_invoices():
    try:
        result = sync_sobject_intelligent(
            session=session,
            access_info=sf_token,
            sobject='Invoice__c',
            schema='SALESFORCE',
            table='INVOICE'
        )
        print(f"✅ Scheduled sync completed: {result}")
    except Exception as e:
        print(f"❌ Scheduled sync failed: {e}")

# Schedule sync every hour
schedule.every().hour.do(sync_invoices)

# Keep running
while True:
    schedule.run_pending()
    time.sleep(60)
```

## Performance Optimization

### 1. Batch Size Control

```python
from lht.util.data_writer import DataWriter

# Configure batch sizes
writer = DataWriter(session)
writer.BATCH_SIZE = 5000  # Process 5000 records at a time
```

### 2. Warehouse Selection

```python
# Use larger warehouse for big syncs
session.sql("USE WAREHOUSE LARGE_WH").collect()

# Run sync
result = sync_sobject_intelligent(...)

# Return to default warehouse
session.sql("USE WAREHOUSE DEFAULT_WH").collect()
```

### 3. Parallel Processing

```python
# Sync multiple SObjects in parallel
import concurrent.futures

sobjects = ['Account', 'Contact', 'Opportunity', 'Invoice__c']

def sync_sobject(sobject_name):
    return sync_sobject_intelligent(
        session=session,
        access_info=sf_token,
        sobject=sobject_name,
        schema='SALESFORCE',
        table=sobject_name.upper()
    )

# Run parallel syncs
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(sync_sobject, name): name for name in sobjects}
    
    for future in concurrent.futures.as_completed(futures):
        sobject_name = futures[future]
        try:
            result = future.result()
            print(f"✅ {sobject_name} sync completed: {result}")
        except Exception as e:
            print(f"❌ {sobject_name} sync failed: {e}")
```

## Monitoring and Logging

### Check Sync Status

```python
# Check if table exists and has data
def check_sync_status(schema, table):
    try:
        # Check table existence
        table_check = session.sql(f"SHOW TABLES IN SCHEMA {schema}").collect()
        table_exists = any(row['name'] == table for row in table_check)
        
        if table_exists:
            # Check record count
            count_result = session.sql(f"SELECT COUNT(*) as record_count FROM {schema}.{table}").collect()
            record_count = count_result[0]['record_count']
            print(f"✅ Table {schema}.{table} exists with {record_count} records")
            return True
        else:
            print(f"❌ Table {schema}.{table} does not exist")
            return False
            
    except Exception as e:
        print(f"❌ Error checking sync status: {e}")
        return False

# Check your sync
check_sync_status('SALESFORCE', 'INVOICE')
```

### View Sync History

```python
# Check last modified dates
def get_last_sync_info(schema, table):
    try:
        query = f"""
        SELECT 
            MAX(CREATEDDATE) as last_created,
            MAX(LASTMODIFIEDDATE) as last_modified,
            COUNT(*) as total_records
        FROM {schema}.{table}
        """
        result = session.sql(query).collect()
        
        if result:
            row = result[0]
            print(f"📊 {schema}.{table} Sync Info:")
            print(f"   Last Created: {row['last_created']}")
            print(f"   Last Modified: {row['last_modified']}")
            print(f"   Total Records: {row['total_records']}")
        
    except Exception as e:
        print(f"❌ Error getting sync info: {e}")

get_last_sync_info('SALESFORCE', 'INVOICE')
```

## Troubleshooting

### Common Issues and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Data Type Casting** | "Failed to cast variant value" | Use `force_datetime_to_string=True` |
| **Authentication** | "Invalid session" | Refresh Salesforce token |
| **Permissions** | "Insufficient privileges" | Check Snowflake role permissions |
| **Table Not Found** | "Table does not exist" | Ensure schema exists and check permissions |
| **Memory Issues** | "Out of memory" | Reduce batch size or use stage loading |
| **Timeout** | "Query timeout" | Use larger warehouse or stage loading |

### Debug Mode

```python
# Enable comprehensive debugging
set_sql_debug_mode(True)

# Run sync with full visibility
result = sync_sobject_intelligent(...)

# Check specific issues
print(f"Sync result: {result}")
print(f"Sync method used: {result.get('sync_method')}")
print(f"Records processed: {result.get('records_processed')}")
print(f"Errors: {result.get('errors', [])}")
```

## Best Practices

### 1. **Test First**
```python
# Test with small dataset first
result = sync_sobject_intelligent(
    session=session,
    access_info=sf_token,
    sobject='Account',
    schema='SALESFORCE',
    table='ACCOUNT_TEST'  # Use test table first
)
```

### 2. **Monitor Performance**
```python
import time

start_time = time.time()
result = sync_sobject_intelligent(...)
end_time = time.time()

print(f"⏱️ Sync completed in {end_time - start_time:.2f} seconds")
print(f"📊 {result.get('records_processed', 0)} records processed")
```

### 3. **Handle Errors Gracefully**
```python
def safe_sync(sobject, schema, table, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = sync_sobject_intelligent(
                session=session,
                access_info=sf_token,
                sobject=sobject,
                schema=schema,
                table=table
            )
            print(f"✅ Sync successful on attempt {attempt + 1}")
            return result
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"💥 All {max_retries} attempts failed")
                raise

# Use safe sync
result = safe_sync('Invoice__c', 'SALESFORCE', 'INVOICE')
```

### 4. **Regular Maintenance**
```python
# Check for orphaned temporary tables
def cleanup_temp_tables(schema):
    try:
        temp_tables = session.sql(f"SHOW TABLES IN SCHEMA {schema}").collect()
        for table in temp_tables:
            if table['name'].startswith('TMP_'):
                print(f"🧹 Dropping temporary table: {table['name']}")
                session.sql(f"DROP TABLE IF EXISTS {schema}.{table['name']}").collect()
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

# Run cleanup periodically
cleanup_temp_tables('SALESFORCE')
```

## Complete Example

```python
# Complete Salesforce to Snowflake sync workflow
from lht.salesforce.intelligent_sync import sync_sobject_intelligent, set_sql_debug_mode
import time

def sync_salesforce_to_snowflake():
    print("🚀 Starting Salesforce to Snowflake synchronization...")
    
    # Configuration
    sobjects = ['Account', 'Contact', 'Invoice__c']
    schema = 'SALESFORCE'
    
    # Enable debug for troubleshooting
    set_sql_debug_mode(True)
    
    results = {}
    
    for sobject in sobjects:
        table_name = sobject.upper()
        print(f"\n🔄 Syncing {sobject} to {schema}.{table_name}")
        
        try:
            start_time = time.time()
            
            result = sync_sobject_intelligent(
                session=session,
                access_info=sf_token,
                sobject=sobject,
                schema=schema,
                table=table_name,
                match_field='ID'
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            results[sobject] = {
                'status': 'success',
                'duration': duration,
                'records': result.get('records_processed', 0),
                'method': result.get('sync_method', 'unknown')
            }
            
            print(f"✅ {sobject} sync completed in {duration:.2f}s")
            print(f"   Records: {results[sobject]['records']}")
            print(f"   Method: {results[sobject]['method']}")
            
        except Exception as e:
            results[sobject] = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"❌ {sobject} sync failed: {e}")
    
    # Summary
    print(f"\n📊 Sync Summary:")
    for sobject, result in results.items():
        if result['status'] == 'success':
            print(f"   ✅ {sobject}: {result['records']} records in {result['duration']:.2f}s")
        else:
            print(f"   ❌ {sobject}: {result['error']}")
    
    # Disable debug
    set_sql_debug_mode(False)
    
    return results

# Run the complete sync
sync_results = sync_salesforce_to_snowflake()
```

## Support

For additional help:
- Check the troubleshooting section above
- Enable debug mode to see detailed execution information
- Review error messages for specific guidance
- Ensure all prerequisites are met

---

**Happy Syncing! 🚀**
