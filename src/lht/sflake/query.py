def get_records(session, query):
    

    results = session.sql(query).collect()
    
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