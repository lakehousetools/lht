import requests
import logging
from lht.util import field_types
from lht.exceptions import SalesforceAuthError, SalesforceAPIError

logger = logging.getLogger(__name__)

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
		logger.error(e)
		return None
	results = requests.get(url, headers=headers)

	# Check the HTTP status before touching the body - an auth failure or other
	# error response won't have a 'retrieveable' key, so parsing it first raises
	# a confusing TypeError/KeyError instead of a clear error.
	if results.status_code == 401:
		logger.error(f"Salesforce session is invalid or expired (describe {sobject})")
		raise SalesforceAuthError(
			f"Salesforce authentication failed while describing '{sobject}' (HTTP 401). "
			"The access token is invalid or expired."
		)
	if results.status_code >= 300:
		logger.error(f"Salesforce describe request for {sobject} failed: HTTP {results.status_code}")
		raise SalesforceAPIError(
			f"Salesforce describe request for '{sobject}' failed with HTTP {results.status_code}: "
			f"{results.text[:500]}"
		)

	response_json = results.json()
	if response_json.get('retrieveable') is False:
		return []

	query_fields = ""

	create_table_fields = ''
	cfields = []
	df_fields = {}
	snowflake_fields = {}  # For table creation with proper Snowflake types

	for field in response_json['fields']:
		
		if field['compoundFieldName'] is not None and field['compoundFieldName'] not in cfields and field['compoundFieldName'] != 'Name':
			cfields.append(field['compoundFieldName'])
	for row in response_json['fields']:
		# Skip compound fields
		if row['name'] in cfields:
			continue
		
		# Skip fields the user doesn't have access to
		if not row.get('accessible', True):
			logger.warning(f"⚠️ Skipping inaccessible field: {row['name']}")
			continue
		
		# Skip fields that can't be retrieved
		if not row.get('retrieveable', True):
			logger.warning(f"⚠️ Skipping non-retrievable field: {row['name']}")
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
	#logger.debug(f"  - df_fields keys: {list(df_fields.keys())}")
	#logger.debug(f"  - df_fields values: {list(df_fields.values())}")
	#logger.debug(f"  - snowflake_fields keys: {list(snowflake_fields.keys())}")
	#logger.debug(f"  - snowflake_fields values: {list(snowflake_fields.values())}")
	
	return query_string, df_fields, snowflake_fields