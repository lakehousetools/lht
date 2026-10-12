"""
Reverse ETL on Databricks: the same query and the same payload as on Snowflake,
with the log tables written in Delta SQL.

The point of these is the equivalence. A notebook is meant to be able to hand
`spark` to the same retl call a Snowflake script passes a Snowpark session to,
and get the same bytes sent to Salesforce.
"""

from unittest import mock

import pytest

from lht.salesforce import results_bapi, retl
from lht.util import log_retl
from lht.warehouse import DatabricksWarehouse, SnowflakeWarehouse
from lht.warehouse.databricks import connect, get_spark_session, on_databricks, secret


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows


class _Session:
    """A session that answers SELECTs with canned rows and records everything else."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.statements = []

    def sql(self, statement):
        self.statements.append(statement)
        if statement.lstrip().upper().startswith(('SELECT', 'WITH')):
            return _Result(self.rows)
        return _Result([])

    @property
    def writes(self):
        return [s for s in self.statements if not s.lstrip().upper().startswith(('SELECT', 'WITH'))]


class _SparkSession(_Session):
    pass


class _SnowparkSession(_Session):
    pass


_SparkSession.__module__ = 'pyspark.sql.connect.session'
_SnowparkSession.__module__ = 'snowflake.snowpark.session'


class _Row:
    def __init__(self, **kv):
        self._kv = kv

    def asDict(self):
        return dict(self._kv)


ACCESS_INFO = {'access_token': 't', 'instance_url': 'https://example.my.salesforce.com'}

JOB_RESPONSE = {
    'id': '750XX0000000001',
    'operation': 'upsert',
    'object': 'Account',
    'createdById': '005XX0000000001',
    'createdDate': '2026-01-01T12:00:00.000+0000',
    'externalIdFieldName': 'Ext__c',
    'contentUrl': 'services/data/v62.0/jobs/ingest/750XX0000000001/batches',
}


def _run(operation, session, rows, **kw):
    """Run one retl operation against `session`, capturing the CSV it sends."""
    sent = []
    posted = mock.Mock(status_code=200, json=mock.Mock(return_value=JOB_RESPONSE))
    session.rows = rows
    with mock.patch.object(retl.requests, 'post', return_value=posted), \
         mock.patch.object(retl.ingest, 'send_file', side_effect=lambda a, j, data: sent.append(data)), \
         mock.patch.object(retl.ingest, 'job_close', return_value={}), \
         mock.patch.object(retl.ingest, 'job_status',
                           return_value={'id': JOB_RESPONSE['id'], 'state': 'JobComplete'}):
        result = operation(session, ACCESS_INFO, 'Account', 'SELECT Ext__c, Name FROM main.crm.scores', **kw)
    return sent, result


# --- the payload is the same on both warehouses -------------------------

def test_upsert_from_spark_sends_the_same_csv_as_from_snowpark():
    rows = [_Row(Ext__c=f'K{i}', Name=f'n{i}', Rating=None) for i in range(5)]
    from_spark, spark_result = _run(retl.upsert, _SparkSession(), rows, field='Ext__c', batch_size=2)
    from_snowpark, snowpark_result = _run(retl.upsert, _SnowparkSession(), rows, field='Ext__c', batch_size=2)

    assert from_spark == from_snowpark
    assert from_spark[0].strip().splitlines()[0] == 'Ext__c,Name,Rating'
    assert spark_result['total_records'] == snowpark_result['total_records'] == 5
    assert spark_result['successful_batches'] == 3


def test_upsert_reads_the_query_once_on_databricks_too():
    # Re-reading per batch without an ORDER BY is what sent rows twice or never.
    session = _SparkSession()
    rows = [_Row(Ext__c=f'K{i}') for i in range(6)]
    sent, _ = _run(retl.upsert, session, rows, field='Ext__c', batch_size=2)
    assert len([s for s in session.statements if s.startswith('SELECT')]) == 1
    keys = [line for payload in sent for line in payload.strip().splitlines()[1:]]
    assert sorted(keys) == sorted(f'K{i}' for i in range(6))


def test_clear_nulls_still_means_na_on_databricks():
    rows = [_Row(Ext__c='K1', Rating=None)]
    sent, _ = _run(retl.upsert, _SparkSession(), rows, field='Ext__c', clear_nulls=True)
    assert sent[0].strip().splitlines()[1] == 'K1,#N/A'


@pytest.mark.parametrize('operation,kw', [
    (retl.update, {}),
    (retl.insert, {}),
    (retl.delete, {}),
])
def test_every_operation_runs_against_a_spark_session(operation, kw):
    sent, job_info = _run(operation, _SparkSession(), [_Row(Id='001XX', Name='A')], **kw)
    assert sent[0].strip().splitlines() == ['Id,Name', '001XX,A']
    assert job_info['id'] == JOB_RESPONSE['id']


def test_a_null_on_insert_is_an_empty_cell_not_na():
    # An insert sets every field it sends; there is no old value to clear.
    sent, _ = _run(retl.insert, _SparkSession(), [_Row(Name='A', Rating=None)])
    assert sent[0].strip().splitlines()[1] == 'A,'


# --- job history --------------------------------------------------------

def test_job_history_is_written_in_delta_sql_on_databricks():
    session = _SparkSession()
    log_retl.job(DatabricksWarehouse(session), JOB_RESPONSE, schema='main.lht_logs')

    create, insert = session.writes
    assert create.startswith('CREATE TABLE IF NOT EXISTS main.lht_logs.RETL_HISTORY')
    assert 'VARCHAR' not in create
    assert 'ID STRING' in create
    assert insert.startswith('INSERT INTO main.lht_logs.RETL_HISTORY')
    assert "'750XX0000000001'" in insert
    assert "CAST('2026-01-01 12:00:00.000' AS TIMESTAMP_NTZ)" in insert


def test_job_history_still_uses_snowflake_sql_on_snowflake():
    session = _SnowparkSession()
    log_retl.job(SnowflakeWarehouse(session), JOB_RESPONSE)

    create, insert = session.writes
    assert 'ID VARCHAR,' in create
    assert 'CREATEDDATE TIMESTAMP_NTZ' in create
    assert "TO_TIMESTAMP_NTZ(TO_TIMESTAMP_TZ('2026-01-01 12:00:00.000'))" in insert


def test_a_response_without_a_job_id_is_skipped_rather_than_logged():
    session = _SparkSession()
    log_retl.job(DatabricksWarehouse(session), {'errors': ['nope']})
    assert session.statements == []


def test_a_logging_failure_never_fails_the_ingest():
    # Result rows are useless without their history row, but a load that already
    # reached Salesforce must not be reported as failed because logging broke.
    class _Broken(_SparkSession):
        """Answers the source query, but cannot write the log tables."""

        def sql(self, statement):
            if statement.lstrip().upper().startswith('SELECT'):
                return super().sql(statement)
            raise RuntimeError('LOGS schema does not exist')

    sent, result = _run(retl.upsert, _Broken(), [_Row(Ext__c='K1')], field='Ext__c')
    assert result['successful_batches'] == 1
    assert sent


# --- per-record results -------------------------------------------------

def _process_results(session, successes, failures, job_info=None):
    with mock.patch.object(results_bapi, 'get_job_info',
                           return_value=job_info if job_info is not None else dict(JOB_RESPONSE, state='JobComplete')), \
         mock.patch.object(results_bapi, 'get_successful_results', return_value=successes), \
         mock.patch.object(results_bapi, 'get_failed_results', return_value=failures):
        return results_bapi.process_bulk_api_results(session, ACCESS_INFO, JOB_RESPONSE['id'],
                                                     match_field='Ext__c')


def test_result_logging_creates_delta_tables_and_writes_every_row():
    session = _SparkSession()
    summary = _process_results(
        session,
        successes=[{'sf__Id': '001XX1', 'sf__Created': 'true', 'sf__Success': 'true', 'Ext__c': 'K1'}],
        failures=[{'sf__Id': '', 'sf__Error': "REQUIRED_FIELD_MISSING: can't be blank", 'Ext__c': 'K2'}],
    )

    assert summary['success'] is True
    assert (summary['success_count'], summary['failure_count']) == (1, 1)

    sql = '\n'.join(session.statements)
    assert 'CREATE SCHEMA IF NOT EXISTS LOGS' in sql
    for table in ('LOGS.JOB_INFO', 'LOGS.SUCCESS', 'LOGS.FAILURE'):
        assert f'CREATE TABLE IF NOT EXISTS {table}' in sql
    assert 'VARCHAR' not in sql
    assert 'INSERT INTO LOGS.SUCCESS' in sql and "'001XX1'" in sql
    assert 'INSERT INTO LOGS.FAILURE' in sql
    # An apostrophe in a Salesforce error must survive. Spark concatenates
    # adjacent string literals, so the SQL standard's doubled quote would drop
    # it silently; Spark needs a backslash.
    assert r"REQUIRED_FIELD_MISSING: can\'t be blank" in sql
    # CREATED_AT is supplied per row, since Delta has no column DEFAULT here.
    assert sql.count('CURRENT_TIMESTAMP()') >= 3


def test_a_zero_counter_is_logged_as_zero_not_null():
    # `or 'NULL'` treated a genuine 0 as missing, so a job that processed
    # nothing was indistinguishable from one lht could not read.
    session = _SparkSession()
    _process_results(session, successes=[], failures=[],
                     job_info=dict(JOB_RESPONSE, state='JobComplete',
                                   numberRecordsProcessed=0, numberRecordsFailed=0))
    insert = next(s for s in session.statements if s.startswith('INSERT INTO LOGS.JOB_INFO'))
    assert ', 0, 0,' in insert


def test_an_unreadable_job_still_gets_a_row_to_hang_its_results_on():
    session = _SparkSession()
    _process_results(session, successes=[], failures=[],
                     job_info={'error': True, 'error_code': '404', 'error_message': 'Not Found',
                               'state': 'Failed'})
    insert = next(s for s in session.statements if s.startswith('INSERT INTO LOGS.JOB_INFO'))
    assert "'750XX0000000001'" in insert and "'Failed'" in insert and "'Not Found'" in insert


# --- getting a session --------------------------------------------------

def test_connect_wraps_a_session_it_is_given():
    session = _SparkSession()
    warehouse = connect(session)
    assert isinstance(warehouse, DatabricksWarehouse)
    assert warehouse.session is session


def test_connect_off_platform_without_databricks_connect_says_how_to_install_it():
    # No Spark running and no Databricks Connect: the message has to name both
    # the notebook case and the install, since this is the first thing a new
    # user hits locally.
    with pytest.raises(ImportError, match='lht\\[databricks\\]'):
        get_spark_session()


def test_reading_a_secret_off_platform_fails_with_a_usable_message():
    with pytest.raises(RuntimeError, match='dbutils'):
        secret('salesforce', 'client_id')


def test_on_databricks_is_false_in_this_process(monkeypatch):
    monkeypatch.delenv('DATABRICKS_RUNTIME_VERSION', raising=False)
    assert on_databricks() is False
    monkeypatch.setenv('DATABRICKS_RUNTIME_VERSION', '15.4')
    assert on_databricks() is True


# --- merge --------------------------------------------------------------

def test_merge_reads_its_pairs_from_a_spark_session():
    # The merge happens in Salesforce over SOAP, so Databricks only has to
    # answer the query -- which makes merge work there for free.
    from lht.salesforce import merge as merge_mod

    session = _SparkSession([_Row(MASTERID='001AA0000000001AAA', LOSERID='001AA0000000002AAA')])
    summary = merge_mod.merge(session, ACCESS_INFO, 'Account',
                              'SELECT MasterId, LoserId FROM main.crm.dupes', dry_run=True)
    assert summary == {'requests': 1, 'records_to_merge': 1, 'merged': 0, 'failed': [], 'results': []}


# --- the import graph ---------------------------------------------------

def test_the_reverse_etl_path_imports_without_snowpark_installed():
    """
    Databricks compute must not need the Snowflake client.

    This runs in a subprocess with `snowflake.*` made unimportable, because the
    guard is about import time: a top-level `from snowflake.snowpark import ...`
    anywhere on the reverse-ETL path would make Snowpark a hard requirement of
    running lht on Databricks, and installing it there puts its pandas and
    pyarrow pins over the ones the runtime ships.
    """
    import subprocess
    import sys

    program = '''
import sys
from importlib.abc import MetaPathFinder


class Blocked(MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] == 'snowflake':
            raise ImportError('blocked: ' + name)
        return None


sys.meta_path.insert(0, Blocked())

import lht
from lht import warehouse
from lht.salesforce import retl, results_bapi, merge
from lht.util import log_retl
from lht.warehouse.databricks import connect
from lht.user.salesforce_auth import get_salesforce_access_info_from_credentials
from lht.user.connections import register_connection

# The bare `snowflake` namespace package is registered by snowpark's own .pth
# at interpreter startup wherever it is installed, so only a real submodule
# import means lht pulled the client in.
imported = [m for m in sys.modules if m.startswith('snowflake.')]
assert not imported, 'lht imported the Snowflake client: ' + ', '.join(imported)
print('ok')
'''
    result = subprocess.run([sys.executable, '-c', program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith('ok')


def test_connecting_to_snowflake_without_snowpark_names_the_extra_to_install():
    import subprocess
    import sys

    program = '''
import sys
from importlib.abc import MetaPathFinder


class Blocked(MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] == 'snowflake':
            raise ImportError('blocked: ' + name)
        return None


sys.meta_path.insert(0, Blocked())

from lht.user.auth import create_session

try:
    create_session({'account': 'a', 'user': 'u', 'role': 'r', 'warehouse': 'w',
                    'private_key_file': '/nonexistent'})
except ImportError as e:
    print(e)
'''
    result = subprocess.run([sys.executable, '-c', program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'lht[snowflake]' in result.stdout


# --- credentials either side of the platform boundary -------------------

class _Secrets:
    """Stands in for dbutils.secrets."""

    def __init__(self, values, can_list=True):
        self.values = values
        self.can_list = can_list

    def list(self, scope):
        if not self.can_list:
            raise PermissionError('no list grant')
        return [mock.Mock(key=key) for key in self.values]

    def get(self, scope, key):
        return self.values[key]


def _with_dbutils(values, **kw):
    from lht.warehouse import databricks as dbx

    return mock.patch.object(dbx, '_dbutils',
                             return_value=mock.Mock(secrets=_Secrets(values, **kw)))


def test_credentials_come_from_the_secret_scope_on_databricks():
    from lht.warehouse import databricks as dbx

    values = {'client_id': 'cid', 'client_secret': 'shhh', 'my_domain': 'example'}
    with _with_dbutils(values), \
         mock.patch('lht.user.salesforce_auth.get_salesforce_access_info_from_credentials',
                    return_value=ACCESS_INFO) as authenticate:
        assert dbx.salesforce_access_info(scope='salesforce') == ACCESS_INFO

    # client_secret is what Salesforce's own UI calls it; lht's own key is client_key.
    assert authenticate.call_args[0][0] == {
        'client_id': 'cid', 'client_key': 'shhh', 'my_domain': 'example',
    }


def test_a_scope_without_list_permission_is_still_read_key_by_key():
    from lht.warehouse import databricks as dbx

    class _OnlyGet(_Secrets):
        def get(self, scope, key):
            if key not in self.values:
                raise KeyError(key)
            return self.values[key]

    secrets = _OnlyGet({'client_id': 'cid', 'client_key': 'shhh', 'my_domain': 'example'},
                       can_list=False)
    with mock.patch.object(dbx, '_dbutils', return_value=mock.Mock(secrets=secrets)), \
         mock.patch('lht.user.salesforce_auth.get_salesforce_access_info_from_credentials',
                    return_value=ACCESS_INFO) as authenticate:
        dbx.salesforce_access_info(scope='salesforce')
    assert authenticate.call_args[0][0]['client_id'] == 'cid'


def test_sandbox_arrives_from_a_scope_as_a_boolean():
    from lht.warehouse import databricks as dbx

    values = {'client_id': 'cid', 'client_key': 'k', 'my_domain': 'example', 'sandbox': 'true'}
    with _with_dbutils(values), \
         mock.patch('lht.user.salesforce_auth.get_salesforce_access_info_from_credentials',
                    return_value=ACCESS_INFO) as authenticate:
        dbx.salesforce_access_info(scope='salesforce')
    assert authenticate.call_args[0][0]['sandbox'] is True


def test_an_empty_scope_says_how_to_populate_it():
    from lht.warehouse import databricks as dbx

    with _with_dbutils({}), pytest.raises(ValueError, match='put-secret'):
        dbx.salesforce_access_info(scope='salesforce')


def test_off_databricks_the_same_call_falls_back_to_a_saved_connection():
    # This is what lets one notebook file run unchanged on a laptop.
    from lht.warehouse import databricks as dbx

    with mock.patch.object(dbx, '_dbutils', return_value=None), \
         mock.patch('lht.user.salesforce_auth.get_salesforce_access_info',
                    return_value=ACCESS_INFO) as from_file:
        assert dbx.salesforce_access_info(scope='salesforce', connection_name='dev') == ACCESS_INFO
    from_file.assert_called_once_with('dev')
