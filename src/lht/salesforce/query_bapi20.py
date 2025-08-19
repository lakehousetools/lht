import requests
import json
import pandas as pd
import numpy as np
import io
from . import sobjects
from lht.util import field_types
from lht.util import stage
import os

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

def get_bulk_results_direct(session, access_info, job_id, sobject, schema, table, database=None):
	# Auto-detect database if not provided
	if database is None:
		database = session.sql('SELECT CURRENT_DATABASE()').collect()[0][0]
		print(f"🔍 DEBUG: Auto-detected database: {database}")
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
	
	# Get field descriptions for formatting
	query_string, df_fields = sobjects.describe(access_info, sobject)
	
	# Process first batch
	csv_content = results.text
	print(f"\n\nPROCESSING BATCH 1")
	
	# Load and process data directly (no stage upload needed)
	df = pd.read_csv(io.StringIO(csv_content))
	formatted_df = field_types.format_sync_file(df, df_fields)
	formatted_df = formatted_df.replace(np.nan, None)
	
	# Set the current database and schema context
	session.sql(f"USE DATABASE {database}").collect()
	session.sql(f"USE SCHEMA {schema}").collect()
	
	# Use fully qualified table name for write_pandas
	fully_qualified_table = f"{schema}.{table}"
	
	# CRITICAL FIX: Create table with correct schema BEFORE write_pandas
	try:
		print(f"🔍 DEBUG: About to create table {schema}.{table}")
		print(f"🔍 DEBUG: df_fields contains {len(df_fields)} fields: {list(df_fields.keys())}")
		
		# Check if table already exists first
		print(f"🔍 DEBUG: Checking if table already exists...")
		try:
			table_check = session.sql(f'SHOW TABLES IN SCHEMA "{schema}"').collect()
			table_names = [row['name'] for row in table_check]
			print(f"🔍 DEBUG: Tables in schema {schema}: {table_names}")
			print(f"🔍 DEBUG: Looking for table: {table}")
			
			if table in table_names:
				print(f"🔍 DEBUG: Table {schema}.{table} already exists, skipping creation")
			else:
				print(f"🔍 DEBUG: Table {schema}.{table} does not exist, creating it...")
				create_table_sql = _build_create_table_sql(schema, table, df_fields)
				print(f"🔍 DEBUG: CREATE TABLE SQL: {create_table_sql}")
				
				# Execute CREATE TABLE statement
				print(f"🔍 DEBUG: Executing CREATE TABLE statement...")
				result = session.sql(create_table_sql).collect()
				print(f"✅ Table created with correct schema")
				
				# Verify table was created
				print(f"🔍 DEBUG: Verifying table creation...")
				table_check_after = session.sql(f'SHOW TABLES IN SCHEMA "{schema}"').collect()
				table_names_after = [row['name'] for row in table_check_after]
				print(f"🔍 DEBUG: Tables after creation: {table_names_after}")
				
				if table not in table_names_after:
					raise Exception(f"Table {schema}.{table} was not created successfully")
				else:
					print(f"🔍 DEBUG: Table {schema}.{table} verified successfully")
		
		except Exception as table_check_error:
			print(f"🔍 DEBUG: Error checking/creating table: {table_check_error}")
			print(f"🔍 DEBUG: Falling back to auto_create_table=True")
			# Fallback: let Snowflake create the table automatically
			session.write_pandas(formatted_df, fully_qualified_table, quote_identifiers=False, auto_create_table=True, overwrite=False, use_logical_type=False, on_error="CONTINUE")
			print(f"✅ Data loaded with auto-created table")
			return results
		
		# Now load data into existing table (no auto-create, no overwrite)
		print(f"🔍 DEBUG: Loading data into table {fully_qualified_table}")
		session.write_pandas(formatted_df, fully_qualified_table, quote_identifiers=False, auto_create_table=False, overwrite=False, use_logical_type=False, on_error="CONTINUE")
		print(f"✅ Data loaded successfully")
		
	except Exception as e:
		print(f"❌ Failed to create table or load data: {e}")
		print(f"🔍 DEBUG: Final fallback - trying auto_create_table=True")
		try:
			# Ultimate fallback: let Snowflake handle everything
			session.write_pandas(formatted_df, fully_qualified_table, quote_identifiers=False, auto_create_table=True, overwrite=False, use_logical_type=False, on_error="CONTINUE")
			print(f"✅ Data loaded with ultimate fallback")
		except Exception as final_error:
			print(f"❌ Ultimate fallback also failed: {final_error}")
			raise final_error
	
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
		
		df = pd.read_csv(io.StringIO(csv_content))
		formatted_df = field_types.format_sync_file(df, df_fields)
		formatted_df = formatted_df.replace(np.nan, None)
	
		# Set the current database and schema context
		session.sql(f"USE DATABASE {database}").collect()
		session.sql(f"USE SCHEMA {schema}").collect()
		
		# Use fully qualified table name for write_pandas
		fully_qualified_table = f"{schema}.{table}"
		
		try:
			session.write_pandas(formatted_df, fully_qualified_table, quote_identifiers=False, auto_create_table=False, overwrite=False, use_logical_type=True, on_error="CONTINUE")
			print(f"✅ Batch {counter} loaded successfully")
		except Exception as e:
			print(f"❌ Batch {counter} failed: {e}")
			raise
		
		counter += 1
	
	return results

