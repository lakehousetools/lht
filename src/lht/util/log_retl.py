import json
import logging
import requests
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col
from . import csv

logger = logging.getLogger(__name__)


def _literal(value):
    """Render a Python value as a SQL literal, escaping embedded single quotes."""
    if value is None:
        return 'NULL'
    return "'{}'".format(str(value).replace("'", "''"))


def _created_date(raw):
    """Convert Salesforce's ISO createdDate into a Snowflake-friendly timestamp string."""
    if not raw or len(raw) < 19:
        return None
    return raw[:10] + ' ' + raw[11:23]


def job(session, json_data, schema='LOGS'):
    """
    Record one Bulk API ingest job in <schema>.RETL_HISTORY.

    Without this row, the per-record rows in RETL_RESULTS/RETL_FAILURES have no
    parent to join to and the audit trail is unusable.
    """
    if not isinstance(json_data, dict) or not json_data.get('id'):
        logger.warning(f"Skipping job log; no job id in response: {json_data}")
        return None

    columns = (
        'id', 'operation', 'object', 'createdById',
        'createdDate', 'externalIdFieldName', 'contentUrl',
    )
    values = (
        _literal(json_data.get('id')),
        _literal(json_data.get('operation')),
        _literal(json_data.get('object')),
        _literal(json_data.get('createdById')),
        _literal(_created_date(json_data.get('createdDate'))),
        _literal(json_data.get('externalIdFieldName')),
        _literal(json_data.get('contentUrl')),
    )
    query = "INSERT INTO {}.RETL_HISTORY ({}) SELECT {}".format(
        schema, ', '.join(columns), ', '.join(values)
    )
    session.sql(query).collect()
    return None

def successful_results(access_info, job_id, match_field=None):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/successfulResults/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    response = requests.get(url, headers=headers)
    results = csv.success_upserts(response.text, job_id, match_field=match_field)

    return results

def failed_results(access_info, job_id, match_field=None):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/failedResults/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    response = requests.get(url, headers=headers)
    results = csv.fail_upserts(response.text, job_id, match_field=match_field)

    return results

def _align_to_table(session, df, table, schema):
    """
    Drop DataFrame columns the destination table doesn't have.

    Log tables predate MATCH_FIELD/MATCH_ID in some deployments, and write_pandas
    fails outright on an unknown column. Dropping and warning keeps logging working
    on an older schema instead of failing the run.
    """
    try:
        fields = session.table(f"{schema}.{table}").schema.fields
        existing = {f.name.upper().strip('"') for f in fields}
    except Exception as e:
        logger.warning(f"Could not read columns of {schema}.{table}: {e}")
        return df

    extras = [c for c in df.columns if c.upper() not in existing]
    if extras:
        logger.warning(
            f"{schema}.{table} has no column(s) {extras}; skipping them. "
            f"Add them to record which source record produced each row."
        )
        return df.drop(columns=extras)
    return df


def log_results(session, access_info, job_id, schema, match_field=None):
    """
    Load one job's per-record outcomes into <schema>.RETL_RESULTS and RETL_FAILURES.

    Pass `match_field` (the external ID column sent to Salesforce) to populate
    MATCH_FIELD/MATCH_ID, which is what ties a Salesforce ID back to its source record.
    """
    successes = successful_results(access_info, job_id, match_field=match_field)
    if len(successes) > 0:
        successes = _align_to_table(session, successes, 'RETL_RESULTS', schema)
        session.write_pandas(successes, 'RETL_RESULTS', schema=schema, quote_identifiers=False, auto_create_table=False, overwrite=False,use_logical_type=True)

    failures = failed_results(access_info, job_id, match_field=match_field)
    if len(failures) > 0:
        failures = _align_to_table(session, failures, 'RETL_FAILURES', schema)
        session.write_pandas(failures, 'RETL_FAILURES', schema=schema, quote_identifiers=False, auto_create_table=False, overwrite=False,use_logical_type=True)

    return None


def check_log(session, id, schema='LOGS'):
    """Return the number of already-logged result rows for a job, in the session's database."""
    database = session.get_current_database()
    if database:
        database = database.replace('"', '')
    query = history_query(id, database=database, schema=schema)
    results = session.sql(query).collect()

    return len(results)

def history_query(id, database=None, schema='LOGS'):
    """Build the dedupe lookup joining RETL_HISTORY to RETL_RESULTS for one job id."""
    prefix = "{}.{}".format(database, schema) if database else schema
    query = """with history as (
                select
                ID,
                OPERATION,
                OBJECT,
                EXTERNALIDFIELDNAME
                from {prefix}.RETL_HISTORY
                ),
                results as (
                Select
                HISTORY_ID
                from {prefix}.RETL_RESULTS
                )
                select
                h.id,
                r.history_id
                from history h
                join results r
                on r.history_id = h.id
                where h.id = '{id}'""".format(prefix=prefix, id=str(id).replace("'", "''"))

    return query