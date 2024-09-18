import os
import requests		
from snowflake.snowpark import Session
import json

def salesforce_oauth(session, token, prod):
	headers = {'content-Type': 'application/x-www-form-urlencoded'}
	if prod == 1:
		payload = {
			'grant_type': 'refresh_token',
			'client_id': 'REDACTED_CLIENT_ID',
			'client_secret': 'REDACTED',
			'refresh_token': token
		}
		url = 'https://login.salesforce.com/services/oauth2/token'
	else:
		payload = {
			'grant_type': 'refresh_token',
			'client_id': "REDACTED_CLIENT_ID",
			'client_secret': "REDACTED",
			'refresh_token': token
		}
		url = 'https://test.salesforce.com/services/oauth2/token'		

	r = requests.post(url, headers=headers, data=payload)
	return r.json()
	
def get_access_token():
	current_dir = os.path.dirname(os.path.abspath(__file__))
	creds_path = os.path.join(current_dir, '..', '.snowflake', 'token.json')
	with open(creds_path, 'r') as file:
		file_str = file.read()
	access_info = file_str.replace("'", '"')
	return json.loads(access_info)