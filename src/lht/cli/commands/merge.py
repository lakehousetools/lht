"""
Merge command implementation.

Merge Salesforce records inside Salesforce, with the (MasterId, LoserId) pairs read from a Snowflake
SQL query.
"""

import sys
import logging
from typing import Optional

from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info
from lht.user.connections import get_primary_connection, load_connection
from lht.cli.commands.retl import _read_sql


def merge(
    sobject: str,
    sql: Optional[str] = None,
    sql_file: Optional[str] = None,
    snowflake_connection: Optional[str] = None,
    salesforce_connection: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Run a merge. Returns 1 if any merge failed, so a calling script stops."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s",
                        stream=sys.stdout, force=True)
    try:
        sql_text = _read_sql(sql, sql_file).strip().rstrip(";")

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
        if load_connection(snowflake_connection) is None:
            print(f"Error: Snowflake connection '{snowflake_connection}' not found")
            return 1

        print(f"✓ Using Snowflake connection: {snowflake_connection}")
        session = create_session(connection_name=snowflake_connection)
        print("✓ Connected to Snowflake")
        print(f"✓ Using Salesforce connection: {salesforce_connection}")
        access_info = get_salesforce_access_info(salesforce_connection)
        print("✓ Authenticated with Salesforce")

        from lht.salesforce import merge as merge_mod

        print("\n" + "=" * 60)
        print("Merge Configuration")
        print("=" * 60)
        print(f"Salesforce Object: {sobject}")
        print(f"Dry run: {'Yes -- nothing is sent to Salesforce' if dry_run else 'No'}")
        print("=" * 60)
        if verbose:
            print("\nSQL Query:\n" + "-" * 40 + f"\n{sql_text}\n" + "-" * 40)

        summary = merge_mod.merge(session, access_info, sobject, sql_text, dry_run=dry_run)
        print(f"\nMerge requests: {summary['requests']:,} ({summary['records_to_merge']:,} record(s) to merge)")
        if dry_run:
            print("✓ Dry run: pairs validated, nothing merged")
            return 0
        print(f"Merged: {summary['merged']:,}")
        print(f"Failed requests: {len(summary['failed']):,}")
        for failure in summary["failed"]:
            print(f"   ✗ master {failure['master_id']} <- {', '.join(failure['loser_ids'])}: {'; '.join(failure['errors'])}")
        if summary["failed"]:
            return 1
        print("✓ Merge completed successfully")
        return 0

    except KeyboardInterrupt:
        print("\n\n✗ Merge cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error during merge: {e}")
        import traceback
        traceback.print_exc()
        return 1
