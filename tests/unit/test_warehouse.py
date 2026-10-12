"""
The warehouse layer: the right backend is picked for a session, and each
backend spells lht's log tables in its own SQL.

The Snowflake DDL assertions are deliberately literal. An existing LOGS schema
is not recreated by `CREATE TABLE IF NOT EXISTS`, so quietly changing a column
type here would leave new deployments disagreeing with old ones.
"""

import pytest

from lht.warehouse import DatabricksWarehouse, SnowflakeWarehouse, Warehouse, from_session
from lht.warehouse.base import (
    FAILURE_COLUMNS,
    JOB_INFO_COLUMNS,
    RETL_HISTORY_COLUMNS,
    SUCCESS_COLUMNS,
    iso_timestamp,
    row_to_dict,
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows


class _FakeSession:
    """Records every statement, and answers queries with canned rows."""

    module = None  # set on the subclasses below to drive backend detection

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.statements = []

    def sql(self, statement):
        self.statements.append(statement)
        return _Result(self.rows)


class _SnowparkSession(_FakeSession):
    pass


class _SparkSession(_FakeSession):
    pass


# from_session reads the session's defining module, so a fake has to claim one.
_SnowparkSession.__module__ = 'snowflake.snowpark.session'
_SparkSession.__module__ = 'pyspark.sql.connect.session'


class _Row:
    def __init__(self, **kv):
        self._kv = kv

    def asDict(self):
        return dict(self._kv)


# --- picking a backend ---------------------------------------------------

def test_a_snowpark_session_is_snowflake():
    warehouse = from_session(_SnowparkSession())
    assert isinstance(warehouse, SnowflakeWarehouse)
    assert warehouse.name == 'snowflake'


def test_a_spark_session_is_databricks():
    warehouse = from_session(_SparkSession())
    assert isinstance(warehouse, DatabricksWarehouse)
    assert warehouse.name == 'databricks'


def test_a_warehouse_passes_through_so_wrapping_is_idempotent():
    warehouse = DatabricksWarehouse(_SparkSession())
    assert from_session(warehouse) is warehouse
    assert from_session(from_session(warehouse)) is warehouse


def test_an_unrecognised_session_is_treated_as_snowflake():
    # Every caller written before this module passed a Snowpark session or a
    # stand-in for one; those must keep behaving exactly as they did.
    assert isinstance(from_session(_FakeSession()), SnowflakeWarehouse)


def test_something_that_cannot_run_sql_is_rejected_up_front():
    with pytest.raises(TypeError, match='sql'):
        from_session(object())


# --- reading rows -------------------------------------------------------

@pytest.mark.parametrize('session_class', [_SnowparkSession, _SparkSession])
def test_rows_come_back_as_plain_dicts(session_class):
    session = session_class(rows=[_Row(ID='001', Name='A'), _Row(ID='002', Name='B')])
    assert from_session(session).rows('SELECT 1') == [
        {'ID': '001', 'Name': 'A'},
        {'ID': '002', 'Name': 'B'},
    ]
    assert session.statements == ['SELECT 1']


def test_row_to_dict_accepts_rows_and_mappings():
    assert row_to_dict(_Row(A=1)) == {'A': 1}
    assert row_to_dict({'A': 1}) == {'A': 1}


def test_row_to_dict_rejects_anything_else():
    with pytest.raises(TypeError):
        row_to_dict(('A', 1))


# --- DDL ----------------------------------------------------------------

def _ddl(warehouse, table, columns):
    session = warehouse.session
    warehouse.create_table(table, columns)
    return ' '.join(session.statements[-1].split())


def test_snowflake_log_tables_keep_the_types_lht_has_always_written():
    warehouse = SnowflakeWarehouse(_SnowparkSession())
    assert _ddl(warehouse, 'LOGS.RETL_HISTORY', RETL_HISTORY_COLUMNS) == (
        'CREATE TABLE IF NOT EXISTS LOGS.RETL_HISTORY ( ID VARCHAR, OPERATION VARCHAR, '
        'OBJECT VARCHAR, CREATEDBYID VARCHAR, CREATEDDATE TIMESTAMP_NTZ, '
        'EXTERNALIDFIELDNAME VARCHAR, CONTENTURL VARCHAR )'
    )
    success = _ddl(warehouse, 'LOGS.SUCCESS', SUCCESS_COLUMNS)
    assert 'ID INTEGER IDENTITY PRIMARY KEY' in success
    assert 'JOB_ID VARCHAR(255) NOT NULL' in success
    assert 'MATCH_ID VARCHAR(16777216)' in success
    assert 'CREATED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()' in success
    assert 'ID VARCHAR(255) PRIMARY KEY' in _ddl(warehouse, 'LOGS.JOB_INFO', JOB_INFO_COLUMNS)


def test_databricks_log_tables_use_delta_types():
    warehouse = DatabricksWarehouse(_SparkSession())
    assert _ddl(warehouse, 'main.logs.RETL_HISTORY', RETL_HISTORY_COLUMNS) == (
        'CREATE TABLE IF NOT EXISTS main.logs.RETL_HISTORY ( ID STRING, OPERATION STRING, '
        'OBJECT STRING, CREATEDBYID STRING, CREATEDDATE TIMESTAMP_NTZ, '
        'EXTERNALIDFIELDNAME STRING, CONTENTURL STRING )'
    )
    for columns, table in ((SUCCESS_COLUMNS, 'LOGS.SUCCESS'), (FAILURE_COLUMNS, 'LOGS.FAILURE'),
                           (JOB_INFO_COLUMNS, 'LOGS.JOB_INFO')):
        ddl = _ddl(warehouse, table, columns)
        # VARCHAR(n) is accepted but not enforced on Delta, and a column DEFAULT
        # needs a table feature lht does not want to depend on.
        assert 'VARCHAR' not in ddl, table
        assert 'DEFAULT' not in ddl, table
        assert 'PRIMARY KEY' not in ddl, table


def test_every_log_table_column_has_a_type_in_both_backends():
    for warehouse in (SnowflakeWarehouse(_SnowparkSession()), DatabricksWarehouse(_SparkSession())):
        for columns in (RETL_HISTORY_COLUMNS, JOB_INFO_COLUMNS, SUCCESS_COLUMNS, FAILURE_COLUMNS):
            for column, logical_type in columns:
                assert warehouse.column_ddl(column, logical_type).startswith(column)


def test_an_unknown_logical_type_names_itself():
    with pytest.raises(KeyError, match='nonesuch'):
        SnowflakeWarehouse(_SnowparkSession()).column_ddl('C', 'nonesuch')


def test_a_table_name_that_could_inject_sql_is_rejected():
    warehouse = DatabricksWarehouse(_SparkSession())
    with pytest.raises(ValueError):
        warehouse.create_table('LOGS.X; DROP TABLE Y', RETL_HISTORY_COLUMNS)
    with pytest.raises(ValueError):
        warehouse.insert_rows('LOGS.X)--', ('A',), [("'1'",)])


def test_only_snowflake_backfills_the_match_columns():
    # Those columns predate nothing on Databricks: every table there was created
    # by a release that already has them, so there is nothing to ALTER.
    snowflake = SnowflakeWarehouse(_SnowparkSession())
    snowflake.add_columns_if_missing('LOGS.SUCCESS', (('MATCH_FIELD', 'str255'),))
    assert snowflake.session.statements == [
        'ALTER TABLE LOGS.SUCCESS ADD COLUMN IF NOT EXISTS MATCH_FIELD VARCHAR(255)'
    ]

    databricks = DatabricksWarehouse(_SparkSession())
    databricks.add_columns_if_missing('LOGS.SUCCESS', (('MATCH_FIELD', 'str255'),))
    assert databricks.session.statements == []


# --- inserts ------------------------------------------------------------

def test_insert_rows_batches_into_one_statement_per_chunk():
    # One INSERT per record turned a 25k batch into 25k round trips.
    warehouse = DatabricksWarehouse(_SparkSession())
    rows = [(f"'{i}'", "'x'") for i in range(7)]
    warehouse.insert_rows('LOGS.SUCCESS', ('SF_ID', 'MATCH_ID'), rows, chunk_size=3)

    assert len(warehouse.session.statements) == 3
    sent = ' '.join(warehouse.session.statements)
    assert sent.count('INSERT INTO LOGS.SUCCESS (SF_ID, MATCH_ID) VALUES') == 3
    for i in range(7):
        assert f"('{i}', 'x')" in sent


def test_insert_rows_sends_nothing_when_there_are_no_rows():
    warehouse = SnowflakeWarehouse(_SnowparkSession())
    warehouse.insert_rows('LOGS.SUCCESS', ('SF_ID',), [])
    assert warehouse.session.statements == []


# --- string literals ----------------------------------------------------

def test_snowflake_escapes_a_quote_by_doubling_it():
    assert SnowflakeWarehouse(_SnowparkSession()).literal("O'Brien") == "'O''Brien'"


def _inside(rendered):
    """The escaped body of a rendered literal, without its surrounding quotes."""
    assert rendered.startswith("'") and rendered.endswith("'"), rendered
    return rendered[1:-1]


def test_databricks_escapes_a_quote_with_a_backslash():
    # Spark concatenates adjacent string literals, so 'it''s' parses as 'it'
    # followed by 's' and evaluates to "its" -- the apostrophe is dropped with
    # no error at all, quietly corrupting any logged Salesforce value.
    # Verified against Spark 4.0: 'it''s' -> 'its', 'it\'s' -> "it's".
    assert _inside(DatabricksWarehouse(_SparkSession()).literal("it's")) == "it\\'s"


def test_databricks_escapes_a_backslash_before_the_quotes():
    # Inside a Spark string literal a backslash is an escape character -- '\b' is
    # a backspace -- so a raw backslash has to be doubled. Doubled *first*, or
    # the backslash added for a quote would itself get escaped.
    warehouse = DatabricksWarehouse(_SparkSession())
    one, two, three = '\\', '\\' * 2, '\\' * 3

    assert _inside(warehouse.literal('C:' + one + 'path')) == 'C:' + two + 'path'
    assert _inside(warehouse.literal('ends' + one)) == 'ends' + two
    # A backslash followed by a quote: two for the backslash, one for the quote.
    assert _inside(warehouse.literal(one + "'")) == three + "'"


@pytest.mark.parametrize('warehouse_class,session_class',
                         [(SnowflakeWarehouse, _SnowparkSession), (DatabricksWarehouse, _SparkSession)])
def test_a_none_is_null_not_the_string_none(warehouse_class, session_class):
    assert warehouse_class(session_class()).literal(None) == 'NULL'


@pytest.mark.parametrize('warehouse_class,session_class,expected', [
    (SnowflakeWarehouse, _SnowparkSession, "x''; DROP TABLE t; --"),
    (DatabricksWarehouse, _SparkSession, "x\\'; DROP TABLE t; --"),
])
def test_a_value_cannot_break_out_of_its_literal(warehouse_class, session_class, expected):
    rendered = warehouse_class(session_class()).literal("x'; DROP TABLE t; --")
    assert _inside(rendered) == expected


# --- timestamps ---------------------------------------------------------

@pytest.mark.parametrize('raw,expected', [
    ('2026-01-01T12:00:00.000+0000', '2026-01-01 12:00:00.000'),
    ('2026-01-01T12:00:00Z', '2026-01-01 12:00:00'),
    ('2026-01-01T12:00:00.123456+00:00', '2026-01-01 12:00:00.123'),
    ('', None),
    (None, None),
    ('2026-01-01', None),
])
def test_salesforce_timestamps_lose_their_zone_offset(raw, expected):
    # Salesforce reports UTC and the column has no zone, so the offset is
    # dropped rather than converted.
    assert iso_timestamp(raw) == expected


def test_each_backend_casts_a_timestamp_its_own_way():
    raw = '2026-01-01T12:00:00.000+0000'
    assert SnowflakeWarehouse(_SnowparkSession()).timestamp_literal(raw) == (
        "TO_TIMESTAMP_NTZ(TO_TIMESTAMP_TZ('2026-01-01 12:00:00.000'))"
    )
    assert DatabricksWarehouse(_SparkSession()).timestamp_literal(raw) == (
        "CAST('2026-01-01 12:00:00.000' AS TIMESTAMP_NTZ)"
    )


@pytest.mark.parametrize('warehouse_class,session_class',
                         [(SnowflakeWarehouse, _SnowparkSession), (DatabricksWarehouse, _SparkSession)])
def test_a_missing_timestamp_is_null_not_a_broken_cast(warehouse_class, session_class):
    assert warehouse_class(session_class()).timestamp_literal(None) == 'NULL'


def test_warehouse_is_abstract_so_a_backend_must_define_its_dialect():
    with pytest.raises(TypeError):
        Warehouse(_FakeSession())
