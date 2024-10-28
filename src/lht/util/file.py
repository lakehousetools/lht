

def read_sql_from_file(file_path):
    # Read the content of the file
    with open(file_path, 'r') as file:
        sql_statement = file.read()
    return sql_statement