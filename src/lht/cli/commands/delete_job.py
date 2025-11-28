"""
Delete Bulk API 2.0 job command implementation.
"""

from typing import Optional


def delete_job(job_id: str, salesforce_connection: Optional[str] = None, api_version: str = "v58.0") -> int:
    """
    Delete a specific Bulk API 2.0 job from Salesforce.
    
    Args:
        job_id: The ID of the job to delete
        salesforce_connection: Optional Salesforce connection name (defaults to primary)
        api_version: Salesforce API version (default: "v58.0")
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from lht.user.salesforce_auth import get_salesforce_access_info
        from lht.salesforce.jobs import delete_bulk_api_job
        
        # Get Salesforce access info
        try:
            access_info = get_salesforce_access_info(connection_name=salesforce_connection)
        except ValueError as e:
            print(f"Error: {e}")
            print("\nPlease create a Salesforce connection first using:")
            print("  lht create-connection --salesforce")
            return 1
        
        # Delete job
        print(f"\nDeleting Bulk API 2.0 job: {job_id}")
        print("=" * 80)
        print()
        
        try:
            result = delete_bulk_api_job(access_info, job_id, api_version=api_version)
            
            if result.get('success'):
                print(f"✅ Successfully deleted job: {job_id}")
                print()
                return 0
            else:
                error_msg = result.get('error', 'Unknown error')
                status_code = result.get('status_code', 'N/A')
                print(f"❌ Failed to delete job: {job_id}")
                print(f"   Status Code: {status_code}")
                print(f"   Error: {error_msg}")
                print()
                return 1
            
        except ValueError as e:
            print(f"Error: {e}")
            return 1
        except Exception as e:
            print(f"Error deleting job: {e}")
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

