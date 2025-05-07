import requests

def successful_results(access_info, job_id):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/successfulResults/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    print("@@@ STATUS {}".format(response.json()))
    return response.json()