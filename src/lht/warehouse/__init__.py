"""
Warehouse backends: Snowflake via Snowpark, Databricks via Spark.

Reverse ETL takes whichever session you already have. :func:`from_session`
recognises it, so ``lht.salesforce.retl`` keeps the same signature on both
warehouses and a notebook can hand it the cluster's ``spark`` directly::

    from lht.salesforce import retl
    retl.upsert(spark, access_info, 'Account', 'SELECT ...', 'Ext__c')

Neither backend imports its vendor library here: detection reads the session's
type, so importing lht on Databricks does not need Snowpark installed, and the
reverse holds too.
"""

from __future__ import annotations

import logging
from typing import Any

from lht.warehouse.base import Warehouse, iso_timestamp, row_to_dict
from lht.warehouse.databricks import DatabricksWarehouse
from lht.warehouse.snowflake import SnowflakeWarehouse

logger = logging.getLogger(__name__)

__all__ = [
    'Warehouse',
    'SnowflakeWarehouse',
    'DatabricksWarehouse',
    'from_session',
    'iso_timestamp',
    'row_to_dict',
]

# Top-level module a session's class comes from -> its backend. Spark Connect
# sessions, which is what Databricks Connect hands back, live under `pyspark`
# too.
_BACKENDS = {
    'snowflake': SnowflakeWarehouse,
    'pyspark': DatabricksWarehouse,
    'databricks': DatabricksWarehouse,
}


def from_session(session: Any) -> Warehouse:
    """
    The warehouse backend for a session object.

    Args:
        session: A Snowpark ``Session``, a Spark session, or a
            :class:`~lht.warehouse.base.Warehouse` (returned unchanged, so
            callers can pass either and this stays idempotent).

    Anything else that answers ``sql()`` is treated as Snowflake. That is
    deliberate: it is what every caller written before this module passed, and
    a Snowpark-shaped stand-in should keep behaving as it did.

    Raises:
        TypeError: If the object has no ``sql()`` method at all.
    """
    if isinstance(session, Warehouse):
        return session

    if not callable(getattr(session, 'sql', None)):
        raise TypeError(
            f"Expected a Snowpark session, a Spark session or an lht Warehouse, "
            f"got {type(session).__name__}, which has no sql() method."
        )

    root = type(session).__module__.split('.')[0]
    backend = _BACKENDS.get(root)
    if backend is None:
        logger.debug(
            "Treating a %s session as Snowflake; pass an lht.warehouse.Warehouse "
            "to choose a backend explicitly.", type(session).__name__
        )
        backend = SnowflakeWarehouse
    return backend(session)
