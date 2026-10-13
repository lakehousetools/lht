"""
Merge command implementation.

Merge Salesforce records inside Salesforce, with the (MasterId, LoserId) pairs read from a warehouse
SQL query.
"""

import sys
import logging
from typing import Optional

from lht.cli.commands.warehouse import (
    WarehouseError,
    open_warehouse,
    resolve_salesforce_connection,
)
from lht.user.salesforce_auth import get_salesforce_access_info
from lht.cli.commands.retl import _read_sql


def merge(
    sobject: str,
    sql: Optional[str] = None,
    sql_file: Optional[str] = None,
    snowflake_connection: Optional[str] = None,
    salesforce_connection: Optional[str] = None,
    databricks: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """
    Run a merge. Returns 1 if any merge failed, so a calling script stops.

    Args:
        databricks: Read the pairs from Databricks instead of Snowflake. The
            value is a `~/.databrickscfg` profile name; an empty string means
            "let Databricks Connect resolve it". None means use Snowflake.
    """
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s",
                        stream=sys.stdout, force=True)
    try:
        sql_text = _read_sql(sql, sql_file).strip().rstrip(";")

        try:
            salesforce_connection = resolve_salesforce_connection(salesforce_connection)
            session, warehouse_label = open_warehouse(
                snowflake_connection=snowflake_connection,
                databricks_profile=databricks,
                use_databricks=databricks is not None,
            )
        except WarehouseError as e:
            print(f"Error: {e}")
            return 1
        print(f"✓ Connected to {warehouse_label}")
        print(f"✓ Using Salesforce connection: {salesforce_connection}")
        access_info = get_salesforce_access_info(salesforce_connection)
        print("✓ Authenticated with Salesforce")

        from lht.salesforce import merge as merge_mod

        print("\n" + "=" * 60)
        print("Merge Configuration")
        print("=" * 60)
        print(f"Warehouse: {warehouse_label}")
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
