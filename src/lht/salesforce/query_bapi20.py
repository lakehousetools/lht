import requests
import json
import pandas as pd
import numpy as np
import io
from . import sobjects
from lht.util import field_types
from lht.util import stage
from lht.util import table_creator
import os
from lht.util import merge


def create_batch_query(access_info, query):
	"""Creates a batch query job in Salesforce using the Bulk Query API.

	Args:
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) and 'instance_url' (str).
		query (str): SOQL query to execute (e.g., 'SELECT Id, Name FROM Account').

	Returns:
		dict: JSON response from Salesforce containing job details (e.g., job ID).

	Raises:
		requests.exceptions.RequestException: If the API request fails (e.g., network error, invalid token).
		json.JSONDecodeError: If the response is not valid JSON.
	"""
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
	"""Retrieves the status of Salesforce query jobs.

	Args:
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) and 'instance_url' (str).
		job_type (str): Type of job to filter (e.g., 'Query', 'QueryAll'). If 'None', no filtering by type.
		job_id (str): Specific job ID to query, or 'None' to retrieve all jobs.

	Returns:
		list: List of dictionaries containing job status details (e.g., ID, state).

	Raises:
		requests.exceptions.RequestException: If the API request fails (e.g., invalid token, network error).
		json.JSONDecodeError: If the response is not valid JSON.
		SystemExit: If the API returns a non-200 status code indicating authentication failure.
	"""
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
			print(results.status_code)
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
	"""Deletes a Salesforce query job by ID.

	Args:
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) and 'instance_url' (str).
		job_id (str): ID of the query job to delete.

	Returns:
		requests.Response: HTTP response object from the DELETE request.

	Raises:
		requests.exceptions.RequestException: If the API request fails (e.g., invalid job ID, network error).
	"""
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}".format(job_id)
	results = requests.delete(url, headers=headers)

	return results

def get_query_ids(access_info):
	"""Retrieves a list of active Salesforce query job IDs and their details.

	Args:
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) and 'instance_url' (str).

	Returns:
		list: List of dictionaries containing job details (e.g., id, jobType, operation, object, createdDate, state).
			Excludes jobs with jobType 'Classic'.

	Raises:
		requests.exceptions.RequestException: If the API request fails (e.g., invalid token, network error).
		json.JSONDecodeError: If the response is not valid JSON.
	"""
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

def get_bulk_results_direct(session, access_info, job_id, sobject, schema, table, snowflake_fields=None, database=None, force_full_sync=False):
	print(f"🔍 get_bulk_results_direct called with force_full_sync={force_full_sync}")
	print(f"🔍 force_full_sync type: {type(force_full_sync)}")
	print(f"🔍 force_full_sync value: {repr(force_full_sync)}")
	
	# Auto-detect database if not provided
	if database is None:
		database = session.sql('SELECT CURRENT_DATABASE()').collect()[0][0]
	"""Fetches and processes bulk query results from Salesforce, loading them directly into a Snowflake table.

	Args:
		session (snowflake.snowpark.Session): Snowpark session for Snowflake operations.
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) and 'instance_url' (str).
		job_id (str): ID of the query job to retrieve results for.
		sobject (str): Salesforce SObject type (e.g., 'Account', 'Contact').
		schema (str): Snowflake schema name (e.g., 'RAW').
		table (str): Snowflake table name to load results into.
		database (str, optional): Snowflake database name. If not provided, uses current database.

	Returns:
		requests.Response: HTTP response object from the last API request, or None if the job is not ready.

	Raises:
		requests.exceptions.RequestException: If the API request fails (e.g., invalid job ID, network error).
		pandas.errors.EmptyDataError: If the CSV data is empty or malformed.
		snowflake.snowpark.exceptions.SnowparkSQLException: If Snowflake write operation fails.
	"""
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}/results".format(job_id)
	results = requests.get(url, headers=headers)
	if results.status_code != 200:
		print('The job is not ready.  Retry in a few minutes')
		return None
	
	# Always get both field types from describe to ensure we have the correct information
	query_string, df_fields, snowflake_fields = sobjects.describe(access_info, sobject)
	
	# Process first batch
	csv_content = results.text
	print(f"\n\nPROCESSING BATCH 1")
	
	# Load and process data directly (no stage upload needed)
	# CRITICAL: Force string reading to prevent pandas from converting numeric strings to floats
	# This prevents "20" from becoming 20.0 and then "20.0"
	df = pd.read_csv(io.StringIO(csv_content), dtype=str)
	
	# Set the current database and schema context
	session.sql(f"USE DATABASE {database}").collect()
	session.sql(f"USE SCHEMA {schema}").collect()
	
	# Use centralized table creation utility
	try:
		print(f"🚀 Creating table {schema}.{table}...")
		table_creator.ensure_table_exists_for_dataframe(
			session=session,
			schema=schema,
			table=table,
			df_fields=df_fields,
			snowflake_fields=snowflake_fields,
			force_full_sync=force_full_sync,
			database=database
		)
		print(f"✅ Table creation completed successfully")
				
		df_str = df.astype(str)
		df = None
		print(f"📊 Processing first batch of data")
		session.write_pandas(df_str, schema=schema, table_name="tmp_"+table, auto_create_table=True, overwrite=True, quote_identifiers=False, table_type="temporary")
		df_str = None
		transformed_data = merge.transform_and_match_datatypes(session, "tmp_"+table, table)
		session.sql(f"Insert into {table} select {transformed_data} from tmp_{table}").collect()
		print(f"✅ First batch loaded successfully")
	except Exception as e:
		print(f"❌ Failed to create table or load data: {e}")
		raise Exception(f"Failed to load data into table {schema}.{table}: {e}")
	
	# Process remaining batches

	counter = 2
	while True:
		if 'Sforce-Locator' not in results.headers:			
			break
		elif results.headers['Sforce-Locator'] == 'null':
			break

		url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}/results?locator={}".format(job_id, results.headers['Sforce-Locator'])
		results = requests.get(url, headers=headers)
		csv_content = results.text
		print(f"\n\nPROCESSING BATCH {counter}")
		
		# CRITICAL: Force string reading to prevent pandas from converting numeric strings to floats
		# This prevents "20" from becoming 20.0 and then "20.0"
		df = pd.read_csv(io.StringIO(csv_content), dtype=str)
		

		df_str = df.astype(str)
		df = None
		print(f"📊 Processing batch {counter}")
		session.write_pandas(df_str, schema=schema, table_name="tmp_"+table, auto_create_table=True, overwrite=True, quote_identifiers=False, table_type="temporary")
		transformed_data = merge.transform_and_match_datatypes(session, "tmp_"+table, table)
		session.sql(f"Insert into {table} select {transformed_data} from tmp_{table}").collect()
		print(f"✅ Batch {counter} loaded successfully using save_as_table")
		df_str = None
		counter += 1
	
	return results

