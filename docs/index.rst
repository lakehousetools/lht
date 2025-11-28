.. Lakehouse Tools - Salesforce documentation master file, created by
   sphinx-quickstart on Thu Jun  5 17:40:35 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Lakehouse Tools - Salesforce's documentation!
========================================================

LHT is a Python library for synchronizing Salesforce data to Snowflake using
Bulk API 2.0.

Features
--------

* **Bulk API 2.0**: All syncs use Salesforce Bulk API 2.0 for efficient data extraction
* **Incremental Sync**: Automatically detects and syncs only changed records based on LastModifiedDate
* **Full Sync**: Complete data synchronization for first-time syncs
* **Job Management**: List, view, and manage Bulk API 2.0 jobs via CLI
* **CLI Tools**: Command-line interface for all operations
* **Data Type Mapping**: Automatic Salesforce to Snowflake type conversion
* **MERGE Operations**: Efficient upsert logic for incremental syncs

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules

Indices and tables
==================

* :ref:`genindex`
* :doc:`modules`
* :ref:`search`
