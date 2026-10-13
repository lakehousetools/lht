"""
Run the SQL lht generates for Databricks against a real Spark engine.

Marked `spark` and excluded by default; it needs `pyspark` and a JVM, not a
workspace or any credentials:

    pip install "pyspark==4.0.1"
    pytest -m spark

This is not redundant with the unit tests. Those assert what lht *writes*;
this asserts what Spark *does with it*, which is where the two diverged: Spark
concatenates adjacent string literals, so the SQL standard's `''` escape made
`O'Brien` arrive as `OBrien` with no error anywhere. Only an engine catches
that. Re-run it after touching `DatabricksWarehouse`.
"""

import tempfile

import pytest

from lht.warehouse import DatabricksWarehouse
from lht.warehouse.base import (
    FAILURE_COLUMNS,
    JOB_INFO_COLUMNS,
    RETL_HISTORY_COLUMNS,
    SUCCESS_COLUMNS,
)

pytestmark = pytest.mark.spark

# Delta table features a plain local Spark has no catalog for. The parser still
# accepts them, so the DDL is checked by parsing rather than by running it.
DELTA_ONLY = 'GENERATED ALWAYS AS IDENTITY'


@pytest.fixture(scope='module')
def spark():
    # Checked here rather than at import time, so the `spark` marker can
    # deselect this module without importing anything first.
    pytest.importorskip('pyspark', reason='pyspark is not installed')
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.appName('lht-dialect')
        .master('local[1]')
        .config('spark.sql.warehouse.dir', tempfile.mkdtemp())
        .config('spark.ui.enabled', 'false')
        .config('spark.sql.shuffle.partitions', '1')
        .getOrCreate()
    )
    session.sparkContext.setLogLevel('ERROR')
    session.sql('CREATE SCHEMA IF NOT EXISTS lht_test')
    yield session
    session.stop()


class _Recording:
    """Captures the SQL lht generates without running it."""

    def __init__(self):
        self.statements = []

    def sql(self, statement):
        self.statements.append(statement)
        return type('R', (), {'collect': lambda s: []})()


_Recording.__module__ = 'pyspark.sql.connect.session'


@pytest.fixture
def recorded():
    """A DatabricksWarehouse whose statements are captured, not executed."""
    return DatabricksWarehouse(_Recording())


def _run(spark, statements):
    """Parse every statement; run the ones a local Spark can."""
    for statement in statements:
        spark._jsparkSession.sessionState().sqlParser().parsePlan(statement)
        if DELTA_ONLY not in statement:
            spark.sql(statement)


@pytest.mark.parametrize('name,columns', [
    ('RETL_HISTORY', RETL_HISTORY_COLUMNS),
    ('JOB_INFO', JOB_INFO_COLUMNS),
    ('SUCCESS', SUCCESS_COLUMNS),
    ('FAILURE', FAILURE_COLUMNS),
])
def test_every_log_table_ddl_is_valid_spark_sql(spark, recorded, name, columns):
    recorded.create_table(f'lht_test.{name}', columns)
    _run(spark, recorded.session.statements)


def test_a_job_history_row_round_trips_through_spark(spark):
    from lht.util import log_retl

    recorded = DatabricksWarehouse(_Recording())
    log_retl.job(recorded, {
        'id': '750XX0000000001',
        'operation': 'upsert',
        'object': 'Account',
        'createdById': '005XX0000000001',
        'createdDate': '2026-01-01T12:00:00.000+0000',
        'externalIdFieldName': 'Ext__c',
        # An apostrophe and a backslash: the two characters that break a literal.
        'contentUrl': "jobs/it's/a\\path",
    }, schema='lht_test')
    _run(spark, recorded.session.statements)

    row = spark.sql('SELECT * FROM lht_test.RETL_HISTORY').collect()[-1].asDict()
    assert row['ID'] == '750XX0000000001'
    assert row['CONTENTURL'] == "jobs/it's/a\\path"
    # CAST(... AS TIMESTAMP_NTZ) really produced a timestamp, not a string.
    assert (row['CREATEDDATE'].year, row['CREATEDDATE'].hour) == (2026, 12)


def test_per_record_results_round_trip_through_spark(spark):
    from lht.salesforce import results_bapi

    recorded = DatabricksWarehouse(_Recording())
    # Identity columns need Delta, so create these two without the surrogate key.
    for table, columns in (('SUCCESS', SUCCESS_COLUMNS), ('FAILURE', FAILURE_COLUMNS)):
        DatabricksWarehouse(spark).create_table(
            f'lht_test.R_{table}', tuple((c, t) for c, t in columns if t != 'autoincrement')
        )

    results_bapi.insert_success_records(recorded, '750XX1', [
        {'sf__Id': '001XX1', 'sf__Created': 'true', 'Ext__c': "O'Brien"},
    ], match_field='Ext__c')
    results_bapi.insert_failure_records(recorded, '750XX1', [
        {'sf__Id': '', 'sf__Error': "REQUIRED_FIELD_MISSING: can't be blank", 'Ext__c': 'K3'},
    ], match_field='Ext__c')

    # insert_* target a fixed LOGS schema; point them at the test tables.
    _run(spark, [s.replace('LOGS.SUCCESS', 'lht_test.R_SUCCESS')
                  .replace('LOGS.FAILURE', 'lht_test.R_FAILURE')
                 for s in recorded.session.statements])

    success = spark.sql('SELECT * FROM lht_test.R_SUCCESS').collect()[0].asDict()
    # The apostrophe survives. With `''` escaping Spark returns "OBrien".
    assert success['MATCH_ID'] == "O'Brien"
    assert success['CREATED'] is True
    # Salesforce's successfulResults has no sf__Success column; a row in it is a
    # success, and used to land as NULL.
    assert success['SUCCESS'] is True
    assert success['CREATED_AT'] is not None

    failure = spark.sql('SELECT * FROM lht_test.R_FAILURE').collect()[0].asDict()
    assert failure['SF_ERROR'] == "REQUIRED_FIELD_MISSING: can't be blank"
    assert failure['SF_ID'] is None          # a failed insert has no Salesforce Id


