from sflake import query as q
import requests
import json
from util import csv, log_retl
from salesforce import ingest_bapi20 as ingest
import time

def upsert(session, access_info, sobject, query, field):
    access_token = access_info['access_token']

    records = q.get_records(session, query)
    data = csv.json_to_csv(records)

    bulk_api_url = access_info['instance_url']+ f"/services/data/v62.0/jobs/ingest"

    # Create a new job
    job_data = {
        "object": f"{sobject}",  # Specify the Salesforce object
        "operation": "upsert",  # Use upsert operation
        "externalIdFieldName": f"{field}",  # Field to use for upsert
        "lineEnding" : "CRLF"
    }

    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

    # Create the job
    print("creating job")
    response = requests.post(bulk_api_url, headers=headers, data=json.dumps(job_data))
    job_info = response.json()
    log_retl.job(session, job_info)

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
    log_retl.job(session, job_info)

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
    log_retl.job(session, job_info)

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
    log_retl.job(session, job_info)

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