import csv
import json
import io
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def json_to_csv(json_data):
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    output = io.StringIO()
    
    writer = csv.writer(output)

    try:
        writer.writerow(json_data[0].keys())
    except:
        logger.warning("no data to process")
        return None
    for item in json_data:
        writer.writerow(item.values())

    csv_content = output.getvalue()
    output.close()
    
    return csv_content

def _column_index(header, *names, default=None):
    """
    Find a column's position in a Bulk API results header, matched case-insensitively.

    Returns `default` when the header is missing or none of `names` are present.
    """
    if not header:
        return default
    lowered = [str(h).strip().lower() for h in header]
    for name in names:
        if not name:
            continue
        try:
            return lowered.index(str(name).strip().lower())
        except ValueError:
            continue
    return default


def _value_at(row, index):
    """Read a positional value from a CSV row, tolerating short rows and missing indexes."""
    if index is None or index >= len(row):
        return None
    return row[index]


def success_upserts(data, job_id, match_field=None):
    """
    Parse a Bulk API 2.0 successfulResults CSV into rows for LOGS.RETL_RESULTS.

    Salesforce echoes every submitted column back after `sf__Id` and `sf__Created`,
    so passing `match_field` (the external ID column that was sent) records which
    source record produced each Salesforce ID.
    """
    csv_file = io.StringIO(data)
    csv_reader = csv.reader(csv_file)

    header = next(csv_reader, None)
    if header:
        logger.debug(f"Header: {header}")

    id_index = _column_index(header, 'sf__Id', default=0)
    created_index = _column_index(header, 'sf__Created', default=1)
    match_index = _column_index(header, match_field) if match_field else None
    if match_field and match_index is None:
        logger.warning(
            f"Match field '{match_field}' not found in results header; "
            "MATCH_FIELD/MATCH_ID will be empty."
        )

    records = []
    for row in csv_reader:
        records.append({
            'HISTORY_ID': job_id,
            'SF_ID': _value_at(row, id_index),
            'SF_CREATED': _value_at(row, created_index),
            'MATCH_FIELD': match_field if match_index is not None else None,
            'MATCH_ID': _value_at(row, match_index),
        })
    return pd.DataFrame(records)


def fail_upserts(data, job_id, match_field=None):
    """
    Parse a Bulk API 2.0 failedResults CSV into rows for LOGS.RETL_FAILURES.

    The failed-results CSV leads with `sf__Id` and `sf__Error` and then echoes the
    submitted columns, so `match_field` ties each failure back to its source record.
    """
    csv_file = io.StringIO(data)
    csv_reader = csv.reader(csv_file)

    header = next(csv_reader, None)
    if header:
        logger.debug(f"Header: {header}")

    id_index = _column_index(header, 'sf__Id', default=0)
    error_index = _column_index(header, 'sf__Error', default=1)
    match_index = _column_index(header, match_field) if match_field else None
    if match_field and match_index is None:
        logger.warning(
            f"Match field '{match_field}' not found in failure header; "
            "MATCH_FIELD/MATCH_ID will be empty."
        )

    records = []
    for row in csv_reader:
        records.append({
            'HISTORY_ID': job_id,
            'SF_ID': _value_at(row, id_index),
            'SF_CREATED': False,
            'SF_ERROR': _value_at(row, error_index),
            'HEADERS': header,
            'RESULTS': row,
            'MATCH_FIELD': match_field if match_index is not None else None,
            'MATCH_ID': _value_at(row, match_index),
        })
    return pd.DataFrame(records)