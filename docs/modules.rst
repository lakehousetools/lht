API Reference
=============

This page contains the API reference for all modules in the LHT package.

Salesforce Modules
------------------

Bulk API 2.0 Jobs
~~~~~~~~~~~~~~~~~

.. automodule:: lht.salesforce.jobs
   :members:
   :undoc-members:
   :show-inheritance:

   This module provides functions to list, retrieve, and delete Bulk API 2.0 jobs.

Intelligent Sync
~~~~~~~~~~~~~~~~

.. automodule:: lht.salesforce.intelligent_sync
   :members:
   :undoc-members:
   :show-inheritance:

   Synchronization orchestrator for Salesforce data using Bulk API 2.0. All syncs use
   Bulk API 2.0 regardless of data volume. The system automatically determines whether
   to perform a full sync (first-time) or incremental sync (based on LastModifiedDate).
   
   The orchestrator handles:
   
   * Schema and table existence checking
   * LastModifiedDate detection for incremental syncs
   * Record count estimation
   * Full vs incremental sync determination
   * Stage vs non-stage sync options
   * Bulk API 2.0 job orchestration
   * Result compilation and metadata collection
   
   **Note:** The regular API sync method has been removed. All synchronizations now
   exclusively use Bulk API 2.0 for consistency and performance.

Bulk API 2.0 Query
~~~~~~~~~~~~~~~~~~

.. automodule:: lht.salesforce.query_bapi20
   :members:
   :undoc-members:
   :show-inheritance:

   Functions for creating and managing Bulk API 2.0 query jobs.

SObjects
~~~~~~~~

.. automodule:: lht.salesforce.sobjects
   :members:
   :undoc-members:
   :show-inheritance:

   Salesforce object metadata and field descriptions.

SObject Sync
~~~~~~~~~~~~

.. automodule:: lht.salesforce.sobject_sync
   :members:
   :undoc-members:
   :show-inheritance:

   Incremental synchronization for Salesforce objects.

SObject Query
~~~~~~~~~~~~~

.. automodule:: lht.salesforce.sobject_query
   :members:
   :undoc-members:
   :show-inheritance:

   Query operations for Salesforce objects.

Bulk API Results
~~~~~~~~~~~~~~~~

.. automodule:: lht.salesforce.results_bapi
   :members:
   :undoc-members:
   :show-inheritance:

   Processing and storing Bulk API 2.0 job results.

CLI Commands
------------

All CLI commands are prefixed with ``lht``. The following sections document each command
and show their usage examples.

Job Management Commands
~~~~~~~~~~~~~~~~~~~~~~~

These commands allow you to manage Bulk API 2.0 jobs from the command line.

**List Jobs**

.. code-block:: bash

   lht list-jobs [--salesforce NAME] [--api-version VERSION]

.. automodule:: lht.cli.commands.list_jobs
   :members:
   :undoc-members:

   List all Bulk API 2.0 query jobs from Salesforce.

**Show Job**

.. code-block:: bash

   lht show-job <JOB_ID> [--salesforce NAME] [--api-version VERSION]

.. automodule:: lht.cli.commands.show_job
   :members:
   :undoc-members:

   Show detailed information about a specific Bulk API 2.0 job.

**Delete Job**

.. code-block:: bash

   lht delete-job <JOB_ID> [--salesforce NAME] [--api-version VERSION]

.. automodule:: lht.cli.commands.delete_job
   :members:
   :undoc-members:

   Delete a specific Bulk API 2.0 job from Salesforce.

Sync Command
~~~~~~~~~~~~

**Sync SObject**

.. code-block:: bash

   lht sync --sobject <SOBJECT> --table <TABLE> [--schema SCHEMA] [--database DATABASE]
            [--snowflake NAME] [--salesforce NAME] [--match-field FIELD]
            [--use-stage] [--stage-name STAGE] [--force-full-sync]
            [--force-bulk-api] [--existing-job-id JOB_ID] [--no-delete-job]
            [--where WHERE_CLAUSE]

.. automodule:: lht.cli.commands.sync_sobject
   :members:
   :undoc-members:

   Synchronize a Salesforce object to a Snowflake table using Bulk API 2.0.

Connection Commands
~~~~~~~~~~~~~~~~~~~

**Create Connection**

The create-connection command interactively prompts for connection details. Use ``--snowflake``
for Snowflake connections or ``--salesforce`` for Salesforce connections.

.. code-block:: bash

   lht create-connection --snowflake
   lht create-connection --salesforce

Create Snowflake Connection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you run ``lht create-connection --snowflake``, you will be prompted for the following:

**Required Arguments:**

* **Account** - Your Snowflake account identifier (e.g., ``xy12345.us-east-1`` or ``xy12345``)
* **Username** - Your Snowflake username
* **Role** - The Snowflake role to use (e.g., ``ACCOUNTADMIN``, ``SYSADMIN``)
* **Warehouse** - The Snowflake warehouse to use (e.g., ``COMPUTE_WH``)
* **Private Key File** - Path to your RSA private key file (PEM format) for JWT authentication
* **Connection Name** - A name to identify this connection (defaults to account name)

**Optional Arguments:**

* **Private Key Passphrase** - Passphrase for encrypted private key files (leave blank if key is unencrypted)
* **Database** - Default database to use (can be overridden when using the connection)
* **Schema** - Default schema to use (can be overridden when using the connection)

**Additional Prompts:**

* **Make this the primary connection?** - Set this connection as the default Snowflake connection (y/n)

**Example:**

