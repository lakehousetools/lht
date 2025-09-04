import pandas as pd
import numpy as np
import tempfile
import re


def salesforce_field_type(field_type):
	if field_type['type'] == 'id':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'boolean':
		return 'boolean'
	elif field_type['type'] == 'reference':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'string':
		return 'string' #'string({})'.format(field_type['length']) -- modified this because mixed types calls strings that look like numbers to overflow, ie '20' becomes 20.0 even when it's converted back to a string
	elif field_type['type'] == 'email':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'picklist':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'textarea':
		return 'string'
	elif field_type['type'] == 'double':
		if field_type['precision'] > 0:
			precision = field_type['precision']
		elif field_type['digits'] > 0:
			precision = field_type['precision']
		scale = field_type['scale']
		return 'NUMBER({},{})'.format(precision, scale)
	elif field_type['type'] == 'phone':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'datetime':
		return 'timestamp_ntz' #'NUMBER(38,0)' #
	elif field_type['type'] == 'date':
		return 'date' #'NUMBER(38,0)' #
	elif field_type['type'] == 'address':
		return 'string' #({})'.format(field_type['length'])
	elif field_type['type'] == 'url':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'currency':
		return 'number({},{})'.format(field_type['precision'], field_type['scale'])
	elif field_type['type'] == 'int':
		if field_type['precision'] > 0:
			precision = field_type['precision']
		elif field_type['digits'] > 0:
			precision = field_type['digits']
		return 'number({},{})'.format(precision, field_type['scale'])
	elif field_type['type'] == 'multipicklist':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'percent':
		return 'number({},{})'.format(field_type['precision'], field_type['scale'])
	elif field_type['type'] == 'combobox':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'encryptedstring':
		return 'string({})'.format(field_type['length'])
	elif field_type['type'] == 'base64':
		return 'string'
	elif field_type['type'] == 'datacategorygroupreference':
		return 'string(80)'	
	elif field_type['type'] == 'anyType':
		return 'string'
	elif field_type['type'] == 'byte':
		return 'string(1)'	
	elif field_type['type'] == 'calc':
		return 'string(255)'
	# Removed duplicate int case
	elif field_type['type'] == 'junctionidlist':
		return 'string(18)'
	elif field_type['type'] == 'long':
		return 'number(32)'
	elif field_type['type'] == 'time':
		return 'string(24)'
	else:
		print("KACK {}".format(field_type['type']))
		exit(0)
	
def df_field_type(field_type):
	if field_type['type'] == 'id':
		return 'object'
	elif field_type['type'] == 'boolean':
		return 'bool'
	elif field_type['type'] == 'reference':
		return 'object'
	elif field_type['type'] == 'string':
		return 'object'
	elif field_type['type'] == 'email':
		return 'object'
	elif field_type['type'] == 'picklist':
		return 'object'
	elif field_type['type'] == 'textarea':
		return 'object'
	elif field_type['type'] == 'double':
		return 'float64'
	elif field_type['type'] == 'phone':
		return 'object'
	elif field_type['type'] == 'datetime':
		return 'datetime64'
	elif field_type['type'] == 'date':
		return 'date'  # Keep date fields as date, not convert to datetime64
	elif field_type['type'] == 'address':
		return 'object'
	elif field_type['type'] == 'url':
		return 'object'
	elif field_type['type'] == 'currency':
		return 'float64'
	elif field_type['type'] == 'int':
		return 'int64'

def convert_field_types(df, df_fieldsets, table_fields):

	for col, dtype in df_fieldsets.items():

		if col.upper() not in table_fields:
			df.drop(columns=[col], inplace=True)
			continue 
		elif dtype == 'date':
			df[col] == pd.to_datetime(df[col],errors='coerce').dt.date
		elif dtype == 'int64':
			df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
		elif dtype == 'object':
			df[col] = df[col].astype(str)
		elif dtype == 'float64':
			df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
		elif dtype == 'bool':
			df[col] = pd.to_numeric(df[col], errors='coerce').astype('bool')
		elif dtype == 'datetime64':
			df[col] = pd.to_datetime(df[col], errors='coerce')
			#df[col] = pd.to_datetime(df[col],errors='coerce').dt.datetime64
	df = df.replace(np.nan, None)
	return df.rename(columns={col: col.upper() for col in df.columns})

def cache_data(data):
	with tempfile.NamedTemporaryFile(delete=False) as temp_file:
		temp_file.write(data)
		temp_file_path = temp_file.name
	#print("  {}".format(temp_file_path))
	return temp_file_path


