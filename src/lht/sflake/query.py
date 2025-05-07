from snowflake.snowpark import Session
from lht.util import file

def get_records(session, query_file):
    sql = file.read_sql_from_file(query_file)

    results = session.sql(sql).collect()
    
    record = {}
    records = []
    for result in results:
        for key, value in result.asDict().items():
            if value == None:
                record[key] = ''
            else:
                record[key] = value
        records.append(record)
        record = {}
    return records