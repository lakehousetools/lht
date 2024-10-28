import json
import requests
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col
from . import csv


def job(session, json_data):   
    if 'externalIdFieldName' in json_data:
        externalid = json_data['externalIdFieldName']
    else:
        externalid = None
    query = """INSERT INTO LOGS.RETL_HISTORY (id, operation, object, createdById, createdDate, externalIdFieldName,contentUrl) values(\'{}\',\'{}\',\'{}\',\'{}\',\'{}\',\'{}\',\'{}\')""".format(json_data['id'], json_data['operation'], json_data['object'], json_data['createdById'], json_data['createdDate'][:10]+' '+json_data['createdDate'][11:23], externalid,json_data['contentUrl'])
    session.sql(query).collect()
    return None

def successful_results(access_info, job_id):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/successfulResults/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    response = requests.get(url, headers=headers)
    results = csv.success_upserts(response.text, job_id)
    #response.raise_for_status()

    return results

def failed_results(access_info, job_id):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/failedResults/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    print("@@@ STATUS {}".format(response.text))
    return response.text

def log_results(session, access_info, job_id, schema, table):   
    if check_log(session, job_id) > 0:
        return "see existing logs"
    else:
        successes = successful_results(access_info, job_id)
        print(successes)
        
        session.write_pandas(successes, 'RADNET_SANDBOX.LOGS.RETL_RESULTS', quote_identifiers=False, auto_create_table=False, overwrite=False,use_logical_type=True)
        #def success_upserts(data):
        #
        failures = failed_results(access_info, job_id)
        
        #print(successes)
        print("\n---------------------------\n")
        print(failures)
    return None


def check_log(session, id):
    query = history_query(id)
    results = session.sql(query).collect() 
    
    return len(results)

def history_query(id):
    query = """with history as (
                select 
                ID, 
                OPERATION, 
                OBJECT, 
                EXTERNALIDFIELDNAME
                from RADNET_SANDBOX.LOGS.RETL_HISTORY
                ),
                results as (
                Select 
                HISTORY_ID
                from RADNET_SANDBOX.LOGS.RETL_RESULTS
                )
                select
                h.id,
                r.history_id
                from history h
                join results r
                on r.history_id = h.id
                where h.id = \'{}\'""".format(id)

    return query