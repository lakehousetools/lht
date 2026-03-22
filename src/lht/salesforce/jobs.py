"""
Bulk API 2.0 jobs operations from Salesforce.
"""

import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _fetch_jobs_from_endpoint(headers: Dict[str, str], url: str, instance_url: str) -> List[Dict[str, Any]]:
    """Fetch all jobs from a paginated Bulk API 2.0 endpoint."""
    jobs = []
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()
        jobs.extend(result.get('records', []))
        next_url = result.get('nextRecordsUrl')
        if next_url and not next_url.startswith('http'):
            next_url = f"{instance_url}{next_url}"
        url = next_url
    return jobs


def list_bulk_api_jobs(access_info: Dict[str, str], api_version: str = "v58.0") -> List[Dict[str, Any]]:
    """
    List all Bulk API 2.0 jobs from Salesforce (both query and ingest jobs).

    Args:
        access_info: Dictionary containing Salesforce access details, including
            'access_token' (str) and 'instance_url' (str).
        api_version: Salesforce API version (default: "v58.0")

    Returns:
        List of dictionaries containing job information with fields:
        - id
        - operation
        - object
        - createdById
        - createdDate
        - state
        - concurrencyMode
        - contentType
        - apiVersion
        - jobType

    Raises:
        requests.exceptions.RequestException: If the API request fails
        ValueError: If access_info is missing required fields
    """
    if 'access_token' not in access_info or 'instance_url' not in access_info:
        raise ValueError("access_info must contain 'access_token' and 'instance_url'")

    headers = {
        "Authorization": f"Bearer {access_info['access_token']}",
        "Content-Type": "application/json"
    }

    base_url = f"{access_info['instance_url']}/services/data/{api_version}"

    try:
        query_jobs = _fetch_jobs_from_endpoint(headers, f"{base_url}/jobs/query", access_info['instance_url'])
        logger.debug(f"Retrieved {len(query_jobs)} query jobs")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing query jobs: {e}")
        raise

    try:
        ingest_jobs = _fetch_jobs_from_endpoint(headers, f"{base_url}/jobs/ingest", access_info['instance_url'])
        logger.debug(f"Retrieved {len(ingest_jobs)} ingest jobs")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing ingest jobs: {e}")
        raise

    jobs = query_jobs + ingest_jobs
    logger.debug(f"Retrieved {len(jobs)} total Bulk API 2.0 jobs")
    return jobs


def get_bulk_api_job(access_info: Dict[str, str], job_id: str, api_version: str = "v58.0") -> Dict[str, Any]:
    """
    Get details about a specific Bulk API 2.0 query job from Salesforce.
    
    Args:
        access_info: Dictionary containing Salesforce access details, including
            'access_token' (str) and 'instance_url' (str).
        job_id: The ID of the job to retrieve
        api_version: Salesforce API version (default: "v58.0")
    
    Returns:
        Dictionary containing job information with fields:
        - id
        - operation
        - object
        - createdById
        - createdDate
        - state
        - apiVersion
        - jobType
        - numberRecordsProcessed
        - retries
        - totalProcessingTime
        - isPkChunkingSupported
    
    Raises:
        requests.exceptions.RequestException: If the API request fails
        ValueError: If access_info is missing required fields
        requests.exceptions.HTTPError: If the job is not found (404) or other HTTP error
    """
    if 'access_token' not in access_info or 'instance_url' not in access_info:
        raise ValueError("access_info must contain 'access_token' and 'instance_url'")
    
    if not job_id:
        raise ValueError("job_id is required")
    
    headers = {
        "Authorization": f"Bearer {access_info['access_token']}",
        "Content-Type": "application/json"
    }
    
    base_url = f"{access_info['instance_url']}/services/data/{api_version}"

    for job_type in ('query', 'ingest'):
        url = f"{base_url}/jobs/{job_type}/{job_id}"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            job = response.json()
            logger.debug(f"Retrieved Bulk API 2.0 job: {job_id}")
            return job
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error getting job from {job_type} endpoint: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting job: {e}")
            raise

    raise ValueError(f"Job not found: {job_id}")


