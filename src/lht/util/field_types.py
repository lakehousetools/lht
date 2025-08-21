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
		return 'datetime64[ns]'  # Fix: date fields should be datetime64[ns], not object
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
	
	if force_datetime_to_string:
		print("⚠️  FORCE_DATETIME_TO_STRING is enabled - all datetime fields will be converted to strings")
	
	for col, dtype in df_fields.items():
		# Convert field name to uppercase to match DataFrame columns
		col_upper = col.upper()
		try:
			if col_upper in df.columns:
				# CRITICAL: Force fields to their intended types BEFORE any data analysis
				# This ensures write_pandas creates the correct table schema
				if dtype == 'datetime64' or dtype == 'datetime64[ns]':
					# Salesforce datetime/date fields (like CreatedDate, LastViewedDate, LastActivityDate) MUST be datetime
					df[col_upper] = pd.to_datetime(df[col_upper], errors='coerce', utc=True)
					
					# Check if we have timezone-aware datetimes and convert to timezone-naive
					if hasattr(df[col_upper], 'dt') and hasattr(df[col_upper].dt, 'tz'):
						tz_info = df[col_upper].dt.tz
						if tz_info is not None:
							df[col_upper] = df[col_upper].dt.tz_localize(None)
					
					# Check if we still have numeric data after datetime conversion
					if df[col_upper].dtype in ['int64', 'float64']:
						df[col_upper] = df[col_upper].astype(str)
						df[col_upper] = df[col_upper].replace({'nan': None, 'None': None, '<NA>': None})
						
				elif dtype == 'object':
					# Salesforce string fields (including PO_Number__c) MUST be strings
					# Convert to string immediately, regardless of content
					df[col_upper] = df[col_upper].replace({pd.NA: None, pd.NaT: None})
					df[col_upper] = df[col_upper].astype(str)
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
						df[col_upper] = df[col_upper].astype(str)
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
							

			else:
				print(f"field not found '{col_upper}' in DataFrame columns: {list(df.columns)}")
		except Exception as e:
			print(f"field not found '{col_upper}': {e}")
	return df