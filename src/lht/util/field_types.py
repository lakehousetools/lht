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
		return 'string({})'.format(field_type['length'])
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
	elif field_type['type'] == 'int':
		return 'number(32)'
	elif field_type['type'] == 'junctionidlist':
		return 'string(18)'
	elif field_type['type'] == 'reference':
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
		#return 'datetime64[ns]'
		return 'object'
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

def convert_df2snowflake(df, table_fields):
	print(table_fields)
	for field in table_fields:
		if field not in df.columns:
			continue
		if table_fields[field].startswith('TIMESTAMP_NTZ'):
			df[field] = pd.to_datetime(df[field], errors='coerce').fillna(pd.Timestamp('1900-01-01'))
		if table_fields[field].startswith('DATE'):
			df[field] = pd.to_datetime(df[field].astype(str), format='%Y%m%d', errors='coerce').fillna(pd.Timestamp('1900-01-01'))
			df[field] = df[field].dt.strftime('%Y-%m-%d')
		elif table_fields[field].startswith('VARCHAR'):
			df[field] = df[field].astype(str)
		elif table_fields[field] == 'BOOLEAN':
			df[field] = pd.to_numeric(df[field], errors='coerce').astype('bool')
		elif table_fields[field].startswith('NUMBER'):
			match = re.match(r'(NUMBER)\((\d+),(\d+)\)', table_fields[field])
			if match:
				scale = int(match.group(3))  # Extract scale
				if scale == 0:
					df[field] = pd.to_numeric(df[field], errors='coerce').astype('Int64') 
				else:
					df[field] = pd.to_numeric(df[field], errors='coerce').astype('float64') 
			#df[field] = df[field].astype(str)

	return df

def cache_data(data):
	with tempfile.NamedTemporaryFile(delete=False) as temp_file:
		temp_file.write(data)
		temp_file_path = temp_file.name
	#print("  {}".format(temp_file_path))
	return temp_file_path


