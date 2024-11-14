# LHT (Lake House Tools) User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Basic Usage](#basic-usage)
5. [Advanced Features](#advanced-features)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [API Reference](#api-reference)

## Introduction

LHT (Lake House Tools) is a Python package designed to facilitate seamless data integration between Salesforce and Snowflake. It provides robust ETL (Extract, Transform, Load) and Reverse ETL capabilities, making it ideal for organizations that need to maintain synchronized data between these platforms.

### Key Features
- Bi-directional data synchronization
- Automatic schema mapping
- Bulk data operations
- Incremental updates
- Error handling and logging
- CLI interface for common operations

## Installation

### Prerequisites
- Python 3.10 or higher
- Access to Salesforce instance
- Snowflake account
- Required Python packages (see requirements.txt)

### Install via pip
```bash
pip install git+https://github.com/dansolomo/lht.git@initial_pypi_package#egg=lht
```

### Install from source
```bash
git clone https://github.com/dansolomo/lht.git
cd lht
pip install -e .
```

## Configuration

### Directory Structure
```plaintext
your_project/
├── .snowflake/
│   ├── connections.toml
│   └── sfdc.json
└── your_code.py
```

### Snowflake Configuration (connections.toml)
```toml
[myconnection]
account = "your_account"
user = "your_user"
password = "your_password"
warehouse = "your_warehouse"
database = "your_database"
schema = "your_schema"

[salesforce_sandbox]
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
sandbox = true

[salesforce_prod]
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
sandbox = false
```

### Salesforce Authentication
1. Set up Connected App in Salesforce
2. Use the CLI to authenticate:
```bash
lht login
```

## Basic Usage

### 1. Creating Tables
Create a Snowflake table that mirrors a Salesforce object:

```bash
lht create --sobject Account --table MY_ACCOUNTS --username your_username --db_connect myconnection
```

This will:
- Fetch the Salesforce object schema
- Create a corresponding Snowflake table
- Map data types appropriately

### 2. Syncing Data
Perform initial or incremental sync:

```bash
lht sync \
    --sobject Account \
    --table MY_ACCOUNTS \
    --sync_field Id \
    --username your_username \
    --db_connect myconnection
```

Optional: Specify last modified date for incremental sync:
```bash
lht sync \
    --sobject Account \
    --table MY_ACCOUNTS \
    --sync_field Id \
    --lastmodifieddate "2024-01-01 00:00:00" \
    --username your_username \
    --db_connect myconnection
```

### 3. Bulk Query Operations
Execute bulk queries against Salesforce:

```bash
lht query \
    --bapi20 \
    --sobject Account \
    --username your_username \
    --db_connect myconnection
```

Check job status:
```bash
lht bulk_status --job_id your_job_id --username your_username
```

Get results:
```bash
lht bulk_results \
    --job_id your_job_id \
    --sobject Account \
    --schema your_schema \
    --table your_table \
    --username your_username \
    --db_connect myconnection
```

### 4. Reverse ETL Operations
Send data from Snowflake to Salesforce:

```bash
lht retl_upsert \
    --sobject Account \
    --query path/to/query.sql \
    --field ExternalId \
    --username your_username \
    --db_connect myconnection
```

Delete records in Salesforce:
```bash
lht retl_delete \
    --sobject Account \
    --query path/to/query.sql \
    --field Id \
    --username your_username \
    --db_connect myconnection
```

## Advanced Features

### 1. Custom Field Mappings
When creating tables, you can specify custom field mappings:

```python
from lht.util import field_types

custom_mappings = {
    'MyCustomField__c': 'string(255)',
    'AnotherField__c': 'number(18,2)'
}

field_types.register_custom_mappings(custom_mappings)
```

### 2. Batch Size Configuration
Adjust batch sizes for better performance:

```bash
lht sync \
    --sobject Account \
    --table MY_ACCOUNTS \
    --sync_field Id \
    --batch_size 5000 \
    --username your_username \
    --db_connect myconnection
```

### 3. Error Handling
View and manage sync errors:

```bash
lht results \
    --job_id your_job_id \
    --schema your_schema \
    --table your_table \
    --username your_username \
    --db_connect myconnection
```

## Troubleshooting

### Common Issues and Solutions

1. Authentication Errors
```plaintext
Error: "you are not logged in"
Solution: Run 'lht login' to refresh authentication
```

2. Data Type Mismatches
```plaintext
Error: "Invalid type conversion"
Solution: Check field mappings in field_types.py
```

3. API Limits
```plaintext
Error: "INVALID_BULK_API_LIMIT"
Solution: Reduce batch size or implement rate limiting
```

## Best Practices

### 1. Performance Optimization
- Use appropriate batch sizes (typically 2000-5000 records)
- Implement incremental syncs where possible
- Index matching fields in Snowflake

### 2. Data Quality
- Validate data before syncing
- Use external IDs for reliable matching
- Maintain audit logs

### 3. Security
- Rotate credentials regularly
- Use environment variables for sensitive data
- Implement proper access controls

## API Reference

### Command Line Interface
| Command | Description | Required Parameters |
|---------|-------------|-------------------|
| create | Create table | sobject, table, username |
| sync | Sync data | sobject, table, sync_field, username |
| query | Bulk query | bapi20, sobject, username |
| retl_upsert | Reverse ETL | sobject, query, field, username |
| retl_delete | Delete records | sobject, query, field, username |

### Python API
```python
from lht.salesforce import sobject_create, sobject_sync, retl

# Create table
sobject_create.create(session, access_info, "Account", "MY_ACCOUNTS")

# Sync data
sobject_sync.new_changed_records(session, access_info, 
                               "Account", "MY_ACCOUNTS", "Id")

# Reverse ETL
retl.upsert(session, access_info, "Account", "query.sql", "ExternalId")
```

For more detailed information, visit the [GitHub repository](https://github.com/dansolomo/lht).