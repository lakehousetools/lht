
import requests
import json
from lht.util import csv, log_retl
from lht.salesforce import ingest_bapi20 as ingest
import time

def upsert(session, access_info, sobject, query, field):
    """
    Upsert records to Salesforce using data from a SQL query executed against Snowflake.
    
    Args:
        session: Snowflake session object
        access_info: Salesforce access credentials dictionary
        sobject: Salesforce object name (e.g., 'Account', 'Contact')
        query: SQL query string to execute against Snowflake
        field: External ID field name for upsert operation
    """
    print("\n" + "="*100)
    print("🚀 STARTING SALESFORCE UPSERT WITH DEBUG OUTPUT")
    print("="*100)
    print(f"📋 Parameters:")
    print(f"   - SObject: {sobject}")
    print(f"   - External ID Field: {field}")
    print(f"   - SQL Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    print(f"   - Instance URL: {access_info.get('instance_url', 'Not available')}")
    print("="*100)
    
    try:
        access_token = access_info['access_token']

        print("🔍 STEP 1: Executing SQL query against Snowflake...")
        # Execute the SQL query directly instead of reading from a file
        results = session.sql(query).collect()
        
        # Convert results to the expected format
        records = []
        for result in results:
            record = {}
            for key, value in result.asDict().items():
                if value is None:
                    record[key] = ''
                else:
                    record[key] = value
            records.append(record)
        
        print(f"📊 Retrieved {len(records)} records from Snowflake")
        
        print("🔍 STEP 2: Converting records to CSV format...")
        data = csv.json_to_csv(records)
        print(f"📄 CSV data length: {len(data)} characters")
        print(f"📄 CSV preview (first 200 chars): {data[:200]}...")

        bulk_api_url = access_info['instance_url']+ f"/services/data/v62.0/jobs/ingest"
        print(f"🔗 Bulk API URL: {bulk_api_url}")

        # Create a new job
        job_data = {
            "object": f"{sobject}",  # Specify the Salesforce object
            "operation": "upsert",  # Use upsert operation
            "externalIdFieldName": f"{field}",  # Field to use for upsert
            "lineEnding" : "CRLF"
        }

        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

        # Create the job
        print("🔍 STEP 3: Creating Salesforce Bulk API job...")
        print(f"📋 Job data: {job_data}")
        response = requests.post(bulk_api_url, headers=headers, data=json.dumps(job_data))
        
        if response.status_code != 200:
            print(f"❌ Job creation failed with status {response.status_code}")
            print(f"❌ Response: {response.text}")
            response.raise_for_status()
            
        job_info = response.json()
        print(f"✅ Job created successfully: {job_info}")
        #log_retl.job(session, job_info)

        job_id = job_info['id']
        print(f"🆔 Job ID: {job_id}")

        #########################################################
        ###  SEND BATCH FILE
        #########################################################
        print("🔍 STEP 4: Sending CSV data to Salesforce...")
        ingest.send_file(access_info, job_id, data)
        print("✅ File sent successfully")
        
        #########################################################
        ###  CLOSE JOB
        #########################################################
        print("🔍 STEP 5: Closing job to start processing...")
        close_results = ingest.job_close(access_info, job_id)
        print(f"✅ Job closed: {close_results}")

        #########################################################
        ###  CHECK STATUS
        #########################################################
        print("🔍 STEP 6: Monitoring job status...")
        status_check_count = 0
        while True:
            status_check_count += 1
            close_results = ingest.job_status(access_info, job_id)
            print(f"📊 Status check #{status_check_count} - ID: {close_results['id']}, Status: {close_results['state']}")
            
            if close_results['state'] == 'JobComplete':
                print("✅ Job completed successfully!")
                break
            elif close_results['state'] in ['Failed', 'Aborted']:
                print(f"❌ Job failed with status: {close_results['state']}")
                print(f"❌ Full job details: {close_results}")
                break
            
            print("⏳ Waiting 10 seconds before next status check...")
            time.sleep(10)

        print("\n" + "="*100)
        print("✅ UPSERT COMPLETED SUCCESSFULLY")
        print("="*100)
        print(f"📊 Final Result: {job_info}")
        print("="*100)
        
        return job_info
        
    except Exception as e:
        print("\n" + "="*100)
        print("❌ UPSERT FAILED")
        print("="*100)
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Full traceback:")
        print(traceback.format_exc())
        print("="*100)
        raise

def update(session, access_info, sobject, query):
    access_token = access_info['access_token']

    records = q.get_records(session, query)
    data = csv.json_to_csv(records)

    bulk_api_url = access_info['instance_url']+ f"/services/data/v62.0/jobs/ingest"

    # Create a new job
    job_data = {
        "object": f"{sobject}",  # Specify the Salesforce object
        "operation": "update",  # Use upsert operation
        "lineEnding" : "CRLF"
    }

    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

    # Create the job
    print("creating job")
    response = requests.post(bulk_api_url, headers=headers, data=json.dumps(job_data))
    job_info = response.json()
    #log_retl.job(session, job_info)

    job_id = job_info['id']

    #########################################################
    ###  SEND BATCH FILE
    #########################################################
    #def add_batch(instance_url, access_token, job_id, data):
    print("sending file")
    ingest.send_file(access_info, job_id, data)
    
    #########################################################
    ###  CLOSE JOB
    #########################################################
    print("closing job")
    close_results = ingest.job_close(access_info, job_id)
    print(close_results)


    #########################################################
    ###  CHECK STATUS
    #########################################################    
    while True:
        close_results = ingest.job_status(access_info, job_id)
        print("\nID: {}".format(close_results['id']))
        print("\nStatus: {}".format(close_results['state']))
        if close_results['state'] == 'JobComplete':
            break
        time.sleep(10)

    return job_info

def insert(session, access_info, sobject, query):
    access_token = access_info['access_token']

    records = q.get_records(session, query)
    data = csv.json_to_csv(records)

    bulk_api_url = access_info['instance_url']+ f"/services/data/v62.0/jobs/ingest"

    # Create a new job
    job_data = {
        "object": f"{sobject}",  
        "contentType" : "CSV",
        "operation": "insert",  
        "lineEnding" : "CRLF"
    }

    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

    # Create the job
    print("creating job")
    response = requests.post(bulk_api_url, headers=headers, data=json.dumps(job_data))
    job_info = response.json()
    #log_retl.job(session, job_info)

    job_id = job_info['id']

    #########################################################
    ###  SEND BATCH FILE
    #########################################################
    #def add_batch(instance_url, access_token, job_id, data):
    print("sending file")
    ingest.send_file(access_info, job_id, data)
    
    #########################################################
    ###  CLOSE JOB
    #########################################################
    print("closing job")
    close_results = ingest.job_close(access_info, job_id)
    print(close_results)


    #########################################################
    ###  CHECK STATUS
    #########################################################    
    while True:
        close_results = ingest.job_status(access_info, job_id)
        print("\nID: {}".format(close_results['id']))
        print("\nStatus: {}".format(close_results['state']))
        if close_results['state'] == 'JobComplete':
            break
        time.sleep(10)

    return job_info

def delete(session, access_info, sobject, query, field):

    access_token = access_info['access_token']

    records = q.get_records(session, query)
    data = csv.json_to_csv(records)

    bulk_api_url = access_info['instance_url']+ f"/services/data/v62.0/jobs/ingest"

    # Create a new job
    job_data = {
        "object": f"{sobject}",  
        "contentType" : "CSV",
        "operation": "delete", 
        "lineEnding" : "CRLF"
    }

    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

    # Create the job
    print("creating job")
    response = requests.post(bulk_api_url, headers=headers, data=json.dumps(job_data))
    job_info = response.json()
    print("@@@ JOB: {}".format(job_info))
    #log_retl.job(session, job_info)

    job_id = job_info['id']

    #########################################################
    ###  SEND BATCH FILE
    #########################################################
    #def add_batch(instance_url, access_token, job_id, data):
    print("sending file")
    ingest.send_file(access_info, job_id, data)
    
    #########################################################
    ###  CLOSE JOB
    #########################################################
    print("closing job")
    close_results = ingest.job_close(access_info, job_id)
    print(close_results)


    #########################################################
    ###  CHECK STATUS
    #########################################################    
    while True:
        close_results = ingest.job_status(access_info, job_id)
        print("\nID: {}".format(close_results['id']))
        print("\nStatus: {}".format(close_results['state']))
        if close_results['state'] == 'JobComplete':
            break
        time.sleep(10)
    
    return job_info