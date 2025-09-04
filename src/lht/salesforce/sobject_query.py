import re
import requests
import pandas as pd
from urllib.parse import unquote_plus

def remove_field_from_query(query, field_to_remove):
    """
    Remove a specific field from a SOQL query string.
    
    Args:
        query: SOQL query string (e.g., "SELECT Id, Name, Field1 FROM Account")
        field_to_remove: Field name to remove from the query
    
    Returns:
        str: Modified query string with the field removed
    """
    print(f"🔍 DEBUG: Original query: '{query}'")
    print(f"🔍 DEBUG: Query type: {type(query)}")
    print(f"🔍 DEBUG: Query length: {len(query) if query else 0}")
    print(f"🔍 DEBUG: Field to remove: '{field_to_remove}'")
    
    # Check if query is None or empty
    if not query or not isinstance(query, str):
        print(f"❌ DEBUG: Query is None, empty, or not a string")
        return query or ""
    
    # Clean up the query string and handle URL encoding
    query_clean = query.strip()
    if not query_clean:
        print(f"❌ DEBUG: Query is empty after stripping whitespace")
        return query
    
    # Check if query is URL encoded (contains + instead of spaces)
    is_url_encoded = '+' in query_clean and not re.search(r'SELECT\s+.*\s+FROM', query_clean, re.IGNORECASE)
    print(f"🔍 DEBUG: Query appears to be URL encoded: {is_url_encoded}")
    
    if is_url_encoded:
        # URL decode the query by replacing + with spaces
        query_for_parsing = unquote_plus(query_clean)
        print(f"🔍 DEBUG: URL decoded query (first 200 chars): '{query_for_parsing[:200]}...'")
    else:
        query_for_parsing = query_clean
        print(f"🔍 DEBUG: Query for parsing (first 200 chars): '{query_for_parsing[:200]}...'")
    
    # Try multiple regex patterns to be more flexible
    patterns = [
        r'SELECT\s+(.*?)\s+FROM',  # Standard pattern
        r'SELECT\s+(.*?)\sFROM',   # Less strict whitespace
        r'SELECT\s+(.*?)FROM',     # Even less strict
        r'(?i)SELECT\s+(.*?)\s+FROM',  # Case insensitive inline
        r'SELECT[\s+]+(.*?)[\s+]+FROM',  # Handle + or spaces
    ]
    
    select_match = None
    for i, pattern in enumerate(patterns):
        select_match = re.search(pattern, query_for_parsing, re.IGNORECASE | re.DOTALL)
        if select_match:
            print(f"✅ DEBUG: Pattern {i+1} matched: {pattern}")
            break
        else:
            print(f"❌ DEBUG: Pattern {i+1} failed: {pattern}")
    
    if not select_match:
        print(f"❌ DEBUG: Could not parse SELECT clause from query")
        print(f"🔍 DEBUG: Query contains 'SELECT'? {'SELECT' in query_for_parsing.upper()}")
        print(f"🔍 DEBUG: Query contains 'FROM'? {'FROM' in query_for_parsing.upper()}")
        
        # Show character-by-character breakdown for very short queries
        if len(query_for_parsing) < 100:
            print(f"🔍 DEBUG: Character breakdown: {[c for c in query_for_parsing]}")
        
        return query
    
    select_clause = select_match.group(1)
    print(f"🔍 DEBUG: SELECT clause (first 200 chars): {select_clause[:200]}...")
    
    # Always clean the select clause properly - remove + signs and extra spaces
    select_clause_clean = select_clause.replace('+', ' ')
    select_clause_clean = re.sub(r'\s+', ' ', select_clause_clean.strip())
    
    # Split by commas and clean each field
    fields = [field.strip() for field in select_clause_clean.split(',') if field.strip()]
    print(f"🔍 DEBUG: Total fields found: {len(fields)}")
    print(f"🔍 DEBUG: First 10 fields: {fields[:10]}")
    
    # Find the field to remove (case-insensitive)
    field_found = False
    for field in fields:
        field_name = field.split(' AS ')[0].split(' as ')[0].strip()
        if field_name.upper() == field_to_remove.upper():
            field_found = True
            break
    
    print(f"🔍 DEBUG: Field '{field_to_remove}' found in query: {field_found}")
    
    # Remove the specified field (case-insensitive)
    # Also handle field aliases (e.g., "Field__c AS MyField")
    cleaned_fields = []
    field_removed = False
    
    for field in fields:
        # Extract the actual field name (before any alias)
        field_name = field.split(' AS ')[0].split(' as ')[0].strip()
        
        if field_name.upper() != field_to_remove.upper():
            cleaned_fields.append(field)
        else:
            field_removed = True
            print(f"✅ DEBUG: Removed field: {field}")
    
    print(f"🔍 DEBUG: Fields after removal: {len(cleaned_fields)} remaining")
    print(f"🔍 DEBUG: Original field count: {len(fields)}, Cleaned field count: {len(cleaned_fields)}")
    
    if not field_removed:
        print(f"❌ DEBUG: Field {field_to_remove} not found in fields list")
        return query
    
    if len(cleaned_fields) == 0:
        print(f"❌ DEBUG: Cannot remove all fields from SELECT clause")
        return query
    
    # Reconstruct the query
    if is_url_encoded:
        # Put back the + signs for URL encoded format
        cleaned_select = ', '.join(cleaned_fields).replace(' ', '+')
        # For URL encoded queries, we need to be more careful with the replacement
        cleaned_query = re.sub(
            r'(select\+).*?(\+from)', 
            rf'\1{cleaned_select}\2', 
            query, 
            flags=re.IGNORECASE
        )
    else:
        cleaned_select = ', '.join(cleaned_fields)
        cleaned_query = re.sub(
            r'(SELECT\s+).*?(\s+FROM)', 
            rf'\1{cleaned_select}\2', 
            query, 
            flags=re.IGNORECASE | re.DOTALL
        )
    
    print(f"🔍 DEBUG: Cleaned query (first 200 chars): {cleaned_query[:200]}...")
    return cleaned_query


