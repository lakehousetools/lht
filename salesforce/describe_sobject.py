import requests
import json
from util import field_types 
import tempfile
import pandas as pd
import numpy as np
from snowflake.connector.pandas_tools import write_pandas

version_number = "v60.0"

def create_query(access_info, query):
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	body = {
			"operation": "queryAll",
			"query": query
			}
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query"
	results = requests.post(url, headers=headers, data=json.dumps(body))
	print(results.json())
	print(access_info)
	return results.json()

def get_status(access_info, job_id):
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}".format(job_id)
	print("\n\nURL: {}".format(url))
	results = requests.get(url, headers=headers)
	print("\n\n@@@ RESULTS {}".format(results.text))
	
	return results.json()

def query_records(session, access_info, query, sobject, local_table, df_fields, table_fields, batch_size=1000):
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json",
			"Sforce-Query-Options": "batchSize={}".format(batch_size)
	}
	url = access_info['instance_url']+"/services/data/v58.0/queryAll?q={}".format(query)
	print(url)
	#exit(0)
	results = requests.get(url, headers=headers)
	if results.json()['totalSize'] == 0:
		print("nothing to process")
		exit(0)
	sobj_data = pd.json_normalize(results.json()['records'])
	#table_name = "TMP_{}".format(sobject)
	batch_counter = 1
	try:
		sobj_data.drop(columns=['attributes.type', 'attributes.url'], inplace=True)
	except:
		print("moving on")
	sobj_data = field_types.convert_field_types(sobj_data, df_fields, table_fields)
	try:
		session.write_pandas(sobj_data, 'TMP_{}'.format(local_table),quote_identifiers=False,use_logical_type = True)	
	except Exception as e:
		print(sobj_data)
		#print(sobj_data.head(10)[['ID', 'LASTACTIVITYDATE__C']])
		#print(sobj_data['LASTACTIVITYDATE__C'].dtype)
		print(e)
		exit(0)
	#	print(sobj_data)
	#	exit(0)
	while True:
		if 'nextRecordsUrl' in results.json() and results.json()['nextRecordsUrl'] is not None:
			batch_counter +=1
			print("batch TMP_{} - {} Records".format(local_table, len(sobj_data)))
			url = access_info['instance_url']+results.json()['nextRecordsUrl']
			#, data=json.dumps(body)
			results = requests.get(url, headers=headers)
			sobj_data = pd.json_normalize(results.json()['records'])
			sobj_data.drop(columns=['attributes.type', 'attributes.url'], inplace=True)
			sobj_data = field_types.convert_field_types(sobj_data, df_fields, table_fields)
			try:
				session.write_pandas(sobj_data, 'TMP_{}'.format(local_table),auto_create_table=False, overwrite=False,quote_identifiers=False,use_logical_type = True)	
			except Exception as e:
				print(e)
				print(results.json()['records'])
				exit(0)
		else:
			break
	return results.json()
	
def describe(session, access_info, sobject, lmd=None):
	headers = {
		"Authorization":"Bearer {}".format(access_info['access_token']),
		"Accept": "application/json"
	}

	field = {}
	fields = []
	try:
		url = access_info['instance_url'] + "/services/data/v58.0/sobjects/{}/describe".format(sobject)
	except Exception as e:
		print(e)
		return None
	results = requests.get(url, headers=headers)
	if results.status_code > 200:
		print("you are not logged in")
		exit(0)
	query_fields = ""
	#create_table_fields = ""
	create_table_fields = ''
	cfields = []
	df_fields = {}
	print(results.status_code)
	for field in results.json()['fields']:
		if field['compoundFieldName'] is not None and field['compoundFieldName'] not in cfields:
			cfields.append(field['compoundFieldName'])
	for row in results.json()['fields']:
		if row['name'] in cfields:
			continue
		if len(query_fields) == 0:
			print("first time")
		else:
			query_fields +='+,'
			create_table_fields +=','
			
		query_fields += row['name']
		create_table_fields+=row['name']+' '+ field_types.salesforce_field_type(row)
		#create_table_fields[row['name']] = field_types.salesforce_field_type(row)
		#converts the salesforce field type to a dataframe data type
		df_fields[row['name']] = field_types.df_field_type(row)
	query_string = "select+"+query_fields+"+from+{}".format(sobject)
	if lmd is not None:
		query_string = query_string + "+where+LastModifiedDate+>+{}".format(lmd)
	return query_string, df_fields, create_table_fields

def describe_sobjects_2(access_info, sobject, snowflake_fields, lmd=None):

	headers = {
		"Authorization":"Bearer {}".format(access_info['access_token']),
		"Accept": "application/json"
	}

	field = {}
	fields = []
	try:
		url = access_info['instance_url'] + "/services/data/v58.0/sobjects/{}/describe".format(sobject)
	except Exception as e:
		print(e)
		return None
	results = requests.get(url, headers=headers)
	query_fields = []
	cfields = []
	df_fields = {}
	for field in results.json()['fields']:
		if field['name'] == 'Name':
			continue
		if field['compoundFieldName'] is not None and field['compoundFieldName'] not in cfields:
			cfields.append(field['compoundFieldName'])
	for row in results.json()['fields']:
		if row['name'] in cfields:
			continue
		if row['name'].upper() not in snowflake_fields:
			continue
		else:
			query_fields.append(row['name'].upper())
		df_fields[row['name']] = util.df_field_type(row)
	query_string = f"SELECT {', '.join(query_fields)} FROM {sobject}"
	if lmd is not None:
		query_string = query_string + " where LastModifiedDate > {}".format(lmd)
	return query_string, df_fields

def get_results(session, access_info, job_id, schema, table, df_fields):

	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}

	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}/results".format(job_id)
	results = requests.get(url, headers=headers)
	print("\n\nRESULTS {}".format(results))
	while True:
		encoded_data = results.text.encode('utf-8')  # Encode CSV data to UTF-8 bytes
		with tempfile.NamedTemporaryFile(delete=False) as temp_file:
			temp_file.write(encoded_data)
			temp_file_path = temp_file.name
		print("  {}".format(temp_file_path))
		df = pd.read_csv(temp_file_path)
		print(df[['Id', 'CreatedDate', 'LastModifiedDate']])
		#exit(0)
		
		for col, dtype in df_fields.items():
			#if col == 'LastModifiedDate':
			#	print("\n\nLMD DTYPE {}".format(dtype))
			#if col == 'CreatedDate':
			#	print("\n\nCD DTYPE {}".format(dtype))
			if dtype == 'int64':
				df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
			elif dtype == 'object':
				df[col] = df[col].astype(str)
			elif dtype == 'float64':
				df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
			elif dtype == 'bool':
				df[col] = pd.to_numeric(df[col], errors='coerce').astype('bool')
			elif dtype == 'datetime64':
				#df[col] = pd.to_datetime(df[col], errors='coerce')
				df[col] = df[col].astype(str)
		df = df.replace(np.nan, None)
		#st.session_state['user_conn'].execute("USE WAREHOUSE {}".format())
		#write_pandas(session, df, schema=schema, table_name='TMP_'+table, quote_identifiers=False, auto_create_table=False, overwrite=True)
		session.write_pandas(df, 'TMP_'+table,quote_identifiers=False)
		if results.headers['Sforce-Locator']:
			break

	return df