import requests
import json
import csv as csv_module
import io
import logging
from lht.util.csv import bulk_csv_text
from lht.util.http import DEFAULT_TIMEOUT
from lht.util.sql import identifier
from lht.warehouse import Warehouse, from_session
from lht.warehouse.base import (
    FAILURE_COLUMNS,
    JOB_INFO_COLUMNS,
    SUCCESS_COLUMNS,
)

logger = logging.getLogger(__name__)

DEFAULT_LOG_SCHEMA = 'LOGS'


def create_logs_schema_if_not_exists(warehouse: Warehouse, schema: str = DEFAULT_LOG_SCHEMA):
    """Create the log schema if it doesn't exist."""
    try:
        warehouse.create_schema(schema)
        logger.info(f"✅ {schema} schema created/verified successfully")
    except Exception as e:
        logger.warning(f"⚠️ Warning: Could not create {schema} schema: {e}")

def create_job_info_table(warehouse: Warehouse, schema: str = DEFAULT_LOG_SCHEMA):
    """Create the job_info table based on Salesforce API documentation."""
    try:
        warehouse.create_table(f'{schema}.JOB_INFO', JOB_INFO_COLUMNS)
        logger.info("✅ JOB_INFO table created/verified successfully")
    except Exception as e:
        logger.warning(f"⚠️ Warning: Could not create JOB_INFO table: {e}")

def create_success_table(warehouse: Warehouse, schema: str = DEFAULT_LOG_SCHEMA):
    """Create the success table based on Salesforce API documentation."""
    try:
        warehouse.create_table(f'{schema}.SUCCESS', SUCCESS_COLUMNS)
        _add_match_columns(warehouse, f'{schema}.SUCCESS')
        logger.info("✅ SUCCESS table created/verified successfully")
    except Exception as e:
        logger.warning(f"⚠️ Warning: Could not create SUCCESS table: {e}")

def create_failure_table(warehouse: Warehouse, schema: str = DEFAULT_LOG_SCHEMA):
    """Create the failure table based on Salesforce API documentation."""
    try:
        warehouse.create_table(f'{schema}.FAILURE', FAILURE_COLUMNS)
        _add_match_columns(warehouse, f'{schema}.FAILURE')
        logger.info("✅ FAILURE table created/verified successfully")
    except Exception as e:
        logger.warning(f"⚠️ Warning: Could not create FAILURE table: {e}")

def _add_match_columns(warehouse: Warehouse, table: str):
    """Backfill MATCH_FIELD/MATCH_ID onto a log table created before they existed."""
    warehouse.add_columns_if_missing(
        table, (('MATCH_FIELD', 'str255'), ('MATCH_ID', 'text'))
    )

def get_job_info(access_info: dict, job_id: str) -> dict:
    """Retrieve job information from Salesforce Bulk API 2.0."""
    access_token = access_info['access_token']
    url = f"{access_info['instance_url']}/services/data/v62.0/jobs/ingest/{job_id}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        error_info = {
            'error': True,
            'error_code': getattr(e.response, 'status_code', 'UNKNOWN') if hasattr(e, 'response') else 'UNKNOWN',
            'error_message': str(e),
            'state': 'Failed'
        }
        logger.error(f"❌ Error retrieving job info: {error_info}")
        return error_info

def get_successful_results(access_info: dict, job_id: str) -> list:
    """Retrieve successful results from Salesforce Bulk API 2.0."""
    access_token = access_info['access_token']
    url = f"{access_info['instance_url']}/services/data/v62.0/jobs/ingest/{job_id}/successfulResults/"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        # Parse CSV response
        csv_content = bulk_csv_text(response)
        if not csv_content.strip():
            logger.info("ℹ️ No CSV content received for successful results")
            return []
            
        # Parse CSV and convert to list of dictionaries
        try:
            csv_reader = csv_module.DictReader(io.StringIO(csv_content))
            results = []
            for row in csv_reader:
                results.append(row)
            
            logger.info(f"✅ Successfully parsed {len(results)} successful records from CSV")
            return results
            
        except Exception as csv_error:
            logger.warning(f"⚠️ Warning: CSV parsing error for successful results: {csv_error}")
            logger.debug(f"📄 CSV content preview: {csv_content[:200]}...")
            return []
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error retrieving successful results: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Error parsing successful results CSV: {e}")
        return []

