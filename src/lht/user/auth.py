import os
import requests		
from snowflake.snowpark import Session
import json

def salesforce_oauth(session, token, prod):
	headers = {'content-Type': 'application/x-www-form-urlencoded'}
	if prod == 1:
		payload = {
			'grant_type': 'refresh_token',
			'client_id': '3MVG9cHH2bfKACZbozJZ6VCTB.WIZcgxpPRcobzSVrhJW3.IEaOjkgUIVgWZkjJSIxZ2Zohhdg5uXjrqUF4HC',
			'client_secret': 'C888F0F7EC1282FEB7D5A1A2C332811F12141656EFA903021CC696A799D4FCEF',
			'refresh_token': token
		}
		url = 'https://login.salesforce.com/services/oauth2/token'
	else:
		payload = {
			'grant_type': 'refresh_token',
			'client_id': "3MVG9Fy_1ZngbXqMGJuvaHbjmcGSzHnuNv3uxUwd0LnP0ZVVt65agq9pN13nXCpFc8V4aPUh2O.fGYMT1kcq3",
			'client_secret': "D9766BA5DF3351CB03F960AA1A6B64F61280AE5C8F8FFC3A02F174D69739FA89",
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