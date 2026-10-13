"""
Reverse ETL on Databricks: the same query and the same payload as on Snowflake,
with the log tables written in Delta SQL.

The point of these is the equivalence. A notebook is meant to be able to hand
`spark` to the same retl call a Snowflake script passes a Snowpark session to,
and get the same bytes sent to Salesforce.
"""

import logging
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

    schema, create, insert = session.writes
    # The schema first: without it, a catalog that has no such schema logged only
    # a warning and the job history silently stayed empty.
    assert schema == 'CREATE SCHEMA IF NOT EXISTS main.lht_logs'
    assert create.startswith('CREATE TABLE IF NOT EXISTS main.lht_logs.RETL_HISTORY')
    assert 'VARCHAR' not in create
    assert 'ID STRING' in create
    assert insert.startswith('INSERT INTO main.lht_logs.RETL_HISTORY')
    assert "'750XX0000000001'" in insert
    assert "CAST('2026-01-01 12:00:00.000' AS TIMESTAMP_NTZ)" in insert


def test_job_history_still_uses_snowflake_sql_on_snowflake():
    session = _SnowparkSession()
    log_retl.job(SnowflakeWarehouse(session), JOB_RESPONSE)

    schema, create, insert = session.writes
    assert schema == 'CREATE SCHEMA IF NOT EXISTS LOGS'
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


def test_hyphenated_keys_work_for_a_key_vault_backed_scope():
    # Azure Key Vault secret names cannot contain an underscore, and a Key Vault-backed
    # scope serves the vault's names as they are.
    from lht.warehouse import databricks as dbx

    values = {'client-id': 'cid', 'client-secret': 'shhh', 'my-domain': 'example'}
    with _with_dbutils(values), \
         mock.patch('lht.user.salesforce_auth.get_salesforce_access_info_from_credentials',
                    return_value=ACCESS_INFO) as authenticate:
        dbx.salesforce_access_info(scope='kv')

    assert authenticate.call_args[0][0] == {
        'client_id': 'cid', 'client_key': 'shhh', 'my_domain': 'example',
    }


def test_hyphenated_jwt_keys_and_a_scope_that_cannot_be_listed():
    from lht.warehouse import databricks as dbx

    class _OnlyGet(_Secrets):
        def get(self, scope, key):
            if key not in self.values:
                raise KeyError(key)
            return self.values[key]

    secrets = _OnlyGet({'auth-flow': 'jwt_bearer', 'client-id': 'cid', 'username': 'u@example.com',
                        'private-key-pem': 'PEM'}, can_list=False)
    with mock.patch.object(dbx, '_dbutils', return_value=mock.Mock(secrets=secrets)), \
         mock.patch('lht.user.salesforce_auth.get_salesforce_access_info_from_credentials',
                    return_value=ACCESS_INFO) as authenticate:
        dbx.salesforce_access_info(scope='kv')

    assert authenticate.call_args[0][0] == {
        'auth_flow': 'jwt_bearer', 'client_id': 'cid', 'username': 'u@example.com',
        'private_key_pem': 'PEM',
    }


def test_the_underscore_spelling_wins_when_both_exist():
    from lht.warehouse import databricks as dbx

    values = {'client_id': 'underscore', 'client-id': 'hyphen', 'client_key': 'k', 'my_domain': 'd'}
    with _with_dbutils(values), \
         mock.patch('lht.user.salesforce_auth.get_salesforce_access_info_from_credentials',
                    return_value=ACCESS_INFO) as authenticate:
        dbx.salesforce_access_info(scope='salesforce')
    assert authenticate.call_args[0][0]['client_id'] == 'underscore'


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


# --- where the log tables go -------------------------------------------

def test_result_logging_honours_a_qualified_schema():
    # The default is a bare 'LOGS', which on Unity Catalog resolves against
    # whatever catalog the session happens to point at -- so a caller has to be
    # able to name the catalog outright.
    session = _SparkSession()
    _process_results_in(session, 'main.lht_logs', successes=[
        {'sf__Id': '001XX1', 'sf__Created': 'true', 'sf__Success': 'true', 'Ext__c': 'K1'},
    ], failures=[{'sf__Id': '', 'sf__Error': 'BAD', 'Ext__c': 'K2'}])

    sql = '\n'.join(session.statements)
    assert 'CREATE SCHEMA IF NOT EXISTS main.lht_logs' in sql
    for table in ('JOB_INFO', 'SUCCESS', 'FAILURE'):
        assert f'CREATE TABLE IF NOT EXISTS main.lht_logs.{table}' in sql
        assert f'INSERT INTO main.lht_logs.{table}' in sql
    # Nothing should still be pointing at the unqualified default.
    assert 'LOGS.' not in sql.replace('lht_logs.', '')


def test_result_logging_still_defaults_to_the_unqualified_logs_schema():
    session = _SparkSession()
    _process_results(session, successes=[], failures=[])
    sql = '\n'.join(session.statements)
    assert 'CREATE SCHEMA IF NOT EXISTS LOGS' in sql
    assert 'CREATE TABLE IF NOT EXISTS LOGS.JOB_INFO' in sql


