"""Run a sync with credentials from environment variables instead of ~/.solomo.

Suitable for CI, Airflow, Dagster, cron in a container, or any job that gets
secrets from a secret manager. Required environment variables:

    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE,
    SNOWFLAKE_DATABASE, SNOWFLAKE_PRIVATE_KEY_FILE
    SF_CLIENT_ID, SF_USERNAME, SF_PRIVATE_KEY   (JWT bearer flow)

Optional: SNOWFLAKE_PRIVATE_KEY_PASSPHRASE, SF_SANDBOX=true
"""

import os

from lht.user.auth import create_session
from lht.user.salesforce_auth import get_salesforce_access_info_from_credentials
from lht.salesforce.intelligent_sync import sync_sobject_intelligent


def main():
    session = create_session({
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": "RAW",
        "private_key_file": os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
        "private_key_passphrase": os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"),
    })

    access_info = get_salesforce_access_info_from_credentials({
        "auth_flow": "jwt_bearer",
        "client_id": os.environ["SF_CLIENT_ID"],
        "username": os.environ["SF_USERNAME"],
        "private_key_pem": os.environ["SF_PRIVATE_KEY"],
        "sandbox": os.environ.get("SF_SANDBOX", "").lower() == "true",
    })

    result = sync_sobject_intelligent(session, access_info, "Account", schema="RAW", table="ACCOUNT")
    print(result)
    raise SystemExit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
