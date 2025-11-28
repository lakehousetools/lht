"""
Show Bulk API 2.0 job details command implementation.
"""

from typing import Optional


def show_job(job_id: str, salesforce_connection: Optional[str] = None, api_version: str = "v58.0") -> int:
    """
    Show details about a specific Bulk API 2.0 job from Salesforce.
    
    Args:
        job_id: The ID of the job to retrieve
        salesforce_connection: Optional Salesforce connection name (defaults to primary)
        api_version: Salesforce API version (default: "v58.0")
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from lht.user.salesforce_auth import get_salesforce_access_info
        from lht.salesforce.jobs import get_bulk_api_job
        
        # Get Salesforce access info
        try:
            access_info = get_salesforce_access_info(connection_name=salesforce_connection)
        except ValueError as e:
            print(f"Error: {e}")
            print("\nPlease create a Salesforce connection first using:")
            print("  lht create-connection --salesforce")
            return 1
        
        # Get job details
        print("\n" + "=" * 80)
        print(f"Bulk API 2.0 Job Details: {job_id}")
        print("=" * 80)
        print()
        
        try:
            job = get_bulk_api_job(access_info, job_id, api_version=api_version)
            
            # Display job information
            print(f"ID:                          {job.get('id', 'N/A')}")
            print(f"Operation:                   {job.get('operation', 'N/A')}")
            print(f"Object:                      {job.get('object', 'N/A')}")
            print(f"Created By ID:               {job.get('createdById', 'N/A')}")
            print(f"Created Date:                {job.get('createdDate', 'N/A')}")
            print(f"State:                       {job.get('state', 'N/A')}")
            print(f"API Version:                 {job.get('apiVersion', 'N/A')}")
            print(f"Job Type:                    {job.get('jobType', 'N/A')}")
            print(f"Number Records Processed:    {job.get('numberRecordsProcessed', 'N/A')}")
            print(f"Retries:                     {job.get('retries', 'N/A')}")
            print(f"Total Processing Time:       {job.get('totalProcessingTime', 'N/A')}")
            print(f"Is PK Chunking Supported:    {job.get('isPkChunkingSupported', 'N/A')}")
            print()
            
            return 0
            
        except ValueError as e:
            print(f"Error: {e}")
            return 1
        except Exception as e:
            print(f"Error getting job details: {e}")
            import traceback
            traceback.print_exc()
            return 1
            
    except ImportError as e:
        print(f"Error: Required module not available: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

