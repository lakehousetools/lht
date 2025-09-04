# Release Notes - LHT v0.1.227

## 🚀 New Features

### 🔄 Regressive Sync for Permission Issues
- **Resolves field access permission problems**: When a user doesn't have access to certain fields in Salesforce, the sync will now automatically remove those fields from the query and continue with the sync process
- **Intelligent field filtering**: The system now detects which fields the user has access to and dynamically adjusts the SOQL query to exclude inaccessible fields
- **Graceful degradation**: Instead of failing the entire sync, the system now continues with available fields and logs which fields were excluded due to permissions

### ⚡ Force Bulk API 2.0 Option
- **New `force_bulk_api` parameter**: Added to `sync_sobject_intelligent()` function to force the use of Bulk API 2.0 instead of regular API
- **Solves 431 errors**: Resolves "Request Header Fields Too Large" errors that occur when query strings are too long for the regular API
- **Bypasses record count thresholds**: Allows forcing Bulk API 2.0 usage regardless of dataset size
- **Usage example**:
  ```python
  result = sync_sobject_intelligent(
      session=session,
      access_info=access_info,
      sobject="Account",
      schema="SALESFORCE",
      table="ACCOUNT",
      force_bulk_api=True  # Forces Bulk API 2.0 usage
  )
  ```

## 🛠️ Improvements

### 🧹 Error Handling & Debug Cleanup
- **Enhanced error messages**: Improved clarity and specificity of error messages throughout the sync process
- **Better debug logging**: Streamlined debug output to be more informative and less verbose
- **Graceful error recovery**: Better handling of edge cases and unexpected conditions
- **Improved field type handling**: Enhanced logic for detecting and handling different Salesforce field types

### 📊 Sync Strategy Enhancements
- **Smarter field selection**: Improved logic for determining which fields to include in queries
- **Better incremental sync detection**: Enhanced detection of when to use incremental vs full sync
- **Optimized query building**: More efficient SOQL query construction with better field handling

## 🔧 Technical Improvements

### 🏗️ Code Quality
- **Refactored sync logic**: Cleaner separation of concerns in the intelligent sync system
- **Enhanced type safety**: Better type hints and validation throughout the codebase
- **Improved documentation**: Updated docstrings and inline comments for better maintainability

### 🐛 Bug Fixes
- **Fixed field access issues**: Resolved problems where syncs would fail due to inaccessible fields
- **Corrected query string handling**: Fixed issues with URL encoding and special characters in SOQL queries
- **Improved error propagation**: Better error handling and reporting throughout the sync pipeline

## 📋 Coming Soon

### 🎯 Demo Instructions
- **New demo documentation**: Working on comprehensive instructions for setting up and running demos
- **Example scenarios**: Will include common use cases and best practices
- **Troubleshooting guides**: Step-by-step guides for common issues and solutions

## 🔄 Migration Notes

### For Existing Users
- **No breaking changes**: All existing functionality remains the same
- **New optional parameters**: The `force_bulk_api` parameter is optional and defaults to `False`
- **Backward compatibility**: All existing code will continue to work without modification

### Recommended Updates
- **Consider using `force_bulk_api=True`** if you encounter 431 errors with long query strings
- **Review field permissions** in your Salesforce org to ensure optimal sync performance
- **Update to latest version** to benefit from improved error handling and field access logic

## 📈 Performance Improvements

- **Reduced API calls**: More efficient field detection and query building
- **Better memory usage**: Optimized data processing for large datasets
- **Faster error recovery**: Quicker detection and handling of permission issues

## 🛡️ Security & Reliability

- **Enhanced permission handling**: Better respect for Salesforce field-level security
- **Improved error boundaries**: More robust error handling prevents cascading failures
- **Better logging**: Enhanced audit trail for troubleshooting and monitoring

---

## 📞 Support

For questions, issues, or feature requests, please:
- Check the documentation in the `docs/` directory
- Review troubleshooting guides in the project root
- Open an issue on the project repository

**Version**: 0.1.227  
**Release Date**: December 2024  
**Compatibility**: Python 3.9+, Snowflake Snowpark Python 1.31.1+
