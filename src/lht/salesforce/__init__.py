"""
Salesforce operations.

Imports here are resolved on first attribute access, not at import time. The
sync path pulls in Snowpark through the Snowflake writers, and reverse ETL --
which runs on Databricks too -- needs none of it, so importing
`lht.salesforce.retl` must not drag Snowpark in with it.
"""

from typing import Any

# Attribute -> the module that defines it. A name without a dot is a module
# in this package; a dotted one is a full module path.
_EXPORTS = {
    'describe': 'sobjects',
    'query_records': 'sobject_query',
    'create': 'sobject_create',
    'sync_sobject_intelligent': 'intelligent_sync',
    'IntelligentSync': 'intelligent_sync',
    'create_batch_query': 'query_bapi20',
    'query_status': 'query_bapi20',
    'delete_query': 'query_bapi20',
    'get_query_ids': 'query_bapi20',
    'get_bulk_results': 'query_bapi20',
    'get_bulk_results_direct': 'query_bapi20',
    'cleanup_completed_jobs': 'query_bapi20',
    'delete_specific_job': 'query_bapi20',
    'write_dataframe_to_table': 'lht.util.data_writer',
    'write_batch_to_temp_table': 'lht.util.data_writer',
    'write_batch_to_main_table': 'lht.util.data_writer',
    'validate_dataframe_types': 'lht.util.data_writer',
    'standardize_dataframe_types': 'lht.util.data_writer',
    'write_dataframe_with_type_handling': 'lht.util.data_writer',
    'create_salesforce_table': 'lht.util.table_creator',
    'ensure_table_exists_for_dataframe': 'lht.util.table_creator',
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    if '.' not in module_name:
        module_name = f"{__name__}.{module_name}"
    return getattr(import_module(module_name), name)


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
