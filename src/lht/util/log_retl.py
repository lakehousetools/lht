import json
import logging
import requests
from . import csv
from lht.util.http import DEFAULT_TIMEOUT
from lht.util.sql import identifier
from lht.warehouse import from_session
from lht.warehouse.base import RETL_HISTORY_COLUMNS

logger = logging.getLogger(__name__)


def job(session, json_data, schema='LOGS'):
    """
    Record one Bulk API ingest job in <schema>.RETL_HISTORY.

    Without this row, the per-record rows in RETL_RESULTS/RETL_FAILURES have no
    parent to join to and the audit trail is unusable.

    The table is created on first use, as LOGS.JOB_INFO is. Before that the insert
    failed wherever nobody had created it by hand, and because the caller swallows
    logging errors, the job history silently stayed empty. The schema is created
    on first use too: without that, a run against a catalog or database that has
    no such schema logged only a warning and kept no history.

    Args:
        session: A Snowpark session, a Spark session, or an
            :class:`lht.warehouse.Warehouse`. The column types come from
            whichever backend that is.
        json_data: The Bulk API's job-creation response.
        schema: Schema holding the log tables. An unqualified name resolves
            against the session's current database or catalog, so qualify it on
            Unity Catalog (``main.lht_logs``).
    """
    if not isinstance(json_data, dict) or not json_data.get('id'):
        logger.warning(f"Skipping job log; no job id in response: {json_data}")
        return None

    warehouse = from_session(session)
    table = f"{schema}.RETL_HISTORY"
    try:
        warehouse.create_schema(schema)
    except ValueError:
        raise  # an unusable name; creating the table would fail the same way
    except Exception as e:
        # A role that can write the schema's tables may still lack CREATE SCHEMA,
        # and the schema usually exists already. Carry on to the table, which is
        # the step that has to succeed.
        logger.debug(f"Could not create schema {schema} ({e}); assuming it exists.")
    warehouse.create_table(table, RETL_HISTORY_COLUMNS)
    warehouse.insert_rows(table, [column for column, _ in RETL_HISTORY_COLUMNS], [(
        warehouse.literal(json_data.get('id')),
        warehouse.literal(json_data.get('operation')),
        warehouse.literal(json_data.get('object')),
        warehouse.literal(json_data.get('createdById')),
        warehouse.timestamp_literal(json_data.get('createdDate')),
        warehouse.literal(json_data.get('externalIdFieldName')),
        warehouse.literal(json_data.get('contentUrl')),
    )])
    return None

def successful_results(access_info, job_id, match_field=None):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/successfulResults/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    results = csv.success_upserts(csv.bulk_csv_text(response), job_id, match_field=match_field)

    return results

def failed_results(access_info, job_id, match_field=None):
    access_token = access_info['access_token']
    url = access_info['instance_url']+f"/services/data/v62.0/jobs/ingest/{job_id}/failedResults/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    results = csv.fail_upserts(csv.bulk_csv_text(response), job_id, match_field=match_field)

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

    Needs a Snowpark session specifically, for write_pandas. The backend-neutral
    path to the same per-record outcomes is
    `lht.salesforce.results_bapi.process_bulk_api_results`, which is what the CLI's
    `--log-results` calls.
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
    prefix = identifier("{}.{}".format(database, schema) if database else schema)
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