def get_bulk_results(session, access_info, job_id, sobject, schema, table, snowflake_fields=None, use_stage=False, stage_name=None, database=None, force_full_sync=False):
	"""Fetches and processes bulk query results from Salesforce, loading them into a Snowflake table.
	
	This function now uses direct DataFrame-to-table loading for optimal performance.

	Args:
		session (snowflake.snowpark.Session): Snowpark session for Snowflake operations.
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) and 'instance_url' (str).
		job_id (str): ID of the query job to retrieve results for.
		sobject (str): Salesforce SObject type (e.g., 'Account', 'Contact').
		schema (str): Snowflake schema name (e.g., 'RAW').
		table (str): Snowflake table name to load results into.
		use_stage (bool, optional): Deprecated - kept for backward compatibility. Default False.
		stage_name (str, optional): Deprecated - kept for backward compatibility.
		database (str, optional): Snowflake database name. If not provided, uses current database.

	Returns:
		requests.Response: HTTP response object from the last API request, or None if the job is not ready.

	Raises:
		requests.exceptions.RequestException: If the API request fails (e.g., invalid job ID, network error).
		pandas.errors.EmptyDataError: If the CSV data is empty or malformed.
		snowflake.snowpark.exceptions.SnowparkSQLException: If Snowflake write operation fails.
	"""
	print(f"🔍 get_bulk_results called with force_full_sync={force_full_sync}")
	print(f"🔍 force_full_sync type: {type(force_full_sync)}")
	print(f"🔍 force_full_sync value: {repr(force_full_sync)}")
	return get_bulk_results_direct(session, access_info, job_id, sobject, schema, table, snowflake_fields, database, force_full_sync)

def delete_query(access_info, job_id):
	"""Deletes a Salesforce query job by ID using the Bulk Query API.

		Args:
			access_info (dict): Dictionary containing Salesforce access details, including
				'access_token' (str) for authentication and 'instance_url' (str) for the API endpoint.
			job_id (str): ID of the query job to delete.

		Returns:
			requests.Response: HTTP response object from the DELETE request, containing status code
				and headers.

		Raises:
			requests.exceptions.RequestException: If the API request fails (e.g., invalid job ID,
				network error, or authentication failure).
			KeyError: If 'access_token' or 'instance_url' is missing from access_info.
		"""
	headers = {
			"Authorization":"Bearer {}".format(access_info['access_token']),
			"Content-Type": "application/json"
	}
	url = access_info['instance_url']+"/services/data/v58.0/jobs/query/{}".format(job_id)
	results = requests.delete(url, headers=headers)

	return results

def get_query_ids(access_info):
	"""Retrieves a list of active Salesforce query job IDs and their details using the Bulk Query API.
	Iterates through paginated results to collect all non-'Classic' query jobs.

	Args:
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) for authentication and 'instance_url' (str) for the API endpoint.

	Returns:
		list: List of dictionaries, each containing job details: 'id' (str), 'jobType' (str),
			'operation' (str), 'object' (str), 'createdDate' (str), and 'state' (str).
			Excludes jobs with jobType 'Classic'.

	Raises:
		requests.exceptions.RequestException: If the API request fails (e.g., invalid token,
			network error).
		json.JSONDecodeError: If the API response is not valid JSON.
		KeyError: If 'access_token', 'instance_url', or expected response fields are missing.
	"""
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