def format_sync_file(df, df_fields, force_datetime_to_string=False):
	# First, convert all column names to uppercase to match Salesforce API response
	df.columns = df.columns.str.upper()
	
	print(f"🔍 DEBUG: DataFrame columns after uppercase: {list(df.columns)}")
	print(f"🔍 DEBUG: df_fields keys: {list(df_fields.keys())}")
	
	if force_datetime_to_string:
		print("⚠️  FORCE_DATETIME_TO_STRING is enabled - all datetime fields will be converted to strings")
	
	for col, dtype in df_fields.items():
		# Convert field name to uppercase to match DataFrame columns
		col_upper = col.upper()
		print(f"🔍 DEBUG: Processing field '{col}' -> '{col_upper}', dtype: '{dtype}'")
		try:
			if col_upper in df.columns:
				# CRITICAL: Force fields to their intended types BEFORE any data analysis
				# This ensures write_pandas creates the correct table schema
				if dtype == 'datetime64':
					# Salesforce datetime fields (like CreatedDate) MUST be datetime
					print(f"🔧 Processing datetime field: {col_upper}")
					
					# Show sample values and their types to help debug
					sample_values = df[col_upper].dropna().head(5).tolist()
					sample_types = [type(x).__name__ for x in sample_values]
					print(f"📅 Sample values for {col_upper}: {sample_values}")
					print(f"📅 Sample value types: {sample_types}")
					
					# Option 1: Force all datetime fields to string (if flag is set)
					if force_datetime_to_string:
						print(f"⚠️  FORCE_DATETIME_TO_STRING enabled - converting {col_upper} to string")
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
						continue
					
					# Option 2: Auto-detect problematic Salesforce ISO 8601 format
					if any(isinstance(x, str) and ('T' in str(x) or '.000Z' in str(x)) for x in sample_values):
						print(f"⚠️  {col_upper} contains Salesforce ISO 8601 format - converting to string to avoid parsing issues")
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
						continue
					
					# Option 3: Try to convert to datetime (default behavior)
					try:
						df[col_upper] = pd.to_datetime(df[col_upper], errors='coerce')
						# Convert to timezone-naive timestamps for Snowflake compatibility
						df[col_upper] = df[col_upper].dt.tz_localize(None)
						print(f"✅ {col_upper} successfully converted to datetime64")
					except Exception as e:
						print(f"⚠️ Warning: Could not convert {col_upper} to datetime64, treating as string: {e}")
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
						
				elif dtype == 'object':
					# Salesforce string fields (including PO_Number__c) MUST be strings
					# Convert to string immediately, regardless of content
					print(f"🔧 Forcing {col_upper} to string type (Salesforce field type: {dtype})")
					print(f"🔍 DEBUG: Before conversion - {col_upper} dtype: {df[col_upper].dtype}")
					df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
					df[col_upper] = df[col_upper].astype(str)
					df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					print(f"🔍 DEBUG: After conversion - {col_upper} dtype: {df[col_upper].dtype}")
					
				elif dtype == 'int64':
					# Check if ANY value is non-numeric - if so, convert entire column to string
					has_non_numeric = False
					for value in df[col_upper].dropna():
						if isinstance(value, str) and not value.replace('-', '').replace('.', '').isdigit():
							has_non_numeric = True
							break
					
					if has_non_numeric:
						# Convert entire column to string - no mixed types allowed in Snowflake
						print(f"⚠️ Column {col_upper} contains non-numeric values, converting entire column to string")
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					else:
						# All values are numeric, safe to convert
						try:
							df[col_upper] = pd.to_numeric(df[col_upper], errors='coerce').astype('Int64')
						except Exception as e:
							print(f"⚠️ Warning: Could not convert {col_upper} to int64, treating as string: {e}")
							df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
							df[col_upper] = df[col_upper].astype(str)
							df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
							
				elif dtype == 'float64':
					# Similar logic for float fields - check for non-float values
					has_non_float = False
					for value in df[col_upper].dropna():
						if isinstance(value, str):
							try:
								float(value)
							except ValueError:
								has_non_float = True
								break
					
					if has_non_float:
						# Convert entire column to string
						print(f"⚠️ Column {col_upper} contains non-float values, converting entire column to string")
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					else:
						# All values are float, safe to convert
						try:
							df[col_upper] = pd.to_numeric(df[col_upper], errors='coerce').astype('float64')
						except Exception as e:
							print(f"⚠️ Warning: Could not convert {col_upper} to float64, treating as string: {e}")
							df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
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
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
					else:
						# All values are boolean-like, safe to convert
						try:
							df[col_upper] = pd.to_numeric(df[col_upper], errors='coerce').astype('bool')
						except Exception as e:
							print(f"⚠️ Warning: Could not convert {col_upper} to bool, treating as string: {e}")
							df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
							df[col_upper] = df[col_upper].astype(str)
							df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
							
				elif dtype == 'datetime64':
					# Handle Salesforce timestamps (could be ISO 8601 strings or epoch time integers)
					try:
						print(f"🔧 Processing {col_upper} for datetime conversion...")
						
						# Check if we have epoch time (large integers) or string timestamps
						sample_values = df[col_upper].dropna().head(3)
						print(f"🔍 Sample values in {col_upper}: {sample_values.tolist()}")
						
						if df[col_upper].dtype in ['int64', 'float64'] or (df[col_upper].dtype == 'object' and 
						   any(isinstance(x, (int, float)) or (isinstance(x, str) and x.replace('.', '').replace('-', '').isdigit()) 
						       for x in sample_values if pd.notna(x))):
							# Handle epoch time (Unix timestamps)
							print(f"🔧 Converting {col_upper} from epoch time to datetime...")
							df[col_upper] = pd.to_datetime(df[col_upper], unit='ms', errors='coerce')  # Try milliseconds first
							
							# If that fails, try seconds
							if df[col_upper].isna().all():
								print(f"🔧 Retrying {col_upper} with seconds unit...")
								df[col_upper] = pd.to_datetime(df[col_upper], unit='s', errors='coerce')
						else:
							# Handle string timestamps (ISO 8601 format)
							print(f"🔧 Converting {col_upper} from string format to datetime...")
							# Handle Salesforce format: 2023-09-08T02:00:39.000Z
							if df[col_upper].dtype == 'object':
								# Convert to pandas datetime first
								df[col_upper] = pd.to_datetime(df[col_upper], errors='coerce')
							
							# Convert to datetime
							df[col_upper] = pd.to_datetime(df[col_upper], errors='coerce')
						
						# Convert to timezone-naive timestamps for Snowflake compatibility
						df[col_upper] = df[col_upper].dt.tz_localize(None)
						
						print(f"🔧 Successfully converted {col_upper} to datetime64")
					except Exception as e:
						print(f"⚠️ Warning: Could not convert {col_upper} to datetime64, treating as string: {e}")
						df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
			else:
				print(f"field not found '{col_upper}' in DataFrame columns: {list(df.columns)}")
		except Exception as e:
			print(f"field not found '{col_upper}': {e}")
	return df