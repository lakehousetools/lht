import os
import requests		
from snowflake.snowpark import Session
import toml
import json

def sf_login():
	file_path = './.snowflake/sfdc.json'

	# Open the JSON file for reading
	with open(file_path, 'r') as file:
		# Load the JSON data from the file
		data = json.load(file)

	# Now 'data' is a Python dictionary or list 
	# (depending on what the JSON file contains)
	return data	


def get_salesforce_token(session, sfdc_info, username):
	print('here')
	config = toml.load(".snowflake/connections.toml")
	salesforce_access = config[sfdc_info]
	#salesforce_tokens = sf_login()
	print("\n\nUSER {}".format(username))
	refresh_token = get_user(session, username)
	print("\n\nREFRESH TOKEN {}".format(refresh_token))
	headers = {'content-Type': 'application/x-www-form-urlencoded'}
	if salesforce_access['sandbox']== False:
		print("here {}".format(refresh_token))
		payload = {
			'grant_type': 'refresh_token full',
			'client_id': salesforce_access['CLIENT_ID'],
			'client_secret': salesforce_access['CLIENT_SECRET'],
			'refresh_token': refresh_token
		}
		#url = 'https://login.salesforce.com/services/oauth2/token'
		url = """https://login.salesforce.com/services/oauth2/token?grant_type=refresh_token&client_id={}&client_secret={}&refresh_token={}""".format(salesforce_access['CLIENT_ID'], salesforce_access['CLIENT_SECRET'], refresh_token)
	else:
		payload = {
			'grant_type': 'refresh_token',
			'client_id': salesforce_access['CLIENT_ID'],
			'client_secret': salesforce_access['CLIENT_SECRET'],
			'refresh_token': refresh_token
		}
		url = """https://test.salesforce.com/services/oauth2/token?grant_type=refresh_token&client_id={}&client_secret={}&refresh_token={}""".format(salesforce_access['CLIENT_ID'], salesforce_access['CLIENT_SECRET'], refresh_token)	
	print(url)

	r = requests.post(url, headers=headers)
	print("\n@@@ {}".format(r.json()))
	return r.json()
	
def get_access_token():
	current_dir = os.path.dirname(os.path.abspath(__file__))
	creds_path = os.path.join(current_dir, '..', '.snowflake', 'token.json')
	with open(creds_path, 'r') as file:
		file_str = file.read()
	access_info = file_str.replace("'", '"')
	return json.loads(access_info)

def get_snowflake_connection(connection_name):
	config = toml.load(".snowflake/connections.toml")
	snowflake_config = config[connection_name]

	connection_parameters = {
		"account": snowflake_config["account"],
		"user": snowflake_config["user"],
		"password": snowflake_config["password"],
		"warehouse": snowflake_config["warehouse"],
		"database": snowflake_config["database"],
		"schema": snowflake_config["schema"]
	}
	sessionBuilder = Session.builder
	for key, value in connection_parameters.items():
		sessionBuilder.config(key, value)

	session = sessionBuilder.create()
	return session

def get_user(session, user):
	print(user)
	query = """with user as (
			select ORG_ID, USER_ID, USER_NAME, EMAIL from DTSO_PROVIDER_DATA.CORE.USER
		),
		session as (
			select ORG_ID, USER_ID, REFRESH_TOKEN, ISSUED_AT, CREATED_DATE, LAST_MODIFIED_DATE, SESSION_COOKIE from DTSO_PROVIDER_DATA.CORE.SESSION
		)
		select 
		u.org_id,
		u.user_id,
		u.user_name,
		s.refresh_token
		from user u
		join session s
		on s.org_id = u.org_id and s.user_id = u.user_id
		where user_name = \'{}\'""".format(user)
	results = session.sql(query).collect()
	#for result in results:
		#schema['name'] = result['SPECIALTY']
		#schemas.append(schema)
		#schema = {}
	print("\n\nRESULT {}\n\n".format(results))
	if len(results) == 0:
		print("invalid user")
		exit(0)
	return results[0][3]

def get_snowflake_connection(connection_name):
	config = toml.load(".snowflake/connections.toml")
	snowflake_config = config[connection_name]

	connection_parameters = {
		"account": snowflake_config["account"],
		"user": snowflake_config["user"],
		"password": snowflake_config["password"],
		"warehouse": snowflake_config["warehouse"],
		"database": snowflake_config["database"],
		"schema": snowflake_config["schema"]
	}
	sessionBuilder = Session.builder
	for key, value in connection_parameters.items():
		sessionBuilder.config(key, value)

	session = sessionBuilder.create()
	return session