def format_sync_file(df, df_fields):
	"""
	Format DataFrame for Salesforce sync operations with robust type handling.
	
	This function now includes improved DATE field handling that prevents the
	'str object is not callable' error by ensuring proper type conversion
	and fallback handling for problematic data.
	"""
	# First, convert all column names to uppercase to match Salesforce API response
	df.columns = df.columns.str.upper()
	
	# Helper function to safely convert to string
	def safe_to_string(series):
		if series.dtype != 'object':
			return series.astype(str)
		return series
	
	# Pre-process all columns to ensure they're in a clean state
	print("🔍 Pre-processing DataFrame columns for type safety...")
	for col in df.columns:
		try:
			# Handle any problematic data types before main processing
			if df[col].dtype == 'object':
				# Clean up object columns that might have mixed types
				df[col] = df[col].replace({pd.NA: None, pd.NaT: None, 'nan': None, 'None': None, '<NA>': None})
				df[col] = safe_to_string(df[col])
				#print(f"✅ Pre-processed column {col} to clean string")
		except Exception as e:
			print(f"⚠️ Warning: Error pre-processing column {col}: {e}")
			# Fallback: ensure it's a string
			try:
				df[col] = df[col].astype(str)
			except:
				# Last resort: fill with None
				df[col] = None
				print(f"⚠️ Column {col} filled with None due to conversion error")
	
	print("✅ DataFrame pre-processing completed")
	
	# Debug: Show field type mappings
	print("🔍 Field type mappings:")
	for col, dtype in df_fields.items():
		print(f"  {col}: {dtype}")
	print()
	
	# Debug: Check if EFFECTIVEDATE is in the mappings
	if 'EFFECTIVEDATE' in df_fields:
		print(f"✅ EFFECTIVEDATE found in df_fields with type: {df_fields['EFFECTIVEDATE']}")
	else:
		print("❌ EFFECTIVEDATE NOT found in df_fields")
		# Check for case variations
		effective_date_variations = [col for col in df_fields.keys() if col.upper() == 'EFFECTIVEDATE']
		if effective_date_variations:
			print(f"✅ Found EFFECTIVEDATE variations: {effective_date_variations}")
			for var in effective_date_variations:
				print(f"  {var}: {df_fields[var]}")
		else:
			print("❌ No EFFECTIVEDATE variations found either")
		print(f"Available fields: {list(df_fields.keys())}")
	
	# Debug: Show all datetime fields
	datetime_fields = [col for col, dtype in df_fields.items() if dtype in ['datetime64', 'datetime64[ns]']]
	if datetime_fields:
		print(f"🔍 Datetime fields found: {datetime_fields}")
	else:
		print("⚠️ No datetime fields found in df_fields")
	print()
	
	# Now process each field according to its intended type
	for col, dtype in df_fields.items():
		# Convert field name to uppercase to match DataFrame columns
		col_upper = col.upper()
		
		# Debug: Show what's happening with EFFECTIVEDATE specifically
		if col_upper == 'EFFECTIVEDATE':
			print(f"🔍 Processing EFFECTIVEDATE field:")
			print(f"  Original col name: {col}")
			print(f"  Mapped dtype: {dtype}")
			print(f"  Uppercase col: {col_upper}")
			print(f"  In DataFrame columns: {col_upper in df.columns}")
			if col_upper in df.columns:
				print(f"  DataFrame dtype: {df[col_upper].dtype}")
				print(f"  Sample values: {df[col_upper].head(3).tolist()}")
		
		# Case-insensitive field matching
		# First try exact match, then try uppercase match
		field_found = False
		if col in df.columns:
			col_upper = col  # Use original case
			field_found = True
		elif col_upper in df.columns:
			field_found = True
		else:
			# Try to find a case-insensitive match
			for df_col in df.columns:
				if df_col.upper() == col_upper:
					col_upper = df_col  # Use the actual DataFrame column name
					field_found = True
					break
		
		try:
			if field_found:
				# Additional safety check: ensure column is in a good state before processing
				if df[col_upper].dtype == 'object' and df[col_upper].isna().all():
					#print(f"⚠️ Warning: Column {col_upper} is all NaN, skipping type conversion")
					continue
				# CRITICAL: Force fields to their intended types BEFORE any data analysis
				# This ensures write_pandas creates the correct table schema
				if dtype == 'datetime64' or dtype == 'datetime64[ns]':
					# Salesforce datetime fields (like CreatedDate, LastViewedDate, LastActivityDate) MUST be datetime
					print(f"🔍 Processing datetime field: {col_upper}")
					print(f"  Original dtype: {df[col_upper].dtype}")
					print(f"  Sample values: {df[col_upper].head(3).tolist()}")
					
					# First, handle any None/NaN values that might cause conversion issues
					df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None, 'nan': None, 'None': None, '<NA>': None})
					
					# Convert to datetime with more robust error handling
					try:
						df[col_upper] = pd.to_datetime(df[col_upper], errors='coerce', utc=True)
						
						# Fill NaT values with a default datetime
						df[col_upper] = df[col_upper].fillna(pd.Timestamp('1900-01-01 00:00:00'))
						
						# Check if we have timezone-aware datetimes and convert to timezone-naive
						if hasattr(df[col_upper], 'dt') and hasattr(df[col_upper].dt, 'tz'):
							tz_info = df[col_upper].dt.tz
							if tz_info is not None:
								df[col_upper] = df[col_upper].dt.tz_localize(None)
						
						# Verify we have a proper datetime column
						if pd.api.types.is_datetime64_any_dtype(df[col_upper]):
							print(f"✅ Successfully converted {col_upper} to datetime64")
						else:
							print(f"⚠️ Warning: {col_upper} is not datetime64 after conversion, dtype: {df[col_upper].dtype}")
							# Try one more time with string conversion first
							df[col_upper] = pd.to_datetime(df[col_upper].astype(str), errors='coerce', utc=True)
							df[col_upper] = df[col_upper].fillna(pd.Timestamp('1900-01-01 00:00:00'))
							
					except Exception as e:
						print(f"⚠️ Warning: Error converting {col_upper} to datetime: {e}")
						# Fallback: convert to string to preserve data
						df[col_upper] = safe_to_string(df[col_upper])
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					# # Salesforce datetime/date fields (like CreatedDate, LastViewedDate, LastActivityDate) MUST be datetime
					# print(f"🔍 Processing datetime field: {col_upper}")
					# print(f"  Original dtype: {df[col_upper].dtype}")
					# print(f"  Sample values: {df[col_upper].head(3).tolist()}")
					
					# # First, handle any None/NaN values that might cause conversion issues
					# df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None, 'nan': None, 'None': None, '<NA>': None})
					
					# # Convert to datetime with more robust error handling
					# try:
					# 	df[col_upper] = pd.to_datetime(df[col_upper], errors='coerce', utc=True)
						
					# 	# Fill NaT values with a default datetime
					# 	df[col_upper] = df[col_upper].fillna(pd.Timestamp('1900-01-01 00:00:00'))
						
					# 	# Check if we have timezone-aware datetimes and convert to timezone-naive
					# 	if hasattr(df[col_upper], 'dt') and hasattr(df[col_upper].dt, 'tz'):
					# 		tz_info = df[col_upper].dt.tz
					# 		if tz_info is not None:
					# 			df[col_upper] = df[col_upper].dt.tz_localize(None)
						
					# 	# Verify we have a proper datetime column
					# 	if pd.api.types.is_datetime64_any_dtype(df[col_upper]):
					# 		print(f"✅ Successfully converted {col_upper} to datetime64")
					# 	else:
					# 		print(f"⚠️ Warning: {col_upper} is not datetime64 after conversion, dtype: {df[col_upper].dtype}")
					# 		# Try one more time with string conversion first
					# 		df[col_upper] = pd.to_datetime(df[col_upper].astype(str), errors='coerce', utc=True)
					# 		df[col_upper] = df[col_upper].fillna(pd.Timestamp('1900-01-01 00:00:00'))
							
					# except Exception as e:
					# 	print(f"⚠️ Warning: Error converting {col_upper} to datetime: {e}")
					# 	# Fallback: convert to string to preserve data
					# 	df[col_upper] = safe_to_string(df[col_upper])
					# 	df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
						
				elif dtype == 'date':
					# Handle date fields - just fill None values, don't change the type
					df[col_upper] = df[col_upper].fillna(pd.Timestamp('1900-01-01').date())

				elif dtype == 'object':
					# Salesforce string fields (including PO_Number__c) MUST be strings
					# Convert to string immediately, regardless of content
					df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
					df[col_upper] = safe_to_string(df[col_upper])
					df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					
				elif dtype == 'int64':
					# Check if ANY value is non-numeric - if so, convert entire column to string
					has_non_numeric = False
					for value in df[col_upper].dropna():
						if isinstance(value, str) and not value.replace('-', '').replace('.', '').isdigit():
							has_non_numeric = True
							break
					
					if has_non_numeric:
						# Convert entire column to string - no mixed types allowed in Snowflake
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = safe_to_string(df[col_upper])
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					else:
						# All values are numeric, safe to convert
						try:
							df[col_upper] = pd.to_numeric(df[col_upper], errors='coerce').astype('Int64')
						except Exception as e:
							print(f"⚠️ Warning: Could not convert {col_upper} to int64, treating as string: {e}")
							df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
							df[col_upper] = safe_to_string(df[col_upper])
							df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
							
				elif dtype == 'float64':
					# For float fields (like latitude/longitude), handle empty strings properly
					# First, replace empty strings with None (which pandas can handle)
					df[col_upper] = df[col_upper].replace({'': None, 'nan': None, 'None': None, '<NA>': None})
					
					# Now convert to float64 - this will convert None to NaN, which is fine
					try:
						df[col_upper] = pd.to_numeric(df[col_upper], errors='coerce').astype('float64')
					except Exception as e:
						print(f"❌ Failed to convert {col_upper} to float64: {e}")
						# Fallback: convert to string but preserve None values
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = safe_to_string(df[col_upper])
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
							
				elif dtype == 'bool':
					# Check for non-boolean values
					has_non_bool = False
					for value in df[col_upper].dropna():
						if isinstance(value, str) and value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
							has_non_bool = True
							break
					
					if has_non_bool:
						# Convert entire column to string
						print(f"⚠️ Column {col_upper} contains non-boolean values, converting entire column to string")
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = safe_to_string(df[col_upper])
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					else:
						# All values are boolean-like, safe to convert
						try:
							df[col_upper] = pd.to_numeric(df[col_upper], errors='coerce').astype('bool')
						except Exception as e:
							print(f"⚠️ Warning: Could not convert {col_upper} to bool, treating as string: {e}")
							df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
							df[col_upper] = safe_to_string(df[col_upper])
							df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
							

			else:
				print(f"field not found '{col_upper}' in DataFrame columns: {list(df.columns)}")
		except Exception as e:
			print(f"field not found '{col_upper}': {e}")
	
	# Final safety check: ensure all columns are in a safe state for Snowpark conversion
	print("🔍 Final safety check: ensuring all columns are Snowpark-compatible...")
	for col in df.columns:
		try:
			# Ensure the column is in a safe state
			if df[col].dtype == 'object':
				# For object columns, ensure they're clean strings
				df[col] = df[col].replace({pd.NA: None, pd.NaT: None, 'nan': None, 'None': None, '<NA>': None})
				# Convert to string if not already
				if df[col].dtype != 'object':
					df[col] = df[col].astype(str)
			elif df[col].dtype in ['int64', 'float64']:
				# For numeric columns, handle NaN values
				if df[col].isna().any():
					df[col] = df[col].fillna(0)
		except Exception as e:
			print(f"⚠️ Warning: Error in final safety check for column {col}: {e}")
			# Last resort: convert to string
			try:
				df[col] = df[col].astype(str)
			except:
				df[col] = None
	
	print("✅ Final safety check completed")
	return df