def test_a_zero_counter_lands_as_zero(spark):
    from lht.salesforce import results_bapi

    recorded = DatabricksWarehouse(_Recording())
    DatabricksWarehouse(spark).create_table('lht_test.J_INFO', JOB_INFO_COLUMNS)
    results_bapi.insert_job_info(recorded, {
        'operation': 'upsert', 'object': 'Account', 'state': 'JobComplete',
        'createdDate': '2026-01-01T12:00:00.000+0000',
        'numberRecordsProcessed': 0, 'numberRecordsFailed': 3,
    }, '750XX2')
    _run(spark, [s.replace('LOGS.JOB_INFO', 'lht_test.J_INFO')
                 for s in recorded.session.statements])

    row = spark.sql("SELECT * FROM lht_test.J_INFO WHERE ID = '750XX2'").collect()[0].asDict()
    assert row['NUMBER_RECORDS_PROCESSED'] == 0      # not NULL
    assert row['NUMBER_RECORDS_FAILED'] == 3
    assert row['RETRY_COUNT'] is None                # genuinely absent stays NULL


@pytest.mark.parametrize('value', [
    "O'Brien",
    "it's a 'quoted' thing",
    'C:\\Users\\path',
    'ends with a backslash\\',
    "mixed \\ and ' together",
    "x'; DROP TABLE lht_test.RETL_HISTORY; --",
    'plain text',
    'unicode: café – ümlaut',
])
def test_any_value_survives_a_round_trip_unchanged(spark, recorded, value):
    """Whatever a Salesforce field holds must come back out of Spark identical."""
    rendered = recorded.literal(value)
    assert spark.sql(f'SELECT {rendered} AS v').collect()[0]['v'] == value


def test_a_spark_session_is_recognised_without_being_wrapped(spark):
    from lht.warehouse import from_session

    warehouse = from_session(spark)
    assert warehouse.name == 'databricks'
    assert warehouse.rows('SELECT 1 AS n, NULL AS empty') == [{'n': 1, 'empty': None}]


def test_a_running_session_is_found_from_another_thread(spark):
    """
    connect() must find the session even off the thread that created it.

    A notebook cell is not guaranteed to run on that thread, and
    SparkSession.getActiveSession() is thread-local: it answers None there.
    Relying on it alone sent connect() off to start a Databricks Connect
    session instead, which fails on a cluster with
    "No Spark session is running". Verified against PySpark 4.0.
    """
    import threading

    from lht.warehouse.databricks import _active_spark_session, connect

    from pyspark.sql import SparkSession
    assert SparkSession.getActiveSession() is not None, 'precondition: this thread has it'

    found = {}

    def off_thread():
        found['thread_local'] = SparkSession.getActiveSession()
        found['lht'] = _active_spark_session()
        found['warehouse'] = connect()

    thread = threading.Thread(target=off_thread)
    thread.start()
    thread.join()

    assert found['thread_local'] is None, 'precondition: thread-local lookup misses it'
    assert found['lht'] is not None, 'lht must still find the running session'
    assert found['warehouse'].name == 'databricks'
    assert found['warehouse'].rows('SELECT 1 AS n') == [{'n': 1}]


def test_job_history_lands_in_a_schema_that_did_not_exist(spark):
    """
    The bug: RETL_HISTORY went to a schema nobody had created, so the table
    could not be made, the failure was swallowed as a warning, and the job
    history stayed empty. With the schema created first, the same call works
    against a fresh database -- which is what a first run on a new catalog is.
    """
    from lht.util import log_retl

    schema = 'lht_never_created_before'
    spark.sql(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
    assert not spark.catalog.databaseExists(schema), 'precondition: the schema is absent'

    recorded = DatabricksWarehouse(_Recording())
    log_retl.job(recorded, {
        'id': '750XX0000000099',
        'operation': 'upsert',
        'object': 'Account',
        'createdDate': '2026-01-01T12:00:00.000+0000',
    }, schema=schema)
    _run(spark, recorded.session.statements)

    rows = spark.sql(f'SELECT ID, OPERATION FROM {schema}.RETL_HISTORY').collect()
    assert [(r['ID'], r['OPERATION']) for r in rows] == [('750XX0000000099', 'upsert')]


def test_logging_into_a_catalog_that_does_not_exist_reports_failure(spark):
    """
    The real engine's refusal, end to end: nothing can be saved, and the result
    must say so in one short message. It used to say success=True, because every
    step swallows its exception so that logging can never fail a load.
    """
    from unittest import mock

    from lht.salesforce import results_bapi

    with mock.patch.object(results_bapi, 'get_job_info', return_value={'state': 'JobComplete'}), \
         mock.patch.object(results_bapi, 'get_successful_results',
                           return_value=[{'sf__Id': '001XX1', 'sf__Created': 'true', 'Ext__c': 'K1'}]), \
         mock.patch.object(results_bapi, 'get_failed_results', return_value=[]):
        result = results_bapi.process_bulk_api_results(
            spark, {'access_token': 't', 'instance_url': 'https://example.my.salesforce.com'},
            '750XX0000000099', match_field='Ext__c', schema='no_such_catalog.lht_logs',
        )

    assert result['success'] is False
    assert 'no_such_catalog' in result['error']
    assert 'JVM stacktrace' not in result['error']
    assert len(result['error']) < 1500, 'one readable message, not a stack trace'
