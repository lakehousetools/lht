"""
Shared helpers.

Imports here are resolved on first attribute access, not at import time. The
Snowflake writers below pull in Snowpark, and `from lht.util import csv` -- on
the reverse-ETL path, which needs none of them -- would otherwise make Snowpark
a hard requirement of running lht on Databricks.
"""

from typing import Any

# Attribute -> module that defines it, relative to this package.
_EXPORTS = {
    'build_soql': 'soql_query',
    'json_to_csv': 'csv',
    'write_dataframe_to_table': 'data_writer',
    'write_batch_to_temp_table': 'data_writer',
    'write_batch_to_main_table': 'data_writer',
    'validate_dataframe_types': 'data_writer',
    'standardize_dataframe_types': 'data_writer',
    'write_dataframe_with_type_handling': 'data_writer',
    'create_salesforce_table': 'table_creator',
    'ensure_table_exists_for_dataframe': 'table_creator',
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(f"{__name__}.{module_name}"), name)


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
