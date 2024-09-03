import requests		
from snowflake.snowpark import Session

connection_parameters = {
    "account": "jwa11064",
    "user": "dankauppi",
    "password": "O^ICSPqkc33&",
    "role": "DTSO_PROVIDER",  # optional
    "warehouse": "DTSO_WH",  # optional
    "database": "DTSO_PROVIDER_DATA",  # optional
    "schema": "CORE",  # optional
}  

dtso_session = Session.builder.configs(connection_parameters).create() 

def get_refresh_token(session, user_name):
	query = """select 
			s.REFRESH_TOKEN,
			u.USER_NAME,
			CASE
			when i.custom_domain ilike '%.sandbox.%' then 0
			else 1
			end as PRODUCTION,
			u.org_id
			from DTSO_PROVIDER_DATA.CORE.SESSION s
			join DTSO_PROVIDER_DATA.CORE.USER u
			ON u.ORG_ID = s.ORG_ID and u.USER_ID = s.USER_ID
			join DTSO_PROVIDER_DATA.CORE.INSTANCE i
			on i.org_id = u.org_id
			where user_name = \'{}\'""".format(user_name)
	results_df = dtso_session.sql(query).collect()
	refresh_token = results_df[0]['REFRESH_TOKEN']
	prod = results_df[0]['PRODUCTION']
	org_id = results_df[0]['ORG_ID']
	
	return refresh_token, prod, org_id

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
	