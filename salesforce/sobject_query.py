import requests
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd
from util import field_types 
import json

def query_records(session, access_info, query, sobject, local_table, df_fields, table_fields, batch_size=1000):
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json",
			"Sforce-Query-Options": "batchSize={}".format(batch_size)
	}
	url = access_info['instance_url']+"/services/data/v58.0/queryAll?q={}".format(query)
	print(url)
	results = requests.get(url, headers=headers)
	if results.json()['totalSize'] == 0:
		print("nothing to process")
		exit(0)
	sobj_data = pd.json_normalize(results.json()['records'])
	batch_counter = 1
	try:
		sobj_data.drop(columns=['attributes.type', 'attributes.url'], inplace=True)
	except:
		print("moving on")
	sobj_data = field_types.convert_field_types(sobj_data, df_fields, table_fields)
	try:
		session.write_pandas(sobj_data, 'TMP_{}'.format(local_table),quote_identifiers=False,use_logical_type = True)	
	except Exception as e:
		#print(sobj_data)
		print(e)
		exit(0)
	while True:
		if 'nextRecordsUrl' in results.json() and results.json()['nextRecordsUrl'] is not None:
			batch_counter +=1
			url = access_info['instance_url']+results.json()['nextRecordsUrl']
			results = requests.get(url, headers=headers)
			sobj_data = pd.json_normalize(results.json()['records'])
			sobj_data.drop(columns=['attributes.type', 'attributes.url'], inplace=True)
			sobj_data = field_types.convert_field_types(sobj_data, df_fields, table_fields)
			try:
				session.write_pandas(sobj_data, 'TMP_{}'.format(local_table),auto_create_table=False, overwrite=False,quote_identifiers=False,use_logical_type = True)	
			except Exception as e:
				print(e)
				#print(results.json()['records'])
				exit(0)
		else:
			break
	return results.json()