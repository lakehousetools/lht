import csv
import json
import io
import pandas as pd

def json_to_csv(json_data):
    # Convert JSON string to a dictionary if necessary
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    # Create a StringIO object to hold the CSV data
    output = io.StringIO()
    
    # Create a CSV writer
    writer = csv.writer(output)

    # Write the header (keys of the first dictionary)
    try:
        writer.writerow(json_data[0].keys())
    except:
        print("no data to process")
        return None
    # Write the data (values of each dictionary)
    for item in json_data:
        writer.writerow(item.values())

    # Get the CSV content from the StringIO object
    csv_content = output.getvalue()
    output.close()
    
    return csv_content

def success_upserts(data, job_id):
    csv_file = io.StringIO(data)

    csv_reader = csv.reader(csv_file)

    header = next(csv_reader, None)

    record = {}
    records = []
    update_field = header[3]
    
    if header:
        row_count = 1  # If header exists, count it as a row
        print("@@@{}\n".format(header))
    for row in csv_reader:
        record['HISTORY_ID'] = job_id
        record['SF_ID'] = row[0]
        record['SF_CREATED'] = row[1]
        record['SF_ERROR'] = ''
        record['MATCH_FIELD'] = update_field
        record['MATCH_ID'] = row[3]
        records.append(record)
        record = {}
    df = pd.DataFrame(records)
    return df
    