def map_table_field_types(schema_df, dataframe, df_cols):
    df_cols = [col.upper() for col in df_cols]
    
    # Initialize Pandas_Type column
    schema_df['Pandas_Type'] = None
    
    # Track columns to keep
    cols_to_keep = [col for col in dataframe.columns if col.upper() in df_cols]
    
    # Drop columns not in df_cols
    cols_to_drop = [col for col in dataframe.columns if col.upper() not in df_cols]
    if cols_to_drop:
        try:
            dataframe = dataframe.drop(cols_to_drop)
            print(f"Dropped columns not in df_cols: {cols_to_drop}")
        except Exception as e:
            print(f"Error dropping columns: {e}")
    
    # Map types
    for index, row in schema_df.iterrows():
        col = row['Column_Name'].upper()
        dtype = row['Data_Type']
        # Skip columns not in df_cols
        try:
            if col not in df_cols:
                dataframe = dataframe.drop(col, axis=1, inplace=True)
        except Exception as e:
            pass

        # Map Salesforce/Snowflake types to Pandas types
        if dtype.startswith('StringType') or dtype.startswith('VARCHAR'):
            schema_df.at[index, 'Pandas_Type'] = 'object'
        elif dtype.startswith('BooleanType') or dtype.startswith('BOOLEAN'):
            schema_df.at[index, 'Pandas_Type'] = 'bool'
        elif dtype.startswith('DecimalType') or dtype.startswith('NUMBER'):
            schema_df.at[index, 'Pandas_Type'] = 'float64'
        elif dtype.startswith('LongType') or dtype.startswith('INTEGER'):
            schema_df.at[index, 'Pandas_Type'] = 'int64'
        elif dtype.startswith('TimestampType') or dtype.startswith('TIMESTAMP'):
            schema_df.at[index, 'Pandas_Type'] = 'datetime64[ns]'
        elif dtype.startswith('DateType') or dtype.startswith('DATE'):
            schema_df.at[index, 'Pandas_Type'] = 'date'
        else:
            schema_df.at[index, 'Pandas_Type'] = 'unknown'
    
    return schema_df, dataframe