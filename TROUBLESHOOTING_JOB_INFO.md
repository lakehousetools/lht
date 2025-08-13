# Troubleshooting Job Info Table Population Issues

## 🔍 Current Debugging Added

The code now includes comprehensive debugging output that will show:

1. **Job Data Structure**: All keys and values received from Salesforce
2. **SQL Generation**: The exact SQL being generated and executed
3. **Variable Values**: All computed variables before SQL generation
4. **SQL Execution**: Results from the actual SQL execution
5. **Data Flow**: What's being passed between functions

## 🚨 Common Issues and Solutions

### 1. **SQL Syntax Errors**
- **Symptoms**: `syntax error line X at position Y unexpected 'Z'`
- **Causes**: 
  - Python conditional expressions in SQL strings
  - Unescaped quotes in string values
  - Invalid SQL function calls
- **Solutions**: 
  - Move all conditional logic to Python variables
  - Use proper string escaping (`chr(39)` for single quotes)
  - Validate SQL syntax before execution

### 2. **Timestamp Conversion Issues**
- **Symptoms**: `Invalid expression [CAST('timestamp' AS TIMESTAMP_NTZ(9))]`
- **Causes**: 
  - ISO 8601 format with timezone offsets not handled properly
  - Invalid timestamp format from Salesforce
- **Solutions**: 
  - Use `TO_TIMESTAMP_TZ()` first, then `TO_TIMESTAMP_NTZ()`
  - Add timestamp format validation
  - Handle timezone conversion explicitly

### 3. **Data Type Mismatches**
- **Symptoms**: `SQL compilation error: Invalid expression`
- **Causes**: 
  - Field types don't match table schema
  - NULL values not handled properly
  - Numeric fields receiving string data
- **Solutions**: 
  - Validate data types before SQL generation
  - Use proper NULL handling
  - Add type conversion where needed

### 4. **Missing or Empty Data**
- **Symptoms**: Tables created but no data inserted
- **Causes**: 
  - Salesforce API returning empty responses
  - Data structure different than expected
  - Authentication or permission issues
- **Solutions**: 
  - Check Salesforce API responses
  - Validate data structure
  - Verify API credentials and permissions

## 🛠️ Additional Troubleshooting Steps

### 1. **Check Salesforce API Response**
```python
# Add this to see raw API response
print(f"🔍 DEBUG: Raw Salesforce API response: {job_info}")
```

### 2. **Validate Table Schema**
```sql
-- Run this in Snowflake to verify table structure
DESCRIBE TABLE LOGS.JOB_INFO;
SHOW COLUMNS IN LOGS.JOB_INFO;
```

### 3. **Test SQL Manually**
```sql
-- Copy the generated SQL and test it manually in Snowflake
-- This will show exact error messages
```

### 4. **Check Data Types**
```python
# Add type checking
for key, value in job_data.items():
    print(f"   {key}: {value} (type: {type(value)})")
```

### 5. **Verify Session Connection**
```python
# Test Snowflake connection
try:
    test_result = session.sql("SELECT CURRENT_TIMESTAMP()").collect()
    print(f"✅ Snowflake connection test: {test_result}")
except Exception as e:
    print(f"❌ Snowflake connection failed: {e}")
```

## 🔧 Recommended Fixes

### 1. **Add Data Validation**
```python
def validate_job_data(job_data: dict) -> bool:
    """Validate job data before SQL generation"""
    required_fields = ['state', 'operation', 'object']
    for field in required_fields:
        if not job_data.get(field):
            print(f"⚠️ Warning: Missing required field: {field}")
    return True
```

### 2. **Add SQL Validation**
```python
def validate_sql(sql: str) -> bool:
    """Basic SQL validation before execution"""
    if 'if' in sql.lower() or 'else' in sql.lower():
        print("❌ ERROR: SQL contains Python conditionals!")
        return False
    return True
```

### 3. **Add Error Recovery**
```python
def safe_sql_execute(session, sql: str, job_id: str):
    """Execute SQL with error recovery"""
    try:
        result = session.sql(sql).collect()
        return result
    except Exception as e:
        print(f"❌ SQL execution failed for {job_id}: {e}")
        print(f"🔍 Failed SQL: {sql}")
        # Try to insert minimal data
        return insert_minimal_job_info(session, job_id)
```

## 📊 Debug Output Format

When you run the code now, you'll see:

```
🔍 DEBUG: Job data for 750O100000KgrXTIAZ:
   Keys: ['id', 'operation', 'object', 'state', 'createdDate', ...]
   Has error: False
   State: JobComplete
   Operation: insert
   Object: Account
   Created Date: 2025-08-11T00:36:50.000+0000
   System Modstamp: 2025-08-11T00:36:50.000+0000
   Error Code: None
   Error Message: None

🔍 DEBUG: Generated normal SQL for 750O100000KgrXTIAZ:
   SQL: INSERT INTO LOGS.JOB_INFO (...) VALUES (...)
   Variables:
     operation: 'insert'
     object_name: 'Account'
     created_date: TO_TIMESTAMP_NTZ(TO_TIMESTAMP_TZ('2025-08-11T00:36:50.000+0000'))
     ...

🔍 DEBUG: Executing SQL for 750O100000KgrXTIAZ...
🔍 DEBUG: SQL execution result: [Row(...)]
✅ Job info inserted for job 750O100000KgrXTIAZ
```

## 🎯 Next Steps

1. **Run the updated code** to see detailed debug output
2. **Check the debug output** for any obvious issues
3. **Validate the generated SQL** manually in Snowflake
4. **Check table permissions** and schema
5. **Verify Salesforce API responses** are as expected

## 📞 When to Escalate

- **Data corruption**: Salesforce returning unexpected data structures
- **Permission issues**: Cannot create tables or insert data
- **Schema conflicts**: Table structure doesn't match expected format
- **API changes**: Salesforce API response format has changed
