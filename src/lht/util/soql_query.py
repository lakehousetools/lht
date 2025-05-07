from lht.salesforce import sobjects as sobj

def build_soql(session, access_info, sobject):
    query_string, df_fields, create_table_fields = sobj.describe(session, access_info, sobject)
    query_string = "select"
    first_time = True
    for field in df_fields.keys():
        if first_time == True:
            query_string = query_string + "\n"+field
            first_time = False
        else:
            query_string = query_string + '\n,'+field
    query_string = query_string + "\n from {}".format(sobject)
    return query_string