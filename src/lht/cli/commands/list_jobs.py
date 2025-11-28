"""
List Bulk API 2.0 jobs command implementation.
"""

from typing import Optional
from tabulate import tabulate


def list_jobs(salesforce_connection: Optional[str] = None, api_version: str = "v58.0") -> int:
    """
    List all Bulk API 2.0 jobs from Salesforce.
    
    Args:
        salesforce_connection: Optional Salesforce connection name (defaults to primary)
        api_version: Salesforce API version (default: "v58.0")
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from lht.user.salesforce_auth import get_salesforce_access_info
        from lht.salesforce.list_jobs import list_bulk_api_jobs
        
        # Get Salesforce access info
        try:
            access_info = get_salesforce_access_info(connection_name=salesforce_connection)
        except ValueError as e:
            print(f"Error: {e}")
            print("\nPlease create a Salesforce connection first using:")
            print("  lht create-connection --salesforce")
            return 1
        
        # List jobs
        print("\n" + "=" * 80)
        print("Bulk API 2.0 Jobs")
        print("=" * 80)
        print()
        
        try:
            jobs = list_bulk_api_jobs(access_info, api_version=api_version)
            
            if not jobs:
                print("No Bulk API 2.0 jobs found.")
                print()
                return 0
            
            # Prepare data for table display
            table_data = []
            for job in jobs:
                table_data.append([
                    job.get('id', 'N/A'),
                    job.get('operation', 'N/A'),
                    job.get('object', 'N/A'),
                    job.get('createdById', 'N/A'),
                    job.get('createdDate', 'N/A'),
                    job.get('state', 'N/A'),
                    job.get('concurrencyMode', 'N/A'),
                    job.get('contentType', 'N/A'),
                    job.get('apiVersion', 'N/A'),
                    job.get('jobType', 'N/A')
                ])
            
            # Display as table
            headers = [
                'ID',
                'Operation',
                'Object',
                'Created By ID',
                'Created Date',
                'State',
                'Concurrency Mode',
                'Content Type',
                'API Version',
                'Job Type'
            ]
            
            print(tabulate(table_data, headers=headers, tablefmt='grid'))
            print()
            print(f"Total: {len(jobs)} job(s)")
            print()
            
            return 0
            
        except Exception as e:
            print(f"Error listing jobs: {e}")
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

