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

	if results.status_code > 200:
		print("you are not logged in")
		exit(0)
	for field in results.json()['fields']:
		
		if field['compoundFieldName'] is not None and field['compoundFieldName'] not in cfields and field['compoundFieldName'] != 'Name':
			cfields.append(field['compoundFieldName'])
	for row in results.json()['fields']:
		if row['name'] in cfields:
			continue
		if len(query_fields) == 0:
			pass
		else:
			query_fields +='+,'	
			
		query_fields += row['name']
		df_fields[row['name']] = field_types.df_field_type(row)
	query_string = "select+"+query_fields+"+from+{}".format(sobject)
	if lmd is not None:
		query_string = query_string + "+where+LastModifiedDate+>+{}".format(lmd)
	return query_string, df_fields