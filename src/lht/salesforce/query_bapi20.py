import requests
import json
import pandas as pd
import numpy as np
from . import sobjects
from lht.util import field_types
import os

def create_batch_query(access_info, query):
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	body = {
			"operation": "queryAll",
			"query": query
			}
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query"
	results = requests.post(url, headers=headers, data=json.dumps(body))
	
	return results.json()

def query_status(access_info, job_type, job_id):
	if job_id == 'None':
		job_id = None
	#if job_type == 'None':
	#	job_type = None
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	if job_id is None:
		url = access_info['instance_url']+"/services/data/v58.0/jobs/query/"
	else:
		url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}".format(job_id)
	#results = requests.get(url, headers=headers)
	query_statuses = []

	while True:
		results = requests.get(url, headers=headers)
		if isinstance(results.json(), dict):
			query_statuses.append(results.json())
			break
		if results.status_code > 200:
			print("not logged in")
			exit(0)
		records = len(results.json()['records'])
		for result in results.json()['records']:
			if result['jobType'] == job_type:
				query_statuses.append(result)
		if results.json()['nextRecordsUrl'] is not None:
				url = access_info['instance_url']+results.json()['nextRecordsUrl']
		else:
			break
	return query_statuses

def delete_query(access_info, job_id):

	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}".format(job_id)
	results = requests.delete(url, headers=headers)

	return results

def get_query_ids(access_info):

	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/"
	while True:
		results = requests.get(url, headers=headers)
		jobs = []
		job = {}
		for result in results.json()['records']:
			if result['jobType'] == 'Classic':
				continue
			job['id'] = result['id']
			job['jobType'] = result['jobType']
			job['operation'] = result['operation']
			job['object'] = result['object']
			job['createdDate'] = result['createdDate']
			job['state'] = result['state']
			jobs.append(job)
			job = {}
		if results.json()['nextRecordsUrl'] is not None:
				url = access_info['instance_url']+results.json()['nextRecordsUrl']
		else:
			break

	return jobs

def get_bulk_results(session, access_info, job_id, sobject, schema, table):
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}/results".format(job_id)
	results = requests.get(url, headers=headers)
	if results.status_code != 200:
		print('The job is not ready.  Retry in a few minutes')
		return None
	#while True:
	else:
		temp_file_path = field_types.cache_data(results.text.encode('utf-8'))
		df = pd.read_csv(temp_file_path)
		print("\n\nFILE 1:{}".format(temp_file_path))
		query_string, df_fields = sobjects.describe(access_info, sobject)

		formatted_df = field_types.format_sync_file(df, df_fields)

		formatted_df = formatted_df.replace(np.nan, None)

		#formatted_df = formatted_df[string_columns].fillna('')
		schema_table = schema+"."+table

		session.write_pandas(formatted_df, schema_table, quote_identifiers=False, auto_create_table=True, overwrite=True,use_logical_type=True, on_error="CONTINUE")
		#print("\n\nHEADERS {}".format(results.headers))
		if os.path.exists(temp_file_path):
			# Remove the file
			os.remove(temp_file_path)
		counter = 2
		while True:
			if 'Sforce-Locator' not in results.headers:			
				break
			elif results.headers['Sforce-Locator'] == 'null':
				break
			#print("\n\nHEADERS {}".format(results.headers))

			url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}/results?locator={}".format(job_id,results.headers['Sforce-Locator'])
			results = requests.get(url, headers=headers)
			temp_file_path = field_types.cache_data(results.text.encode('utf-8'))
			print("\n\nFILE {}:{}".format(counter, temp_file_path))
			counter += 1
			df = pd.read_csv(temp_file_path)
			formatted_df = field_types.format_sync_file(df, df_fields)
			formatted_df = formatted_df.replace(np.nan, None)
		
			schema_table = schema+"."+table
			session.write_pandas(formatted_df, schema_table, quote_identifiers=False, auto_create_table=False, overwrite=False,use_logical_type=True, on_error="CONTINUE")
			if os.path.exists(temp_file_path):
				# Remove the file
				os.remove(temp_file_path)
	return results