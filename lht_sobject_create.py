
import toml
from salesforce import sobject_create
from snowflake.snowpark import Session
from user import auth

config = toml.load(".snowflake/connections.toml")
snowflake_config = config['myconnection']

connection_parameters = {
    "account": snowflake_config["account"],
    "user": snowflake_config["user"],
    "password": snowflake_config["password"],
    "warehouse": snowflake_config["warehouse"],
    "database": snowflake_config["database"],
    "schema": snowflake_config["schema"]
}
sessionBuilder = Session.builder
for key, value in connection_parameters.items():
    sessionBuilder.config(key, value)

session = sessionBuilder.create()
#session = Session.builder.config(connection_parameters).create()
#session = Session.builder.configs(connection_parameters).create() 
refresh_token, prod, org_id = auth.get_refresh_token(session, 'solomo@radnet.dev')
access_info = auth.salesforce_oauth(session, refresh_token, prod)
sobject_create.create(session, access_info, "Opportunity", "RADNET_SALESFORCE", "STG_SALESFORCE_OPPORTUNITY")