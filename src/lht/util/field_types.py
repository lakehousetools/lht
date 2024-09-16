import pandas as pd
import numpy as np
import tempfile


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
		return 'string({})'.format(field_type['length'])
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
		return 'timestamp_ntz'
	elif field_type['type'] == 'date':
		return 'date'
	elif field_type['type'] == 'address':
		return 'string({})'.format(field_type['length'])
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
		return 'datetime64[ns]'
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
		#if col =='LastModifiedDate' or col =='CreatedDate':
		#	df[col] = pd.to_numeric(pd.to_datetime(df[col], errors='coerce'), errors='coerce').astype('Int64')/1000000000
		if col == 'Last_Activity_Date__c':
			df[col] = pd.to_datetime(df[col],errors='coerce').dt.date
			print(df[col])
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
	for col, dtype in df_fields.items():
		try:
			if dtype == 'int64':
				df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
			elif dtype == 'object':
				df[col] = df[col].astype(str)
			elif dtype == 'float64':
				df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
			elif dtype == 'bool':
				df[col] = pd.to_numeric(df[col], errors='coerce').astype('bool')
			elif dtype == 'datetime64':
				df[col] = pd.to_datetime(df[col], errors='coerce')
				#df[col] = df[col].astype(str)
		except Exception as e:
			print("field not found {}".format(e))
	return df