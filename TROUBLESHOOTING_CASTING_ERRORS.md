# Troubleshooting Snowflake Casting Errors

## 🚨 Common Error: "Failed to cast variant value to FIXED"

### Error Message
```
❌ Error executing sync strategy: (1113): Unable to write pandas dataframe to Snowflake. 
COPY INTO command output [('snowpark_temp_stage_502lgo8vrm/file0.txt', 'PARTIALLY_LOADED', 155218, 130803, 155218, 24415, 'Failed to cast variant value "V207252" to FIXED', 62320, None, None)]
```

### 🔍 What This Means
- **Status**: `PARTIALLY_LOADED` - Some data was loaded, some failed
- **Records**: 155,218 total, 130,803 loaded, 24,415 failed
- **Root Cause**: Snowflake can't convert string value `"V207252"` to numeric type `FIXED`
- **Impact**: Data loss - 24,415 records were not loaded

## 🛠️ Solutions

### 1. **Use the New Type-Handling Functions (Recommended)**

The refactored `data_writer` module now includes automatic type handling:

```python
from lht.util.data_writer import write_dataframe_with_type_handling

# Automatic type handling with validation
result = write_dataframe_with_type_handling(
    session=session,
    df=formatted_df,
    schema=schema,
    table=table,
    type_strategy="lenient",  # Smart type conversion
    overwrite=True
)
```

### 2. **Manual Type Standardization**

If you need more control over type conversion:

```python
from lht.util.data_writer import standardize_dataframe_types, write_dataframe_to_table

# Convert problematic columns to string to avoid casting issues
df_standardized = standardize_dataframe_types(df, type_strategy="string")

# Write with lenient settings
result = write_dataframe_to_table(
    session=session,
    df=df_standardized,
    schema=schema,
    table=table,
    use_logical_type=False,  # More lenient type handling
    on_error="CONTINUE"      # Continue on errors
)
```

### 3. **Data Validation Before Writing**

Check your data for type issues before writing:

```python
from lht.util.data_writer import validate_dataframe_types

# Validate DataFrame types
validation_result = validate_dataframe_types(df)

if not validation_result['is_valid']:
    print("⚠️ Type validation found issues:")
    for issue in validation_result['issues']:
        print(f"   - {issue}")
    
    for recommendation in validation_result['recommendations']:
        print(f"   💡 {recommendation}")
    
    # Use lenient settings for problematic data
    result = write_dataframe_to_table(
        session=session,
        df=df,
        schema=schema,
        table=table,
        use_logical_type=False,
        on_error="CONTINUE"
    )
```

## 🔧 Type Strategy Options

### **"auto"** (Default)
- Smart type inference
- Converts columns to numeric if all values are numeric
- Falls back to string for mixed types

### **"string"** (Safest)
- Converts everything to string
- Prevents all casting issues
- May lose numeric precision

### **"numeric"** (Most Precise)
- Converts to numeric where possible
- Falls back to string for non-numeric values
- May cause errors if conversion fails

### **"lenient"** (Recommended for Problematic Data)
- Intelligent type conversion
- Converts to numeric if 80%+ values are numeric
- Falls back to string for mixed types

## 📊 Example Usage in Intelligent Sync

### **Before (Prone to Errors)**
```python
# Old approach - direct write_pandas
self.session.write_pandas(
    formatted_df, f"{current_db}.{schema}.{table}", 
    quote_identifiers=False, auto_create_table=True, 
    overwrite=overwrite, use_logical_type=True, on_error="CONTINUE"
)
```

### **After (Error-Resistant)**
```python
# New approach - centralized with type handling
from lht.util.data_writer import write_batch_to_main_table

result = write_batch_to_main_table(
    self.session, 
    formatted_df, 
    schema, 
    table, 
    is_first_batch=(records_processed == 0),
    validate_types=True,
    use_logical_type=False  # More lenient for problematic data
)
```

## 🚨 Emergency Fix for Existing Code

If you need a quick fix without refactoring:

```python
# Quick fix: Convert problematic columns to string
for column in df.columns:
    if df[column].dtype == 'object':
        # Check if column contains mixed types
        sample_values = df[column].dropna().head(10)
        has_numeric_strings = any(
            isinstance(x, str) and x.replace('.', '').replace('-', '').isdigit() 
            for x in sample_values
        )
        
        if has_numeric_strings:
            print(f"⚠️ Converting mixed-type column '{column}' to string")
            df[column] = df[column].astype(str)

# Write with lenient settings
session.write_pandas(
    df, table_name,
    use_logical_type=False,  # More lenient
    on_error="CONTINUE"      # Continue on errors
)
```

## 🔍 Debugging Steps

### 1. **Identify Problematic Columns**
```python
# Check column types and sample values
for column in df.columns:
    print(f"\nColumn: {column}")
    print(f"  Type: {df[column].dtype}")
    print(f"  Sample values: {df[column].dropna().head(5).tolist()}")
    
    # Check for mixed types
    if df[column].dtype == 'object':
        numeric_count = 0
        total_count = len(df[column].dropna())
        
        for value in df[column].dropna():
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                numeric_count += 1
        
        if numeric_count > 0 and numeric_count < total_count:
            print(f"  ⚠️ Mixed types: {numeric_count}/{total_count} are numeric strings")
```

### 2. **Test Type Conversion**
```python
# Test if problematic columns can be converted
problematic_column = "your_column_name"
try:
    converted = pd.to_numeric(df[problematic_column], errors='raise')
    print(f"✅ Column '{problematic_column}' can be converted to numeric")
except (ValueError, TypeError) as e:
    print(f"❌ Column '{problematic_column}' cannot be converted to numeric: {e}")
    
    # Show problematic values
    sample_values = df[problematic_column].dropna().head(10)
    print(f"   Sample values: {sample_values.tolist()}")
```

## 📋 Best Practices

1. **Always validate data types** before writing to Snowflake
2. **Use the centralized data writer functions** for consistent error handling
3. **Set `use_logical_type=False`** for problematic or mixed-type data
4. **Use `on_error="CONTINUE"`** to avoid complete failures
5. **Convert mixed-type columns to string** if numeric precision isn't critical
6. **Log type conversion decisions** for debugging and auditing

## 🆘 When to Get Help

Contact support if:
- Type conversion strategies don't resolve the issue
- You're losing critical data due to type mismatches
- You need to preserve specific data types for business logic
- The error persists after using all recommended solutions