def get_bulk_results(session, access_info, job_id, sobject, schema, table, use_stage=False, stage_name=None, database=None):
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
	return get_bulk_results_direct(session, access_info, job_id, sobject, schema, table, database)

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
		print(f"🔍 DEBUG: Auto-detected database: {database}")
	
	print(f"\n🔍 DEBUG: Testing Snowflake permissions and context")
	print(f"🔍 DEBUG: Target schema: {schema}")
	print(f"🔍 DEBUG: Target table: {table}")
	print(f"🔍 DEBUG: Target database: {database}")
	
	# Check current context
	current_db = session.sql('SELECT CURRENT_DATABASE()').collect()[0][0]
	current_schema = session.sql('SELECT CURRENT_SCHEMA()').collect()[0][0]
	current_role = session.sql('SELECT CURRENT_ROLE()').collect()[0][0]
	
	print(f"🔍 DEBUG: Current database: {current_db}")
	print(f"🔍 DEBUG: Current schema: {current_schema}")
	print(f"🔍 DEBUG: Current role: {current_role}")
	
	# Test database permissions
	try:
		print(f"🔍 DEBUG: Testing database access: {database}")
		session.sql(f"SHOW SCHEMAS IN DATABASE {database}").collect()
		print(f"✅ DEBUG: Database access successful")
	except Exception as e:
		print(f"❌ DEBUG: Database access failed: {e}")
	
	# Test schema permissions
	try:
		print(f"🔍 DEBUG: Testing schema access: {database}.{schema}")
		session.sql(f"SHOW TABLES IN SCHEMA {database}.{schema}").collect()
		print(f"✅ DEBUG: Schema access successful")
	except Exception as e:
		print(f"❌ DEBUG: Schema access failed: {e}")
	
	# Test table creation permissions
	try:
		print(f"🔍 DEBUG: Testing table creation in schema: {database}.{schema}")
		test_table = f"{database}.{schema}.TEST_PERMISSIONS_TEMP"
		session.sql(f"CREATE OR REPLACE TEMPORARY TABLE {test_table} (test_col STRING)").collect()
		session.sql(f"DROP TABLE {test_table}").collect()
		print(f"✅ DEBUG: Table creation test successful")
	except Exception as e:
		print(f"❌ DEBUG: Table creation test failed: {e}")
	
	print(f"🔍 DEBUG: Permission test completed\n")

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

def _build_create_table_sql(schema: str, table: str, df_fields: dict) -> str:
	"""
	Build CREATE TABLE SQL statement based on Salesforce field definitions.
	
	Args:
		schema: Snowflake schema name
		table: Snowflake table name
		df_fields: Dictionary mapping field names to pandas dtypes
		
	Returns:
		str: CREATE TABLE SQL statement
	"""
	# Map pandas dtypes to Snowflake types
	type_mapping = {
		'object': 'VARCHAR(16777216)',      # String fields (including PO_Number__c)
		'int64': 'NUMBER(38,0)',            # Integer fields
		'float64': 'DOUBLE',                 # Float fields
		'bool': 'BOOLEAN',                   # Boolean fields
		'datetime64': 'TIMESTAMP_NTZ',       # Datetime fields
		'datetime64[ns]': 'TIMESTAMP_NTZ',   # Datetime fields with nanoseconds
	}
	
	# Build column definitions
	columns = []
	for field_name, dtype in df_fields.items():
		# Convert field name to uppercase to match DataFrame
		field_upper = field_name.upper()
		
		# Map the dtype to Snowflake type
		snowflake_type = type_mapping.get(dtype, 'VARCHAR(16777216)')  # Default to VARCHAR
		
		# Add column definition
		columns.append(f'"{field_upper}" {snowflake_type}')
	
	# Build CREATE TABLE statement
	column_defs = ',\n\t'.join(columns)
	create_sql = f"""CREATE OR REPLACE TABLE "{schema}"."{table}" (
	{column_defs}
)"""
	
	return create_sql