import csv
import json
import io
import pandas as pd

def json_to_csv(json_data):
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    output = io.StringIO()
    
    writer = csv.writer(output)

    try:
        writer.writerow(json_data[0].keys())
    except:
        print("no data to process")
        return None
    for item in json_data:
        writer.writerow(item.values())

    csv_content = output.getvalue()
    output.close()
    
    return csv_content

def success_upserts(data, job_id):
    csv_file = io.StringIO(data)
    csv_reader = csv.reader(csv_file)

    header = next(csv_reader, None)
    record = {}
    records = []
    
    if header:
        row_count = 1  # If header exists, count it as a row
        print("@@@{}\n".format(header))
    for row in csv_reader:
        record['HISTORY_ID'] = job_id
        record['SF_ID'] = row[0]
        record['SF_CREATED'] = row[1]
        records.append(record)
        record = {}
    df = pd.DataFrame(records)
    return df
    
def fail_upserts(data, job_id):
    csv_file = io.StringIO(data)

    csv_reader = csv.reader(csv_file)

    header = next(csv_reader, None)

    record = {}
    records = []
    
    if header:
        row_count = 1  # If header exists, count it as a row
        print("@@@{}\n".format(header))
    for row in csv_reader:
        record['HISTORY_ID'] = job_id
        record['SF_ID'] = row[0]
        record['SF_CREATED'] = False
        #if 'sf__Error' in row:
        record['SF_ERROR'] = row[1]
        record['HEADERS'] = header
        record['RESULTS'] = row
        #record['MATCH_FIELD'] = None
        #record['MATCH_ID'] = None
        records.append(record)
        record = {}
    df = pd.DataFrame(records)
    return df