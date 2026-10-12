"""
The warehouse surface the Salesforce code runs against.

Reverse ETL needs very little from a warehouse: read the rows a SELECT
produces, and run the DDL/DML for lht's own log tables. Everything else --
Bulk API jobs, CSV payloads, polling -- is warehouse-independent already.
That narrow surface is what this module defines, so `retl.upsert()` can take a
Snowpark session on Snowflake and a Spark session on Databricks without
knowing which it has.

The log tables are lht's own, so their shape lives here once, rendered through
each backend's type map rather than duplicated as two slabs of DDL.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from lht.util.sql import identifier, literal

logger = logging.getLogger(__name__)


def iso_timestamp(value: Optional[str]) -> Optional[str]:
    """
    A Salesforce ISO-8601 timestamp as ``YYYY-MM-DD HH:MM:SS.sss``, or None.

    Salesforce answers with ``2026-01-01T12:00:00.000+0000``. Both backends
    parse the space-separated form with sub-second digits and no zone offset,
    so the offset is dropped rather than converted -- Salesforce reports UTC,
    and the column it lands in has no zone either.
    """
    if not value:
        return None
    text = str(value).strip().replace('T', ' ')
    if len(text) < 19:
        return None
    fraction = re.match(r'(\.\d+)', text[19:])
    return text[:19] + (fraction.group(1)[:4] if fraction else '')


def row_to_dict(row: Any) -> Dict[str, Any]:
    """
    One result row as a plain dict.

    Snowpark and PySpark ``Row`` objects both answer ``asDict()``, which is why
    the two backends need no separate row handling. A mapping is passed through
    so a hand-built fake row stays usable in tests.
    """
    if isinstance(row, Mapping):
        return dict(row)
    as_dict = getattr(row, 'asDict', None)
    if callable(as_dict):
        return dict(as_dict())
    raise TypeError(
        f"Cannot read a result row of type {type(row).__name__}; "
        "expected a mapping or a Row with asDict()."
    )


# lht's own log tables, as (column, logical type). Each backend maps the
# logical types to its own physical ones in TYPES below.
#
# CREATED_AT is written explicitly by insert_rows() rather than left to a
# column DEFAULT: Snowflake takes a DEFAULT clause, Delta only does with an
# extra table feature enabled, and CURRENT_TIMESTAMP() means the same thing to
# both. Snowflake's DDL keeps its DEFAULT for anything else writing the table.
RETL_HISTORY_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ('ID', 'str'),
    ('OPERATION', 'str'),
    ('OBJECT', 'str'),
    ('CREATEDBYID', 'str'),
    ('CREATEDDATE', 'timestamp'),
    ('EXTERNALIDFIELDNAME', 'str'),
    ('CONTENTURL', 'str'),
)

JOB_INFO_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ('ID', 'key'),
    ('OPERATION', 'str50'),
    ('OBJECT', 'str255'),
    ('CREATED_BY_ID', 'str255'),
    ('CREATED_DATE', 'timestamp'),
    ('SYSTEM_MODSTAMP', 'timestamp'),
    ('STATE', 'str20'),
    ('JOB_TYPE', 'str50'),
    ('NUMBER_RECORDS_PROCESSED', 'int'),
    ('NUMBER_RECORDS_FAILED', 'int'),
    ('RETRY_COUNT', 'int'),
    ('TOTAL_PROCESSING_TIME', 'int'),
    ('API_ACTIVE_PROCESSING_TIME', 'int'),
    ('AVERAGE_PER_SECOND', 'int'),
    ('AVERAGE_PER_BATCH', 'int'),
    ('NUMBER_RECORDS_TOTAL', 'int'),
    ('NUMBER_BATCHES_TOTAL', 'int'),
    ('NUMBER_BATCHES_IN_PROGRESS', 'int'),
    ('NUMBER_BATCHES_COMPLETED', 'int'),
    ('NUMBER_BATCHES_FAILED', 'int'),
    ('NUMBER_BATCHES_PENDING', 'int'),
    ('BYTES_PROCESSED', 'int'),
    ('ERROR_CODE', 'str255'),
    ('ERROR_MESSAGE', 'text'),
    ('CREATED_AT', 'audit_timestamp'),
)

SUCCESS_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ('ID', 'autoincrement'),
    ('JOB_ID', 'str255_not_null'),
    ('SF_ID', 'str255'),
    ('CREATED', 'bool'),
    ('SUCCESS', 'bool'),
    ('ERRORS', 'text'),
    ('MATCH_FIELD', 'str255'),
    ('MATCH_ID', 'text'),
    ('CREATED_AT', 'audit_timestamp'),
)

FAILURE_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ('ID', 'autoincrement'),
    ('JOB_ID', 'str255_not_null'),
    ('SF_ID', 'str255'),
    ('SF_ERROR', 'text'),
    ('MATCH_FIELD', 'str255'),
    ('MATCH_ID', 'text'),
    ('CREATED_AT', 'audit_timestamp'),
)


class Warehouse(ABC):
    """
    What lht needs from a warehouse, and how that warehouse spells SQL.

    Subclasses implement the two execution methods and supply ``TYPES``.
    Instances are cheap wrappers around a live session, created once per run;
    they hold no state of their own beyond that session.
    """

    #: Short backend name, for log lines and error messages.
    name = 'warehouse'

    #: Logical type -> this backend's column definition fragment. The fragment
    #: is everything after the column name, so it can carry constraints too.
    TYPES: Dict[str, str] = {}

    def __init__(self, session: Any):
        self.session = session

    def __repr__(self) -> str:
        return f"<{type(self).__name__} session={type(self.session).__name__}>"

    # --- execution -----------------------------------------------------
    #
    # Snowpark and PySpark happen to agree on `session.sql(text).collect()`
    # returning rows that answer asDict(), so both backends share these.

    def rows(self, query: str) -> List[Dict[str, Any]]:
        """
        Run a query and return every row as a plain dict.

        Reverse ETL reads the whole result into memory on purpose: the rows are
        then cut into Bulk API batches locally, so the query runs exactly once.
        Re-reading it per batch without an ORDER BY could send a row twice or
        never, since neither backend promises a stable order across runs. The
        driver therefore has to hold the result set -- keep the query to the
        rows that actually need pushing.
        """
        return [row_to_dict(row) for row in self.session.sql(query).collect()]

    def execute(self, statement: str) -> None:
        """Run a statement for its effect (DDL, INSERT) and discard any result."""
        self.session.sql(statement).collect()

    # --- dialect -------------------------------------------------------

    def column_ddl(self, column: str, logical_type: str) -> str:
        """One column's definition, e.g. ``MATCH_ID VARCHAR(16777216)``."""
        try:
            return f"{column} {self.TYPES[logical_type]}".rstrip()
        except KeyError:
            raise KeyError(
                f"{type(self).__name__} has no column type for {logical_type!r}"
            ) from None

    def create_table(self, table: str, columns: Sequence[Tuple[str, str]]) -> None:
        """Create one of lht's log tables if it isn't there yet."""
        definitions = ',\n    '.join(
            self.column_ddl(column, logical_type) for column, logical_type in columns
        )
        self.execute(
            f"CREATE TABLE IF NOT EXISTS {identifier(table)} (\n    {definitions}\n)"
        )

    def create_schema(self, schema: str) -> None:
        """Create a schema if it isn't there yet."""
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {identifier(schema)}")

    def insert_rows(
        self,
        table: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[str]],
        chunk_size: int = 500,
    ) -> None:
        """
        Insert rows of already-rendered SQL literals, a chunk per statement.

        Values arrive pre-rendered -- via this warehouse's own :meth:`literal`
        (never the module-level one, whose escaping is wrong for some backends)
        or one of its expressions, such as a timestamp cast -- because the
        callers build rows of mixed literals and expressions. One INSERT per record turned a 25k
        batch into 25k round trips, which is why result logging never finished
        on large jobs; chunking keeps it to a handful.
        """
        rows = [tuple(row) for row in rows]
        if not rows:
            return
        column_list = ', '.join(columns)
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start:start + chunk_size]
            values = ', '.join('({})'.format(', '.join(row)) for row in chunk)
            self.execute(
                f"INSERT INTO {identifier(table)} ({column_list}) VALUES {values}"
            )

    def literal(self, value: Any) -> str:
        """
        A Python value as a single-quoted SQL string literal, or ``NULL``.

        Part of the dialect because backends disagree on how a quote inside a
        literal is escaped, and getting it wrong corrupts data silently rather
        than failing. The default is the SQL standard's doubled quote.
        """
        return literal(value)

    def now(self) -> str:
        """SQL expression for the current timestamp."""
        return 'CURRENT_TIMESTAMP()'

    @abstractmethod
    def timestamp_literal(self, value: Optional[str]) -> str:
        """
        A Salesforce ISO-8601 timestamp as a SQL expression of this backend's
        timestamp type, or ``NULL``.
        """

    def add_columns_if_missing(self, table: str, columns: Sequence[Tuple[str, str]]) -> None:
        """
        Backfill columns onto a log table created by an older lht.

        A no-op by default: only Snowflake has deployments that predate
        MATCH_FIELD/MATCH_ID, and a table this release created already has them.
        """
        return None
