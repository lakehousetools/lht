import toml

def get_param(group, item):
    config = toml.load(".snowflake/connections.toml")
    
    params = config[group]
    return params[item]