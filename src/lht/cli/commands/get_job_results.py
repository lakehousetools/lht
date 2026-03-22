"""
Get Bulk API 2.0 ingest job results and save as CSV files.
"""

import os
from typing import Optional


def get_job_results(job_id: str, salesforce_connection: Optional[str] = None, api_version: str = "v58.0") -> int:
    """
    Download successfulResults, failedResults, and unprocessedrecords CSVs
    for a completed Bulk API 2.0 ingest job and save them to
    bulk_api_20_results/<job_id>/ relative to the current working directory.
    """
    try:
        from lht.user.salesforce_auth import get_salesforce_access_info
        from lht.salesforce.jobs import get_ingest_job_results

        try:
            access_info = get_salesforce_access_info(connection_name=salesforce_connection)
        except ValueError as e:
            print(f"Error: {e}")
            print("\nPlease create a Salesforce connection first using:")
            print("  lht create-connection --salesforce")
            return 1

        print(f"\nFetching results for job: {job_id}")

        try:
            results = get_ingest_job_results(access_info, job_id, api_version=api_version)
        except Exception as e:
            print(f"Error fetching job results: {e}")
            return 1

        output_dir = os.path.join(os.getcwd(), "bulk_api_20_results", job_id)
        os.makedirs(output_dir, exist_ok=True)

        file_map = {
            'successful_results': f'{job_id}_successful_results.csv',
            'failed_results': f'{job_id}_failed_results.csv',
            'unprocessed_records': f'{job_id}_unprocessed_records.csv',
        }

        print(f"Saving results to: {output_dir}\n")

        for key, filename in file_map.items():
            content = results.get(key, '')
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            row_count = max(0, content.count('\n') - 1) if content.strip() else 0
            print(f"  {filename}: {row_count} record(s)")

        print()
        return 0

    except ImportError as e:
        print(f"Error: Required module not available: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
