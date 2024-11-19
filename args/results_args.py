import argparse

def retl_results_args(retl_res):
    #retl_parser = argparse.ArgumentParser()
    #retl_parser = subparsers.add_parser('retl', help='Reverse ETL data into Salesforce')
    retl_res.add_argument('--job_id', '--id', type=str, required=True, help='The ID of the job with the results')
    retl_res.add_argument('--schema', '--s',required=True, help='The schema holding the table where results are captured')
    #retl_res.add_argument('--table', '--t', required=True, help='the table where results are captured')
    retl_res.add_argument('--username', '--u', type=str, required=True, help='The username you wish to use to login to Salesforce')
    retl_res.add_argument('--db_connect','--db', type=str, required=False, help='The Snowflake database connection') 
    retl_res.add_argument('--instance_type','--instance', type=int, required=True, help='Salesforce Instance Type:  1 = Productio; 0 = Sandbox')  
    return retl_res  #.parse_args()