def delete_bulk_api_job(access_info: Dict[str, str], job_id: str, api_version: str = "v58.0") -> Dict[str, Any]:
    """
    Delete a specific Bulk API 2.0 query job from Salesforce.
    
    Args:
        access_info: Dictionary containing Salesforce access details, including
            'access_token' (str) and 'instance_url' (str).
        job_id: The ID of the job to delete
        api_version: Salesforce API version (default: "v58.0")
    
    Returns:
        Dictionary containing deletion result with fields:
        - success: Boolean indicating if deletion was successful
        - job_id: The ID of the job that was deleted
        - message: Success message (if successful)
        - status_code: HTTP status code (if failed)
        - error: Error message (if failed)
    
    Raises:
        requests.exceptions.RequestException: If the API request fails
        ValueError: If access_info is missing required fields or job_id is empty
    """
    if 'access_token' not in access_info or 'instance_url' not in access_info:
        raise ValueError("access_info must contain 'access_token' and 'instance_url'")
    
    if not job_id:
        raise ValueError("job_id is required")
    
    headers = {
        "Authorization": f"Bearer {access_info['access_token']}",
        "Content-Type": "application/json"
    }
    
    base_url = f"{access_info['instance_url']}/services/data/{api_version}"

    # Determine correct endpoint (query vs ingest) by probing
    url = None
    for job_type in ('query', 'ingest'):
        probe = requests.get(f"{base_url}/jobs/{job_type}/{job_id}", headers=headers)
        if probe.status_code != 404:
            url = f"{base_url}/jobs/{job_type}/{job_id}"
            break

    if url is None:
        return {'success': False, 'job_id': job_id, 'error': f'Job not found: {job_id}'}

    try:
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 204:
            logger.info(f"Successfully deleted Bulk API 2.0 job: {job_id}")
            return {
                'success': True,
                'job_id': job_id,
                'message': 'Job deleted successfully'
            }
        else:
            logger.error(f"Failed to delete job {job_id}: HTTP {response.status_code}")
            return {
                'success': False,
                'job_id': job_id,
                'status_code': response.status_code,
                'error': response.text if response.text else f'HTTP {response.status_code}'
            }
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error deleting job: {e}")
        if e.response is not None:
            logger.error(f"Response: {e.response.text}")
        return {
            'success': False,
            'job_id': job_id,
            'error': str(e)
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error deleting job: {e}")
        return {
            'success': False,
            'job_id': job_id,
            'error': str(e)
        }


def get_ingest_job_results(access_info: Dict[str, str], job_id: str, api_version: str = "v58.0") -> Dict[str, str]:
    """
    Fetch the three result CSVs for a completed Bulk API 2.0 ingest job.

    Returns a dict with keys 'successful_results', 'failed_results', 'unprocessed_records',
    each containing the raw CSV string (empty string if none).
    """
    if 'access_token' not in access_info or 'instance_url' not in access_info:
        raise ValueError("access_info must contain 'access_token' and 'instance_url'")

    base = f"{access_info['instance_url']}/services/data/{api_version}/jobs/ingest/{job_id}"
    headers = {
        "Authorization": f"Bearer {access_info['access_token']}",
        "Accept": "text/csv"
    }

    results = {}
    endpoints = {
        'successful_results': f"{base}/successfulResults",
        'failed_results': f"{base}/failedResults",
        'unprocessed_records': f"{base}/unprocessedrecords",
    }

    for key, url in endpoints.items():
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            results[key] = response.text
            logger.debug(f"Fetched {key} for job {job_id}: {len(response.text)} bytes")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (400, 404):
                results[key] = ''
            else:
                raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {key} for job {job_id}: {e}")
            raise

    return results
