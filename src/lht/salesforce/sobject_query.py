import requests
import pandas as pd
from lht.util import field_types

def query_records(access_info, query, batch_size=1000):
	"""
	Query Salesforce records and yield DataFrames for each batch.
	
	Args:
		session: Snowpark Session (passed for compatibility, not used in query).
		access_info: Dictionary with 'access_token' and 'instance_url'.
		query: Salesforce SOQL query string.
		batch_size: Number of records per batch (default: 1000).
	
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

	# Initial query
	results = requests.get(url, headers=headers)
	results.raise_for_status()  # Raise exception for HTTP errors
	json_data = results.json()

	if json_data['totalSize'] == 0:
		return None

	# Process first batch
	sobj_data = pd.json_normalize(json_data['records'])
	try:
		sobj_data.drop(columns=['attributes.type', 'attributes.url'], inplace=True)
	except KeyError:
		print("Attributes not found, moving on")
	
	#sobj_data = field_types.convert_field_types(sobj_data, df_fields, table_fields)

	# Replace NaT in datetime64 columns
	for col in sobj_data.select_dtypes(include=['datetime64']).columns:
		sobj_data[col] = sobj_data[col].fillna(pd.Timestamp('1900-01-01'))

	# Replace NaN in numeric columns
	for col in sobj_data.select_dtypes(include=['float64', 'int64']).columns:
		sobj_data[col] = sobj_data[col].fillna(0)

	# Replace None in String columns
	for col in sobj_data.select_dtypes(include=['object']).columns:
		sobj_data[col] = sobj_data[col].fillna('')

	sobj_data.columns =sobj_data.columns.str.upper()
	# Yield first batch
	yield sobj_data

	# Process subsequent batches
	while json_data.get('nextRecordsUrl'):
		url = f"{access_info['instance_url']}{json_data['nextRecordsUrl']}"
		results = requests.get(url, headers=headers)
		results.raise_for_status()
		json_data = results.json()

		sobj_data = pd.json_normalize(json_data['records'])
		sobj_data.columns =sobj_data.columns.str.upper()
		try:
			sobj_data.drop(columns=['attributes.type', 'attributes.url'], inplace=True)
		except KeyError:
			print("Attributes not found, moving on")
		
		#sobj_data = field_types.convert_field_types(sobj_data, df_fields, table_fields)

		# Replace NaT and NaN
		for col in sobj_data.select_dtypes(include=['datetime64']).columns:
			sobj_data[col] = sobj_data[col].fillna(pd.Timestamp('1900-01-01')) 
		for col in sobj_data.select_dtypes(include=['float64', 'int64']).columns:
			sobj_data[col] = sobj_data[col].fillna(0)
		for col in sobj_data.select_dtypes(include=['object']).columns:
			sobj_data[col] = sobj_data[col].fillna('')

		# Yield subsequent batch
		yield sobj_data