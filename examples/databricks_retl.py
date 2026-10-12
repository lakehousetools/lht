"""
Reverse ETL from Unity Catalog into Salesforce, on Databricks.

Written to run in three places without edits:

  * a Databricks notebook -- paste the cells below, or attach this file
  * a Databricks Job (notebook or Python task)
  * a laptop, via Databricks Connect against a ~/.databrickscfg profile

What makes that work is that `connect()` and `salesforce_access_info()` each
resolve differently on and off Databricks: on a cluster they use the session and
the secret scope that already exist there, and elsewhere they use a Databricks
Connect profile and a saved lht connection.

On Databricks:

    %pip install lht
    dbutils.library.restartPython()

Locally:

    pip install "lht[databricks]"
    databricks auth login --host https://my-workspace.cloud.databricks.com
    lht create-connection --salesforce
    DATABRICKS_PROFILE=my-workspace python examples/databricks_retl.py
"""

import logging
import os

from lht.salesforce import retl
from lht.salesforce.results_bapi import process_bulk_api_results
from lht.warehouse.databricks import connect, salesforce_access_info

logging.basicConfig(level=logging.INFO, format="%(message)s")

# Replace with your own catalog, schema and Salesforce field API names.
SOURCE_QUERY = """
    SELECT external_id    AS Ext__c,
           rating         AS Rating,
           annual_revenue AS AnnualRevenue
    FROM main.analytics.account_scores
    WHERE scored_at >= current_date() - INTERVAL 1 DAY
"""
SOBJECT = "Account"
MATCH_FIELD = "Ext__c"

# Databricks secret scope holding client_id / client_secret / my_domain.
SECRET_SCOPE = "salesforce"
# Only used off Databricks, where there is no scope to read. None = primary.
LOCAL_CONNECTION = os.environ.get("LHT_SALESFORCE_CONNECTION")
# Only used off Databricks: the ~/.databrickscfg profile to connect with.
PROFILE = os.environ.get("DATABRICKS_PROFILE")


def main() -> int:
    warehouse = connect(profile=PROFILE)
    access_info = salesforce_access_info(
        scope=SECRET_SCOPE, connection_name=LOCAL_CONNECTION
    )

    result = retl.upsert(
        warehouse,
        access_info,
        sobject=SOBJECT,
        query=SOURCE_QUERY,
        field=MATCH_FIELD,
        # A NULL is an empty cell, which Salesforce reads as "leave unchanged".
        # clear_nulls=True sends '#N/A' instead, which clears the field.
        clear_nulls=False,
    )

    if result is None:
        print("Nothing to push: the query returned no rows.")
        return 0

    print(
        f"{result['records_processed']:,} of {result['total_records']:,} record(s) sent in "
        f"{result['successful_batches']}/{result['total_batches']} batch(es)"
    )

    # Per-record outcomes into LOGS.SUCCESS / LOGS.FAILURE, so a failure can be
    # traced back to the source row that caused it. Best-effort by design.
    for batch in result["batch_results"]:
        if batch.get("job_id"):
            process_bulk_api_results(
                warehouse, access_info, batch["job_id"], match_field=MATCH_FIELD
            )

    # Non-zero if any batch failed, so a Job task surfaces it as a failure.
    return 1 if result["failed_batches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
