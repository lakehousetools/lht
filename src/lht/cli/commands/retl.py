"""
Reverse ETL (RETL) command implementation.

Push data from Snowflake into Salesforce using Bulk API 2.0 Ingest.
"""

import sys
import logging
from typing import Optional

from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info
from lht.user.connections import get_primary_connection, load_connection


def _read_sql(sql: Optional[str], sql_file: Optional[str]) -> str:
    """
    Read SQL either from --sql or --sql-file.
    """
    if sql and sql_file:
        raise ValueError("Use only one of --sql or --sql-file")
    if sql_file:
        with open(sql_file, "r", encoding="utf-8") as f:
            return f.read()
    if sql:
        return sql
    raise ValueError("One of --sql or --sql-file is required")


def retl(
    operation: str,
    sobject: str,
    sql: Optional[str] = None,
    sql_file: Optional[str] = None,
    match_field: Optional[str] = None,
    batch_size: int = 25000,
    snowflake_connection: Optional[str] = None,
    salesforce_connection: Optional[str] = None,
    log_results: bool = False,
    verbose: bool = False,
) -> int:
    """
    Run a Reverse ETL operation using a Snowflake SQL query as the source.

    Notes:
      - Salesforce API version remains hardcoded inside the existing RETL implementation.
    """
    # Set logging level based on verbose flag
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    try:
        op = operation.lower().strip()
        sql_text = _read_sql(sql, sql_file).strip()
        # Normalize so LIMIT/OFFSET concatenation in retl.upsert stays valid
        sql_text = sql_text.rstrip(";")

        # Resolve connections (use primary if not provided)
        if snowflake_connection is None:
            snowflake_connection = get_primary_connection("snowflake")
        if salesforce_connection is None:
            salesforce_connection = get_primary_connection("salesforce")

        if not snowflake_connection:
            print("Error: No Snowflake connection found. Use --snowflake or set a primary connection.")
            return 1
        if not salesforce_connection:
            print("Error: No Salesforce connection found. Use --salesforce or set a primary connection.")
            return 1

        # Validate Snowflake connection exists
        snowflake_creds = load_connection(snowflake_connection)
        if snowflake_creds is None:
            print(f"Error: Snowflake connection '{snowflake_connection}' not found")
            return 1

        print(f"✓ Using Snowflake connection: {snowflake_connection}")
        print("✓ Connecting to Snowflake...")
        session = create_session(connection_name=snowflake_connection)
        print("✓ Connected to Snowflake")

        print(f"✓ Using Salesforce connection: {salesforce_connection}")
        print("✓ Authenticating with Salesforce...")
        access_info = get_salesforce_access_info(salesforce_connection)
        print("✓ Authenticated with Salesforce")

        from lht.salesforce import retl as retl_mod

        print("\n" + "=" * 60)
        print("RETL Configuration")
        print("=" * 60)
        print(f"Operation: {op}")
        print(f"Salesforce Object: {sobject}")
        if op == "upsert":
            print(f"Match Field: {match_field}")
            print(f"Batch Size: {batch_size:,}")
        print(f"Log Results: {'Yes' if log_results else 'No'}")
        print("=" * 60)
        if verbose:
            print("\nSQL Query:")
            print("-" * 40)
            print(sql_text)
            print("-" * 40)
        print()

        # Collect job IDs for logging
        job_ids = []

        if op == "upsert":
            if not match_field:
                print("Error: --match-field is required for upsert")
                return 1
            result = retl_mod.upsert(
                session=session,
                access_info=access_info,
                sobject=sobject,
                query=sql_text,
                field=match_field,
                batch_size=batch_size,
            )
            # Extract job IDs from batch results
            if result and 'batch_results' in result:
                for batch in result['batch_results']:
                    if batch.get('job_id'):
                        job_ids.append(batch['job_id'])
        elif op == "insert":
            result = retl_mod.insert(session, access_info, sobject, sql_text)
            if result and 'id' in result:
                job_ids.append(result['id'])
        elif op == "update":
            result = retl_mod.update(session, access_info, sobject, sql_text)
            if result and 'id' in result:
                job_ids.append(result['id'])
        elif op == "delete":
            # retl.delete signature includes `field` but it's unused; pass None for compatibility
            result = retl_mod.delete(session, access_info, sobject, sql_text, field=None)
            if result and 'id' in result:
                job_ids.append(result['id'])
        else:
            print("Error: operation must be one of: upsert, insert, update, delete")
            return 1

        if log_results and job_ids:
            from lht.salesforce.results_bapi import process_bulk_api_results
            print("\n" + "=" * 60)
            print("Logging Results to Snowflake")
            print("=" * 60)
            for job_id in job_ids:
                print(f"📋 Processing results for job: {job_id}")
                try:
                    log_result = process_bulk_api_results(session, access_info, job_id)
                    if log_result.get('success'):
                        print(f"   ✅ Logged: {log_result.get('success_count', 0)} success, {log_result.get('failure_count', 0)} failures")
                    else:
                        print(f"   ⚠️ Logging failed: {log_result.get('error', 'Unknown error')}")
                except Exception as log_error:
                    print(f"   ⚠️ Error logging results: {log_error}")
            print("=" * 60)
        elif log_results and not job_ids:
            print("⚠️ No job IDs to log (operation may have had no records to process)")

        print("✓ RETL completed successfully")
        return 0

    except KeyboardInterrupt:
        print("\n\n✗ RETL cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error during RETL: {e}")
        import traceback
        traceback.print_exc()
        return 1

