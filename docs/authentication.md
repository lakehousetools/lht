# Authentication

lht authenticates to Salesforce with OAuth 2.0 and to Snowflake with key-pair (JWT) authentication. It never asks for, or stores, a Salesforce or Snowflake password.

## Salesforce

lht supports two server-to-server OAuth flows. Neither needs a browser or a user login.

| Flow | Best for | What lht needs |
|---|---|---|
| **Client Credentials** (default) | Most setups; used by `lht create-connection --salesforce` | Consumer key, consumer secret, My Domain |
| **JWT Bearer** | Unattended jobs where you'd rather manage a certificate than a secret | Consumer key, username, private key |

### Client Credentials flow

1. In Setup, create an **External Client App** (or a **Connected App**) and enable OAuth.
2. Enable **Client Credentials Flow**. Add the scopes lht needs: `api` is enough for sync and reverse ETL.
3. Set a **Run As** user. lht acts with that user's permissions, so give it read access to the objects you sync, and write access to the objects you push to.
4. Copy the **Consumer Key** and **Consumer Secret**.
5. Find your **My Domain** under Setup → My Domain. It's everything before `.my.salesforce.com`, for example `acme` or `acme--dev.sandbox`.

Salesforce reference: [OAuth 2.0 Client Credentials Flow](https://help.salesforce.com/s/articleView?id=xcloud.remoteaccess_oauth_client_credentials_flow.htm).

Then run:

```bash
lht create-connection --salesforce
```

lht sends the key and secret in a form-encoded POST body to `https://<my-domain>.my.salesforce.com/services/oauth2/token`, never in the URL.

### JWT Bearer flow

1. Generate a key pair and certificate:
   ```bash
   openssl req -x509 -sha256 -nodes -days 730 -newkey rsa:2048 \
     -keyout sf_private.key -out sf_cert.crt -subj "/CN=lht"
   ```
2. In your app, enable **Use digital signatures** and upload `sf_cert.crt`.
3. Pre-authorize the integration user: set the app to "Admin approved users are pre-authorized" and add the user's profile or permission set.
4. Pass the credentials to lht:
   ```python
   from lht.user.salesforce_auth import get_salesforce_access_info_from_credentials

   access_info = get_salesforce_access_info_from_credentials({
       "auth_flow": "jwt_bearer",
       "client_id": "<consumer key>",
       "username": "integration@example.com",
       "private_key_pem": open("sf_private.key", "rb").read(),
       "sandbox": False,   # True uses https://test.salesforce.com
       # "login_url": "https://acme.my.salesforce.com",   # optional override
   })
   ```

## Snowflake

lht connects through Snowpark using [key-pair authentication](https://docs.snowflake.com/en/user-guide/key-pair-auth).

1. Generate a key pair. Encrypting the private key is optional but recommended:
   ```bash
   openssl genrsa 2048 | openssl pkcs8 -topk8 -v2 des3 -inform PEM -out rsa_key.p8
   openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
   ```
2. Create a role and user, and attach the public key:
   ```sql
   CREATE ROLE IF NOT EXISTS LHT_ROLE;
   GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE LHT_ROLE;
   GRANT USAGE ON DATABASE SALESFORCE TO ROLE LHT_ROLE;
   GRANT USAGE, CREATE TABLE ON SCHEMA SALESFORCE.RAW TO ROLE LHT_ROLE;
   -- optional: allow lht to create schemas it's told to sync into
   GRANT CREATE SCHEMA ON DATABASE SALESFORCE TO ROLE LHT_ROLE;

   CREATE USER IF NOT EXISTS LHT_USER DEFAULT_ROLE = LHT_ROLE TYPE = SERVICE;
   GRANT ROLE LHT_ROLE TO USER LHT_USER;
   ALTER USER LHT_USER SET RSA_PUBLIC_KEY = '<contents of rsa_key.pub without the header/footer lines>';
   ```
3. Save the connection:
   ```bash
   lht create-connection --snowflake
   ```
   lht copies the private key into `~/.solomo/` with `0600` permissions. It stores the passphrase, if you entered one, in `connections.toml`, which is also `0600`.

For reverse ETL with `--log-results`, the role also needs `CREATE SCHEMA` (for `LOGS`) or ownership of an existing `LOGS` schema.

## Where credentials live

| Item | Location | Permissions |
|---|---|---|
| Connection settings and secrets | `~/.solomo/connections.toml` | `0600` |
| Snowflake private keys | `~/.solomo/<key file>` | `0600` |
| Directory | `~/.solomo/` | `0700` |

To avoid a local file entirely (CI, containers, orchestrators), pass credentials straight to `create_session()` and `get_salesforce_access_info_from_credentials()` from your secret manager. See [Python API](python-api.md#headless-credentials).