def _process_results_in(session, schema, successes, failures):
    with mock.patch.object(results_bapi, 'get_job_info',
                           return_value=dict(JOB_RESPONSE, state='JobComplete')), \
         mock.patch.object(results_bapi, 'get_successful_results', return_value=successes), \
         mock.patch.object(results_bapi, 'get_failed_results', return_value=failures):
        return results_bapi.process_bulk_api_results(session, ACCESS_INFO, JOB_RESPONSE['id'],
                                                     match_field='Ext__c', schema=schema)


def test_a_log_schema_that_could_inject_sql_is_reported_once_and_writes_nothing():
    # Each table step only warns, so without an up-front check a bad name would
    # produce four confusing warnings and no clear failure.
    session = _SparkSession()
    result = _process_results_in(session, 'main.logs; DROP TABLE x',
                                 successes=[], failures=[])

    assert result['success'] is False
    assert 'main.logs; DROP TABLE x' in result['error']
    assert session.statements == []


# --- where the job history goes -----------------------------------------

@pytest.mark.parametrize('operation,kw', [
    (retl.upsert, {'field': 'Ext__c'}),
    (retl.update, {}),
    (retl.insert, {}),
    (retl.delete, {}),
])
def test_every_operation_writes_job_history_to_the_given_schema(operation, kw):
    # RETL_HISTORY used to land in a bare LOGS whatever the caller wanted: the
    # four operations had no way to say where, and on Unity Catalog a bare name
    # resolves against whichever catalog the session happens to point at.
    session = _SparkSession()
    _run(operation, session, [_Row(Ext__c='K1', Id='001XX', Name='A')],
         log_schema='main.lht_logs', **kw)

    sql = '\n'.join(session.writes)
    assert 'CREATE SCHEMA IF NOT EXISTS main.lht_logs' in sql
    assert 'CREATE TABLE IF NOT EXISTS main.lht_logs.RETL_HISTORY' in sql
    assert 'INSERT INTO main.lht_logs.RETL_HISTORY' in sql
    assert 'LOGS' not in sql.replace('lht_logs', '')


@pytest.mark.parametrize('operation,kw', [
    (retl.upsert, {'field': 'Ext__c'}),
    (retl.update, {}),
    (retl.insert, {}),
    (retl.delete, {}),
])
def test_job_history_still_defaults_to_the_bare_logs_schema(operation, kw):
    session = _SparkSession()
    _run(operation, session, [_Row(Ext__c='K1', Id='001XX', Name='A')], **kw)
    assert 'INSERT INTO LOGS.RETL_HISTORY' in '\n'.join(session.writes)


def test_a_role_that_cannot_create_the_schema_still_gets_job_history():
    # CREATE SCHEMA needs a privilege that writing to the schema's tables does
    # not, and the schema usually exists already. Failing to create it must not
    # cost the history row.
    class _NoCreateSchema(_SparkSession):
        def sql(self, statement):
            if statement.startswith('CREATE SCHEMA'):
                raise PermissionError('no CREATE SCHEMA on this catalog')
            return super().sql(statement)

    session = _NoCreateSchema()
    log_retl.job(DatabricksWarehouse(session), JOB_RESPONSE, schema='main.lht_logs')

    assert any(s.startswith('CREATE TABLE IF NOT EXISTS main.lht_logs.RETL_HISTORY')
               for s in session.statements)
    assert any(s.startswith('INSERT INTO main.lht_logs.RETL_HISTORY')
               for s in session.statements)


def test_an_unusable_log_schema_never_fails_the_load():
    # Logging is best-effort: a typo in the schema must cost the history row,
    # not a load that already reached Salesforce.
    session = _SparkSession()
    sent, result = _run(retl.upsert, session, [_Row(Ext__c='K1')], field='Ext__c',
                        log_schema='main.logs; DROP TABLE x')

    assert result['successful_batches'] == 1
    assert sent
    assert not any('DROP TABLE' in s for s in session.statements)


# --- the SUCCESS column --------------------------------------------------

def _success_insert(session):
    return next(st for st in session.statements if st.startswith('INSERT INTO LOGS.SUCCESS'))


def test_a_row_from_successful_results_is_marked_a_success():
    # Salesforce's successfulResults CSV has no sf__Success column, so reading one
    # always gave NULL. These are the columns it really has.
    session = _SparkSession()
    _process_results(session, failures=[], successes=[
        {'sf__Id': '001XX1', 'sf__Created': 'true', 'Ext__c': 'K1'},
        {'sf__Id': '001XX2', 'sf__Created': 'false', 'Ext__c': 'K2'},
    ])
    insert = _success_insert(session)
    assert "'001XX1', TRUE, TRUE, NULL" in insert       # created
    assert "'001XX2', FALSE, TRUE, NULL" in insert      # updated: still a success


def test_an_explicit_sf_success_is_still_honoured():
    session = _SparkSession()
    _process_results(session, failures=[], successes=[
        {'sf__Id': '001XX1', 'sf__Created': 'true', 'sf__Success': 'false', 'Ext__c': 'K1'},
    ])
    assert "'001XX1', TRUE, FALSE, NULL" in _success_insert(session)


