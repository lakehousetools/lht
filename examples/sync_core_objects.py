"""Sync a set of core Salesforce objects into Snowflake.

Uses the primary saved connections (see `lht create-connection`). The first
run does a full load of each object; later runs load only changed records.

    python examples/sync_core_objects.py
"""

from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info
from lht.salesforce.intelligent_sync import sync_sobject_intelligent

OBJECTS = ["Account", "Contact", "Opportunity", "Lead", "Case", "User"]
SCHEMA = "RAW"


def main():
    session = create_session()                 # or create_session(connection_name="my_snowflake")
    access_info = get_salesforce_access_info()  # or get_salesforce_access_info("my_salesforce")

    failures = []
    for sobject in OBJECTS:
        result = sync_sobject_intelligent(
            session=session,
            access_info=access_info,
            sobject=sobject,
            schema=SCHEMA,
            table=sobject.upper(),
        )
        status = "ok" if result.get("success") else f"FAILED: {result.get('error')}"
        print(f"{sobject:<12} {result.get('sync_method', '-'):<24} {result.get('actual_records', 0):>10,}  {status}")
        if not result.get("success"):
            failures.append(sobject)

    session.close()
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
