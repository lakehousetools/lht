"""
Bulk API 2.0 jobs operations from Salesforce.
"""

import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def list_bulk_api_jobs(access_info: Dict[str, str], api_version: str = "v58.0") -> List[Dict[str, Any]]:
    """
    List all Bulk API 2.0 query jobs from Salesforce.
    
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
    
    url = f"{access_info['instance_url']}/services/data/{api_version}/jobs/query"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        # The API returns a JSON object with a 'records' array
        jobs = result.get('records', [])
        
        logger.debug(f"Retrieved {len(jobs)} Bulk API 2.0 jobs")
        
        return jobs
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error listing jobs: {e}")
        if e.response is not None:
            logger.error(f"Response: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error listing jobs: {e}")
        raise


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
    
    url = f"{access_info['instance_url']}/services/data/{api_version}/jobs/query/{job_id}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        job = response.json()
        
        logger.debug(f"Retrieved Bulk API 2.0 job: {job_id}")
        
        return job
        
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.error(f"Job not found: {job_id}")
            raise ValueError(f"Job not found: {job_id}")
        logger.error(f"HTTP error getting job: {e}")
        if e.response is not None:
            logger.error(f"Response: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error getting job: {e}")
        raise