# --- saying so when the log could not be saved ---------------------------

# The message Databricks gives for a catalog that does not exist: useful lines,
# then a JVM stack trace.
_NO_CATALOG = (
    "[NO_SUCH_CATALOG_EXCEPTION] Catalog 'my_catalog' was not found. Please verify "
    "the catalog name and then retry the query or command again. SQLSTATE: 42704\n\n"
    "JVM stacktrace:\norg.apache.spark.sql.catalyst.analysis.NoSuchCatalogException\n"
    "\tat com.databricks.sql.managedcatalog.client.ManagedCatalogClientImpl.getCatalogProto(X.scala:741)"
)

_REAL_SUCCESSES = [{'sf__Id': '001XX1', 'sf__Created': 'true', 'Ext__c': 'K1'}]
_REAL_FAILURES = [{'sf__Id': '', 'sf__Error': 'REQUIRED_FIELD_MISSING', 'Ext__c': 'K2'}]


class _Refusing(_SparkSession):
    """Refuses the writes `refuses` picks out, the way Databricks words a refusal."""

    def __init__(self, refuses):
        super().__init__()
        self.refuses = refuses

    def sql(self, statement):
        if self.refuses(statement):
            raise RuntimeError(_NO_CATALOG)
        return super().sql(statement)


def _any_write(statement):
    return not statement.lstrip().upper().startswith(('SELECT', 'WITH'))


def test_logging_that_saved_nothing_no_longer_reports_success(caplog):
    # process_bulk_api_results used to return success=True here: every step swallows
    # its own exception so that logging can never fail a load, and nothing then
    # told the caller that nothing had been written.
    with caplog.at_level(logging.WARNING, logger='lht.salesforce.results_bapi'):
        result = _process_results(_Refusing(_any_write), _REAL_SUCCESSES, _REAL_FAILURES)

    assert result['success'] is False
    assert "Catalog 'my_catalog' was not found" in result['error']
    # The counts are still what Salesforce reported -- those were fetched fine.
    assert (result['success_count'], result['failure_count']) == (1, 1)


def test_the_error_names_each_thing_that_went_wrong_without_the_stack_trace(caplog):
    with caplog.at_level(logging.WARNING, logger='lht.salesforce.results_bapi'):
        result = _process_results(_Refusing(_any_write), _REAL_SUCCESSES, _REAL_FAILURES)

    for table in ('JOB_INFO', 'SUCCESS', 'FAILURE'):
        assert f'LOGS.{table}' in result['error'], table
    assert 'JVM stacktrace' not in result['error']
    assert 'com.databricks' not in result['error']
    # ...and not in the log either, where it buried the one useful line.
    assert 'JVM stacktrace' not in caplog.text
    assert 'com.databricks' not in caplog.text


def test_one_clear_error_line_summarises_a_failed_save(caplog):
    with caplog.at_level(logging.WARNING, logger='lht.salesforce.results_bapi'):
        _process_results(_Refusing(_any_write), _REAL_SUCCESSES, _REAL_FAILURES)

    summaries = [r for r in caplog.records if 'NOT fully saved' in r.getMessage()]
    assert len(summaries) == 1
    assert summaries[0].levelno == logging.ERROR
    assert "Catalog 'my_catalog' was not found" in summaries[0].getMessage()


def test_one_failing_insert_does_not_stop_the_others():
    session = _Refusing(lambda st: st.startswith('INSERT INTO LOGS.SUCCESS'))
    result = _process_results(session, _REAL_SUCCESSES, _REAL_FAILURES)

    assert result['success'] is False
    assert 'LOGS.SUCCESS' in result['error'] and 'LOGS.FAILURE' not in result['error']
    inserted = [st.split(' (')[0] for st in session.statements if st.startswith('INSERT')]
    assert 'INSERT INTO LOGS.JOB_INFO' in inserted
    assert 'INSERT INTO LOGS.FAILURE' in inserted


def test_a_role_that_cannot_create_tables_but_can_write_to_them_is_not_a_failure(caplog):
    # CREATE TABLE needs a privilege that inserting does not. If the tables already
    # exist and the writes land, the log was saved: that is not a failure, though
    # the refused CREATE is still worth a warning.
    session = _Refusing(lambda st: st.startswith(('CREATE TABLE', 'CREATE SCHEMA')))
    with caplog.at_level(logging.WARNING, logger='lht.salesforce.results_bapi'):
        result = _process_results(session, _REAL_SUCCESSES, _REAL_FAILURES)

    assert result['success'] is True
    assert 'error' not in result
    assert 'Could not create' in caplog.text


def test_logging_that_saved_everything_still_reports_success():
    result = _process_results(_SparkSession(), _REAL_SUCCESSES, _REAL_FAILURES)
    assert result['success'] is True
    assert 'error' not in result


def test_a_save_with_nothing_to_insert_is_not_a_failure():
    # No failures to record means no FAILURE insert, so a FAILURE table that cannot
    # be created has cost nothing.
    session = _Refusing(lambda st: 'FAILURE' in st)
    result = _process_results(session, _REAL_SUCCESSES, failures=[])
    assert result['success'] is True