def get_failed_results(access_info: dict, job_id: str) -> list:
    """Retrieve failed results from Salesforce Bulk API 2.0."""
    access_token = access_info['access_token']
    url = f"{access_info['instance_url']}/services/data/v62.0/jobs/ingest/{job_id}/failedResults/"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'text/csv'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        # Parse CSV response
        csv_content = bulk_csv_text(response)
        if not csv_content.strip():
            logger.info("ℹ️ No CSV content received for failed results")
            return []
            
        # Parse CSV and convert to list of dictionaries
        try:
            csv_reader = csv_module.DictReader(io.StringIO(csv_content))
            results = []
            for row in csv_reader:
                results.append(row)
            
            logger.info(f"✅ Successfully parsed {len(results)} failed records from CSV")
            
            # 🔍 DEBUG: Show sample of failed results structure
            if results:
                logger.debug(f"📋 Failed results: {len(results)} records")
            
            return results
            
        except Exception as csv_error:
            logger.warning(f"⚠️ Warning: CSV parsing error for failed results: {csv_error}")
            logger.debug(f"📄 CSV content preview: {csv_content[:200]}...")
            return []
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error retrieving failed results: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Error parsing failed results CSV: {e}")
        return []

def insert_job_info(warehouse: Warehouse, job_data: dict, job_id: str,
                    schema: str = DEFAULT_LOG_SCHEMA):
    """
    Insert one job's metadata into the JOB_INFO table.

    A job that could not be read back from Salesforce still gets a row, carrying
    its error instead of its counters -- otherwise the SUCCESS/FAILURE rows for
    that job would have no parent to join to.
    """
    # Only the job id and CREATED_AT are written on the error path; every other
    # column stays NULL, which is what distinguishes an unreadable job from one
    # that genuinely processed nothing.
    if job_data.get('error'):
        fields = {
            'STATE': _sql_literal(warehouse, job_data.get('state', 'Failed')),
            'ERROR_CODE': _sql_literal(warehouse, job_data.get('error_code')),
            'ERROR_MESSAGE': _sql_literal(warehouse, job_data.get('error_message')),
        }
    else:
        renderers = {
            'literal': lambda value: _sql_literal(warehouse, value),
            'number': _sql_number,
            'timestamp': warehouse.timestamp_literal,
        }
        fields = {
            column: renderers[kind](job_data.get(api_field))
            for column, api_field, kind in _JOB_INFO_FIELDS
        }

    fields['ID'] = _sql_literal(warehouse, job_id)
    fields['CREATED_AT'] = warehouse.now()

    columns = tuple(column for column, _ in JOB_INFO_COLUMNS)
    try:
        warehouse.insert_rows(
            f'{schema}.JOB_INFO',
            columns,
            [tuple(fields.get(column, 'NULL') for column in columns)],
        )
        logger.info(f"✅ Job info inserted for job {job_id}")

    except Exception as e:
        logger.error(f"❌ Error inserting job info for job {job_id}: {e}")

# JOB_INFO column <- (Bulk API job field, how to render it). ID and CREATED_AT
# are set by insert_job_info itself and so are absent here.
_JOB_INFO_FIELDS = (
    ('OPERATION', 'operation', 'literal'),
    ('OBJECT', 'object', 'literal'),
    ('CREATED_BY_ID', 'createdById', 'literal'),
    ('CREATED_DATE', 'createdDate', 'timestamp'),
    ('SYSTEM_MODSTAMP', 'systemModstamp', 'timestamp'),
    ('STATE', 'state', 'literal'),
    ('JOB_TYPE', 'jobType', 'literal'),
    ('NUMBER_RECORDS_PROCESSED', 'numberRecordsProcessed', 'number'),
    ('NUMBER_RECORDS_FAILED', 'numberRecordsFailed', 'number'),
    ('RETRY_COUNT', 'retryCount', 'number'),
    ('TOTAL_PROCESSING_TIME', 'totalProcessingTime', 'number'),
    ('API_ACTIVE_PROCESSING_TIME', 'apiActiveProcessingTime', 'number'),
    ('AVERAGE_PER_SECOND', 'averagePerSecond', 'number'),
    ('AVERAGE_PER_BATCH', 'averagePerBatch', 'number'),
    ('NUMBER_RECORDS_TOTAL', 'numberRecordsTotal', 'number'),
    ('NUMBER_BATCHES_TOTAL', 'numberBatchesTotal', 'number'),
    ('NUMBER_BATCHES_IN_PROGRESS', 'numberBatchesInProgress', 'number'),
    ('NUMBER_BATCHES_COMPLETED', 'numberBatchesCompleted', 'number'),
    ('NUMBER_BATCHES_FAILED', 'numberBatchesFailed', 'number'),
    ('NUMBER_BATCHES_PENDING', 'numberBatchesPending', 'number'),
    ('BYTES_PROCESSED', 'bytesProcessed', 'number'),
    ('ERROR_CODE', 'errorCode', 'literal'),
    ('ERROR_MESSAGE', 'errorMessage', 'literal'),
)


