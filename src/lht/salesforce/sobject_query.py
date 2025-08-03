import requests
import pandas as pd
from lht.util import field_types

def query_records(access_info, query, batch_size=1000):
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

	results = requests.get(url, headers=headers)
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

	sobj_data.columns =sobj_data.columns.str.upper()

	yield sobj_data

	while json_data.get('nextRecordsUrl'):
		url = f"{access_info['instance_url']}{json_data['nextRecordsUrl']}"
		results = requests.get(url, headers=headers)
		results.raise_for_status()
		json_data = results.json()

		sobj_data = pd.json_normalize(json_data['records'])
		sobj_data.columns =sobj_data.columns.str.upper()
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