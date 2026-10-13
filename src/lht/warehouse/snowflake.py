"""Snowflake, through a Snowpark session."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Sequence, Tuple

from lht.util.sql import identifier
from lht.warehouse.base import Warehouse, iso_timestamp

logger = logging.getLogger(__name__)


class SnowflakeWarehouse(Warehouse):
    """
    lht's original backend. The column types here are the ones lht has always
    written, so an existing LOGS schema keeps working untouched.

    Nothing in this class imports Snowpark: it only calls ``sql()`` on the
    session it was handed, which is also what lets a test pass a fake. Snowpark
    is imported where a session is *created*, in :mod:`lht.user.auth`.
    """

    name = 'snowflake'

    TYPES: Dict[str, str] = {
        'str': 'VARCHAR',
        'str20': 'VARCHAR(20)',
        'str50': 'VARCHAR(50)',
        'str255': 'VARCHAR(255)',
        'str255_not_null': 'VARCHAR(255) NOT NULL',
        'text': 'VARCHAR(16777216)',
        'key': 'VARCHAR(255) PRIMARY KEY',
        'autoincrement': 'INTEGER IDENTITY PRIMARY KEY',
        'timestamp': 'TIMESTAMP_NTZ',
        'audit_timestamp': 'TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()',
        'int': 'INTEGER',
        'bool': 'BOOLEAN',
    }

    def timestamp_literal(self, value: Optional[str]) -> str:
        normalized = iso_timestamp(value)
        if normalized is None:
            return 'NULL'
        return f"TO_TIMESTAMP_NTZ(TO_TIMESTAMP_TZ({self.literal(normalized)}))"

    def add_columns_if_missing(self, table: str, columns: Sequence[Tuple[str, str]]) -> None:
        """
        Add MATCH_FIELD/MATCH_ID to a log table created before they existed.

        Deployments predating those columns are the reason this exists; on a
        table this release created, every ALTER is a no-op.
        """
        for column, logical_type in columns:
            try:
                self.execute(
                    f"ALTER TABLE {identifier(table)} "
                    f"ADD COLUMN IF NOT EXISTS {self.column_ddl(column, logical_type)}"
                )
            except Exception as e:
                logger.warning(f"⚠️ Warning: Could not add {column} to {table}: {e}")