def test_snowflake_permissions(session, schema, table, database=None):
	"""Test Snowflake permissions and context for debugging."""
	# Auto-detect database if not provided
	if database is None:
		database = session.sql('SELECT CURRENT_DATABASE()').collect()[0][0]
	
	# Set the current database and schema context
	session.sql(f"USE DATABASE {database}").collect()
	session.sql(f"USE SCHEMA {schema}").collect()

def cleanup_completed_jobs(access_info, max_age_hours=24):
	"""Deletes completed Salesforce Bulk API 2.0 jobs that are older than the specified age.
	
	Args:
		access_info (dict): Dictionary containing Salesforce access details, including
			'access_token' (str) for authentication and 'instance_url' (str) for the API endpoint.
		max_age_hours (int): Maximum age in hours for jobs to be kept. Jobs older than this will be deleted.
			Default is 24 hours.
	
	Returns:
		dict: Summary of cleanup operation including deleted_count, failed_count, and details.
	
	Raises:
		requests.exceptions.RequestException: If the API request fails.
		json.JSONDecodeError: If the API response is not valid JSON.
	"""
	import datetime
	
	headers = {
		"Authorization": "Bearer {}".format(access_info['access_token']),
		"Content-Type": "application/json"
	}
	
	# Get all query jobs
	url = access_info['instance_url'] + "/services/data/v58.0/jobs/query/"
	completed_jobs = []
	
	try:
		while True:
			results = requests.get(url, headers=headers)
			results.raise_for_status()
			
			for job in results.json()['records']:
				# Only process completed jobs (JobComplete, Failed, Aborted)
				if job['state'] in ['JobComplete', 'Failed', 'Aborted']:
					# Parse the created date
					created_date = datetime.datetime.fromisoformat(job['createdDate'].replace('Z', '+00:00'))
					age_hours = (datetime.datetime.now(datetime.timezone.utc) - created_date).total_seconds() / 3600
					
					# If job is older than max_age_hours, mark for deletion
					if age_hours > max_age_hours:
						completed_jobs.append({
							'id': job['id'],
							'state': job['state'],
							'created_date': job['createdDate'],
							'age_hours': age_hours
						})
			
			# Check for next page
			if results.json().get('nextRecordsUrl'):
				url = access_info['instance_url'] + results.json()['nextRecordsUrl']
			else:
				break
		
		# Delete the old completed jobs
		deleted_count = 0
		failed_count = 0
		failed_jobs = []
		
		for job in completed_jobs:
			try:
				delete_url = access_info['instance_url'] + f"/services/data/v58.0/jobs/query/{job['id']}"
				delete_response = requests.delete(delete_url, headers=headers)
				
				if delete_response.status_code == 204:  # Success
					deleted_count += 1
					print(f"🗑️ Deleted completed job {job['id']} (age: {job['age_hours']:.1f}h, state: {job['state']})")
				else:
					failed_count += 1
					failed_jobs.append({
						'id': job['id'],
						'status_code': delete_response.status_code,
						'error': delete_response.text
					})
					print(f"❌ Failed to delete job {job['id']}: {delete_response.status_code}")
					
			except Exception as e:
				failed_count += 1
				failed_jobs.append({
					'id': job['id'],
					'error': str(e)
				})
				print(f"❌ Error deleting job {job['id']}: {e}")
		
		cleanup_summary = {
			'deleted_count': deleted_count,
			'failed_count': failed_count,
			'total_processed': len(completed_jobs),
			'max_age_hours': max_age_hours,
			'failed_jobs': failed_jobs
		}
		
		print(f"🧹 Cleanup completed: {deleted_count} jobs deleted, {failed_count} failed")
		return cleanup_summary
		
	except Exception as e:
		print(f"❌ Error during job cleanup: {e}")
		return {
			'deleted_count': 0,
			'failed_count': 0,
			'total_processed': 0,
			'error': str(e)
		}

def delete_specific_job(access_info, job_id):
	"""Deletes a specific Salesforce Bulk API 2.0 job by ID.
	
	Args:
		access_info (dict): Dictionary containing Salesforce access details.
		job_id (str): ID of the job to delete.
	
	Returns:
		dict: Result of the deletion operation.
	"""
	headers = {
		"Authorization": "Bearer {}".format(access_info['access_token']),
		"Content-Type": "application/json"
	}
	
	try:
		delete_url = access_info['instance_url'] + f"/services/data/v58.0/jobs/query/{job_id}"
		delete_response = requests.delete(delete_url, headers=headers)
		
		if delete_response.status_code == 204:
			print(f"🗑️ Successfully deleted job {job_id}")
			return {
				'success': True,
				'job_id': job_id,
				'message': 'Job deleted successfully'
			}
		else:
			print(f"❌ Failed to delete job {job_id}: {delete_response.status_code}")
			return {
				'success': False,
				'job_id': job_id,
				'status_code': delete_response.status_code,
				'error': delete_response.text
			}
			
	except Exception as e:
		print(f"❌ Error deleting job {job_id}: {e}")
		return {
			'success': False,
			'job_id': job_id,
			'error': str(e)
		}

