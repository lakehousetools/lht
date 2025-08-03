import requests
import json

def job_close(access_info, job_id):
    access_token = access_info['access_token']
    print("closing job")
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    close = {"state":"UploadComplete"}
    response = requests.patch(url, headers=headers, data=json.dumps(close))
    #response.raise_for_status()
    print(response.status_code)

def job_status(access_info, job_id):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}"
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    print("@@@ STATUS {}".format(response.json()))
    return response.json()

def send_file(access_info, job_id, data):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/batches/"
    print(url)
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'text/csv'
    }
    response = requests.put(url, headers=headers, data=data)
    print(response.status_code)

