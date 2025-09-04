import requests
from lht.util import field_types 

def describe(access_info, sobject, lmd=None):
	headers = {
		"Authorization":"Bearer {}".format(access_info['access_token']),
		"Accept": "application/json"
	}

	field = {}
	fields = []
	try:
		url = access_info['instance_url'] + "/services/data/v62.0/sobjects/{}/describe".format(sobject)
	except Exception as e:
		print(e)
		return None
	results = requests.get(url, headers=headers)
	if results.json()['retrieveable'] is False:
		return []
	
	query_fields = ""

	create_table_fields = ''
	cfields = []
	df_fields = {}
	snowflake_fields = {}  # For table creation with proper Snowflake types

	if results.status_code > 200:
		print("you are not logged in")
		exit(0)
	for field in results.json()['fields']:
		
		if field['compoundFieldName'] is not None and field['compoundFieldName'] not in cfields and field['compoundFieldName'] != 'Name':
			cfields.append(field['compoundFieldName'])
	for row in results.json()['fields']:
		# Skip compound fields
		if row['name'] in cfields:
			continue
		
		# Skip fields the user doesn't have access to
		if not row.get('accessible', True):
			print(f"⚠️ Skipping inaccessible field: {row['name']}")
			continue
		
		# Skip fields that can't be retrieved
		if not row.get('retrieveable', True):
			print(f"⚠️ Skipping non-retrievable field: {row['name']}")
			continue
		
		if len(query_fields) == 0:
			pass
		else:
			query_fields +='+,'	
			
		query_fields += row['name']
		df_fields[row['name']] = field_types.df_field_type(row)
		snowflake_fields[row['name']] = field_types.salesforce_field_type(row)
	query_string = "select+"+query_fields+"+from+{}".format(sobject)
	if lmd is not None:
		query_string = query_string + "+where+LastModifiedDate+>+{}".format(lmd)
	
	# Returning field descriptions from Salesforce
	print(f"  - df_fields keys: {list(df_fields.keys())}")
	print(f"  - df_fields values: {list(df_fields.values())}")
	print(f"  - snowflake_fields keys: {list(snowflake_fields.keys())}")
	print(f"  - snowflake_fields values: {list(snowflake_fields.values())}")
	
	return query_string, df_fields, snowflake_fields