def _sql_literal(warehouse, value):
    """
    Render a value as this warehouse's SQL string literal; empty means NULL.

    Goes through the warehouse rather than escaping here, because the backends
    disagree: Spark reads the SQL standard's doubled quote as two concatenated
    literals and drops the quote, so a Salesforce error mentioning O'Brien would
    be logged without its apostrophe.
    """
    if value is None or value == '':
        return 'NULL'
    return warehouse.literal(value)


def _sql_number(value):
    """Render a Bulk API counter as a SQL number, or NULL if it isn't one."""
    if value is None or value == '':
        return 'NULL'
    try:
        return str(int(value))
    except (TypeError, ValueError):
        logger.debug(f"Not a number, logging NULL instead: {value!r}")
        return 'NULL'


def _sql_boolean(value):
    """Render Salesforce's string booleans as SQL TRUE/FALSE/NULL."""
    raw = str(value).strip().lower()
    if raw in ('true', '1'):
        return 'TRUE'
    if raw in ('false', '0'):
        return 'FALSE'
    return 'NULL'


def _lookup(record: dict, field):
    """Read a result column case-insensitively, since Salesforce echoes the submitted casing."""
    if not field:
        return None
    if field in record:
        return record[field]
    target = str(field).strip().lower()
    for key, value in record.items():
        if str(key).strip().lower() == target:
            return value
    return None


def insert_success_records(warehouse: Warehouse, job_id: str, success_data: list,
                           match_field: str = None, schema: str = DEFAULT_LOG_SCHEMA):
    """
    Insert successful records into the SUCCESS table.

    `match_field` names the external ID column that was submitted; Salesforce echoes
    it back in the results, and storing it is what links a Salesforce ID to its source record.
    """
    if not success_data:
        logger.info("ℹ️ No successful records to insert")
        return

    columns = ('JOB_ID', 'SF_ID', 'CREATED', 'SUCCESS', 'ERRORS', 'MATCH_FIELD', 'MATCH_ID',
               'CREATED_AT')
    rows = []
    for record in success_data:
        errors = record.get('sf__Errors')
        match_value = _lookup(record, match_field)
        rows.append((
            _sql_literal(warehouse, job_id),
            _sql_literal(warehouse, record.get('sf__Id')),
            _sql_boolean(record.get('sf__Created')),
            _sql_boolean(record.get('sf__Success')),
            _sql_literal(warehouse, json.dumps(errors)) if errors else 'NULL',
            _sql_literal(warehouse, match_field) if match_value is not None else 'NULL',
            _sql_literal(warehouse, match_value),
            warehouse.now(),
        ))

    try:
        warehouse.insert_rows(f'{schema}.SUCCESS', columns, rows)
        logger.info(f"✅ Inserted {len(rows)} successful records for job {job_id}")

    except Exception as e:
        logger.error(f"❌ Error inserting success records: {e}")

def insert_failure_records(warehouse: Warehouse, job_id: str, failure_data: list,
                           match_field: str = None, schema: str = DEFAULT_LOG_SCHEMA):
    """
    Insert failed records into the FAILURE table.

    `match_field` names the external ID column that was submitted, so a failure can be
    traced back to the source record that caused it rather than only to a Salesforce ID
    (which is often blank on a failed insert).
    """
    if not failure_data:
        logger.info("ℹ️ No failed records to insert")
        return

    logger.info(f"📋 Starting to insert {len(failure_data)} failed records for job {job_id}")

    columns = ('JOB_ID', 'SF_ID', 'SF_ERROR', 'MATCH_FIELD', 'MATCH_ID', 'CREATED_AT')
    rows = []
    for record in failure_data:
        match_value = _lookup(record, match_field)
        rows.append((
            _sql_literal(warehouse, job_id),
            _sql_literal(warehouse, record.get('sf__Id')),
            _sql_literal(warehouse, record.get('sf__Error')),
            _sql_literal(warehouse, match_field) if match_value is not None else 'NULL',
            _sql_literal(warehouse, match_value),
            warehouse.now(),
        ))

    try:
        warehouse.insert_rows(f'{schema}.FAILURE', columns, rows)
        logger.info(f"✅ Inserted {len(rows)} failed records for job {job_id}")

    except Exception as e:
        logger.error(f"❌ Error inserting failure records: {e}")
        raise

