import requests
import logging
from . import sobjects as sobj
from lht.util import field_types

logger = logging.getLogger(__name__)

def create(session, access_info, sobject, local_table):
	headers = {
		"Authorization":"Bearer {}".format(access_info['access_token']),
		"Accept": "application/json"
	}
	fields = ''
	try:
		url = access_info['instance_url'] + "/services/data/v58.0/sobjects/{}/describe".format(sobject)
	except Exception as e:
		logger.error(e)
		return None
	sobject_data = requests.get(url, headers=headers)

	for field_data in sobject_data.json()['fields']:
		if field_data['type'] == 'complexvalue':
			continue
		# if field_data['type'] == 'address':
		# 	continue
		# if field_data['compoundFieldName'] is None and field_data['compoundFieldName'] != 'Name':
		fields = fields + field_data['name'] + ' ' + field_types.salesforce_field_type(field_data) + ','


	query = "CREATE OR REPLACE TABLE {} ({})".format(local_table, fields[:-1])
	logger.debug(f"Query: {query}")

	results = session.sql(query).collect()
	return results[0]['status']