def query_records(access_info, query, batch_size=1000, incremental=False):
    """
    Query Salesforce records and yield DataFrames for each batch.
    
    Args:
        access_info: Dictionary that contains Salesforce 'access_token' and 'instance_url'.
        query: Salesforce SOQL query string.
        batch_size: Number of records per batch (default: 1000).  Can be up to 2000.
    
    Yields:
        pandas.DataFrame: DataFrame containing a batch of records.
    
    Returns:
        None: If no records are found.
    """

    headers = {
        "Authorization": f"Bearer {access_info['access_token']}",
        "Content-Type": "application/json",
        "Sforce-Query-Options": f"batchSize={batch_size}"
    }

    url = f"{access_info['instance_url']}/services/data/v58.0/queryAll?q={query}"
    print("@@@ QUERY: ", query)
    
    results = requests.get(url, headers=headers)
    
    # Check for INVALID_FIELD errors and retry with cleaned query
    if results.status_code == 400:
        json_data = results.json()
        if isinstance(json_data, list) and len(json_data) > 0:
            error_info = json_data[0]
            if error_info.get('errorCode') == 'INVALID_FIELD':
                error_message = error_info.get('message', '')
                print(f"❌ INVALID_FIELD error: {error_message}")
                
                # Extract field name from error message
                field_match = re.search(r"No such column '([^']+)'", error_message)
                if field_match:
                    invalid_field = field_match.group(1)
                    print(f"🔍 Removing invalid field: {invalid_field}")
                    
                    # Remove the invalid field from the query
                    cleaned_query = remove_field_from_query(query, invalid_field)
                    if cleaned_query != query:
                        print(f"🔄 Retrying with cleaned query")
                        # Use 'yield from' to properly delegate the generator
                        yield from query_records(access_info, cleaned_query, batch_size, incremental)
                        return  # Exit early after successful retry
                    else:
                        print(f"❌ Could not remove field {invalid_field} from query")
    
    results.raise_for_status()  # Raise exception for HTTP errors
    json_data = results.json()

    if json_data['totalSize'] == 0:
        return None

    sobj_data = pd.json_normalize(json_data['records'])
    try:
        sobj_data.drop(columns=['attributes.type', 'attributes.url'], inplace=True)
    except KeyError:
        print("Attributes not found, moving on")
    
    for col in sobj_data.select_dtypes(include=['datetime64']).columns:
        sobj_data[col] = sobj_data[col].fillna(pd.Timestamp('1900-01-01'))

    for col in sobj_data.select_dtypes(include=['float64', 'int64']).columns:
        sobj_data[col] = sobj_data[col].fillna(0)

    for col in sobj_data.select_dtypes(include=['object']).columns:
        sobj_data[col] = sobj_data[col].fillna('')

    sobj_data.columns = sobj_data.columns.str.upper()

    yield sobj_data

    while json_data.get('nextRecordsUrl'):
        url = f"{access_info['instance_url']}{json_data['nextRecordsUrl']}"
        results = requests.get(url, headers=headers)
        results.raise_for_status()
        json_data = results.json()

        sobj_data = pd.json_normalize(json_data['records'])
        sobj_data.columns = sobj_data.columns.str.upper()
        try:
            sobj_data.drop(columns=['ATTRIBUTES.TYPE', 'ATTRIBUTES.URL'], inplace=True)
        except KeyError:
            print("Attributes not found, moving on")
        
        for col in sobj_data.select_dtypes(include=['datetime64']).columns:
            sobj_data[col] = sobj_data[col].fillna(pd.Timestamp('1900-01-01')) 
        for col in sobj_data.select_dtypes(include=['float64', 'int64']).columns:
            sobj_data[col] = sobj_data[col].fillna(0)
        for col in sobj_data.select_dtypes(include=['object']).columns:
            sobj_data[col] = sobj_data[col].fillna('')

        yield sobj_data