def process_bulk_api_results(session, access_info: dict, job_id: str, match_field: str = None,
                             schema: str = DEFAULT_LOG_SCHEMA):
    """
    Main function to process Bulk API 2.0 job results and store them in the database.

    Args:
        session: A Snowpark session, a Spark session, or an
            :class:`lht.warehouse.Warehouse`. The log tables are created with
            whichever backend's column types that implies.
        access_info: Salesforce access credentials dictionary
        job_id: The Bulk API 2.0 job ID to process
        match_field: External ID column submitted with the job. Salesforce echoes it back
            in the results, so recording it links each outcome to its source record.
        schema: Schema holding JOB_INFO, SUCCESS and FAILURE, created on first use.
            Defaults to an unqualified ``LOGS``, which resolves against whatever
            database or catalog the session is pointed at. On Unity Catalog that
            is rarely what you want, so qualify it -- ``main.lht_logs`` -- rather
            than relying on the current catalog. Matches the `schema` argument
            `lht.util.log_retl.job` takes for RETL_HISTORY.
    """
    logger.info(f"🚀 Processing Bulk API 2.0 results for job: {job_id}")

    try:
        warehouse = from_session(session)
        # Checked once, before the per-table steps below, each of which only
        # warns: a name that cannot be used at all is a caller's mistake, and
        # should be reported as one failure rather than four warnings.
        identifier(schema)

        # Step 1: Create schema and tables if they don't exist
        logger.info(f"📋 Setting up {schema} schema and tables...")
        create_logs_schema_if_not_exists(warehouse, schema)
        create_job_info_table(warehouse, schema)
        create_success_table(warehouse, schema)
        create_failure_table(warehouse, schema)
        
        # Step 2: Retrieve job information
        logger.info(f"📊 Retrieving job information for job {job_id}...")
        job_info = get_job_info(access_info, job_id)
        
        # Step 3: Insert job information
        logger.info("💾 Storing job information...")
        insert_job_info(warehouse, job_info, job_id, schema=schema)
        
        # Step 4: Retrieve and store successful results
        logger.info("📈 Retrieving successful results...")
        success_results = get_successful_results(access_info, job_id)
        insert_success_records(warehouse, job_id, success_results, match_field=match_field,
                               schema=schema)

        # Step 5: Retrieve and store failed results
        logger.info("📉 Retrieving failed results...")
        failure_results = get_failed_results(access_info, job_id)
        logger.debug(f"📋 Failure results: {len(failure_results) if failure_results else 0} records")

        insert_failure_records(warehouse, job_id, failure_results, match_field=match_field,
                               schema=schema)
        
        # Step 6: Summary
        logger.info("✅ BULK API 2.0 RESULTS PROCESSING COMPLETED")
        logger.info(f"📊 Job ID: {job_id}")
        logger.info(f"📈 Successful Records: {len(success_results)}")
        logger.info(f"📉 Failed Records: {len(failure_results)}")
        logger.info(f"🗄️ Data stored in {schema} tables on {warehouse.name}")
        
        return {
            'job_id': job_id,
            'success_count': len(success_results),
            'failure_count': len(failure_results),
            'job_state': job_info.get('state', 'Unknown'),
            'success': True
        }
        
    except Exception as e:
        logger.error(f"❌ ERROR processing Bulk API 2.0 results: {e}")
        return {
            'job_id': job_id,
            'success_count': 0,
            'failure_count': 0,
            'job_state': 'Error',
            'success': False,
            'error': str(e)
        }

# Legacy function for backward compatibility
def successful_results(access_info, job_id):
    """Legacy function - now redirects to the new comprehensive processing."""
    logger.warning("⚠️ Warning: This function is deprecated. Use process_bulk_api_results() instead.")
    return get_successful_results(access_info, job_id)