.. code-block:: bash

   $ lht create-connection --snowflake
   ============================================================
   Snowflake Authentication
   ============================================================
   
   Account: xy12345.us-east-1
   Username: myuser
   Role: SYSADMIN
   Warehouse: COMPUTE_WH
   Private key file path: /path/to/rsa_key.p8
   Private key passphrase (optional): 
   Database (optional): MYDATABASE
   Schema (optional): MYSCHEMA
   Connection name [xy12345_us-east-1_mydatabase]: 
   Make this the primary connection? (y/n): y
   
   ✓ Connection 'xy12345_us-east-1_mydatabase' saved.

**Note:** The private key file must be in PEM format and is used for JWT authentication.
The key file is copied to the connections directory for secure storage.
For detailed instructions on configuring key-pair authentication, including how to generate
the key pair and assign the public key to your Snowflake user, see the 
`Snowflake Key-Pair Authentication documentation <https://docs.snowflake.com/en/user-guide/key-pair-auth>`_.

Create Salesforce Connection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you run ``lht create-connection --salesforce``, you will be prompted for the following:

**Required Arguments:**

* **Client ID** - The Consumer Key from your Salesforce Connected App
* **Client Key** - The Consumer Secret from your Salesforce Connected App (hidden input)
* **My Domain** - Your Salesforce My Domain identifier (e.g., ``mycompany`` or ``mycompany.my.salesforce.com``)
* **Connection Name** - A name to identify this connection (defaults to first part of My Domain)

**Optional Arguments:**

* **Sandbox** - Whether this is a Salesforce Sandbox instance (y/n, default: n)
* **Redirect URL** - OAuth redirect URL (default: ``https://localhost:1717//OauthRedirect``)

**Additional Prompts:**

* **Test connection now?** - Optionally test the connection before saving (y/n)
* **Make this the primary connection?** - Set this connection as the default Salesforce connection (y/n)

**Example:**

.. code-block:: bash

   $ lht create-connection --salesforce
   ============================================================
   Salesforce Authentication
   ============================================================
   
   Note: This interface currently only supports the web credentials flow.
   
   Client ID: 3MVG9abcdefghijklmnop...
   Client Key: ********
   Sandbox (y/n): n
   My Domain: mycompany
   Redirect URL [https://localhost:1717//OauthRedirect]: 
   Test connection now? (y/n): y
   
   Testing Salesforce connection...
   ✓ Connection test successful!
   
   Connection name [mycompany]: 
   Make this the primary connection? (y/n): y
   
   ✓ Connection 'mycompany' saved.

**Note:** The command line interface requires an External App (Connected App) configured for
the OAuth2.0 Client Credentials flow. The Client ID and Client Key are obtained from the
Connected App settings. For detailed instructions on setting up a Client Credentials flow
External App, see the 
`Salesforce documentation <https://help.salesforce.com/s/articleView?id=xcloud.remoteaccess_oauth_client_credentials_flow.htm>`_.

**API Note:** While the CLI requires Client Credentials flow, the underlying API supports
any kind of OAuth2 flow for authentication to obtain an access token from Salesforce.

.. automodule:: lht.cli.commands.create_connection
   :members:
   :undoc-members:

**List Connections**

.. code-block:: bash

   lht list-connections

.. automodule:: lht.cli.commands.list_connections
   :members:
   :undoc-members:

**Edit Connection**

.. code-block:: bash

   lht edit-connection

.. automodule:: lht.cli.commands.edit_connection
   :members:
   :undoc-members:

**Connect (Verify Connection)**

.. code-block:: bash

   lht connect <CONNECTION_NAME>

.. automodule:: lht.cli.commands.connect
   :members:
   :undoc-members:

**Set Primary Connection**

.. code-block:: bash

   lht set-primary <CONNECTION_NAME>

The lht commands will default to the primary connection if one is set. This means you can
omit the ``--snowflake`` or ``--salesforce`` connection name arguments when a primary
connection exists for that connection type.

.. automodule:: lht.cli.commands.set_primary
   :members:
   :undoc-members:

CLI Main
~~~~~~~~

.. automodule:: lht.cli
   :members:
   :undoc-members:

User Authentication
-------------------

Snowflake Authentication
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: lht.user.auth
   :members:
   :undoc-members:
   :show-inheritance:

Salesforce Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: lht.user.salesforce_auth
   :members:
   :undoc-members:
   :show-inheritance:

Connection Management
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: lht.user.connections.manager
   :members:
   :undoc-members:
   :show-inheritance:

Utilities
---------

Data Writer
~~~~~~~~~~~

.. automodule:: lht.util.data_writer
   :members:
   :undoc-members:
   :show-inheritance:

   Functions for writing DataFrames to Snowflake tables.

Field Types
~~~~~~~~~~~

.. automodule:: lht.util.field_types
   :members:
   :undoc-members:
   :show-inheritance:

   Salesforce to Snowflake field type mapping and conversion.

Merge Operations
~~~~~~~~~~~~~~~~

.. automodule:: lht.util.merge
   :members:
   :undoc-members:
   :show-inheritance:

   SQL MERGE statement generation for incremental syncs.

Table Creator
~~~~~~~~~~~~~

.. automodule:: lht.util.table_creator
   :members:
   :undoc-members:
   :show-inheritance:

   Functions for creating Snowflake tables from DataFrames.

Stage Operations
~~~~~~~~~~~~~~~~

.. automodule:: lht.util.stage
   :members:
   :undoc-members:
   :show-inheritance:

   Snowflake stage operations for file uploads.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

