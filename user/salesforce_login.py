import argparse
import os
import webbrowser
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth
import requests
import toml

config = toml.load("./.snowflake/connections.toml")
config = config['salesforce_sandbox']

# Replace these values with your app's client ID and secret
CLIENT_ID = config["CLIENT_ID"]
CLIENT_SECRET = config["CLIENT_SECRET"]
AUTHORIZATION_BASE_URL = config["AUTHORIZATION_BASE_URL"]
TOKEN_URL = config["TOKEN_URL"]
REDIRECT_URI = config["REDIRECT_URI"]
SCOPE = config["SCOPE"]

def get_oauth_session():
    return OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)

def authenticate():
    oauth = get_oauth_session()
    authorization_url, state = oauth.authorization_url(AUTHORIZATION_BASE_URL)
    
    print('Please go to this URL and authorize the application:')
    print(authorization_url)
    
    # Open the authorization URL in the default web browser
    webbrowser.open(authorization_url)
    
    redirect_response = input('Paste the full redirect URL here: ')
    oauth.fetch_token(TOKEN_URL, authorization_response=redirect_response, client_secret=CLIENT_SECRET, auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET))
    
    # Save the token for later use
    with open('./.snowflake/token.json', 'w') as token_file:
        token_file.write(str(oauth.token))
    
    print('Authentication successful. Token saved to token.json.')

def main():
    parser = argparse.ArgumentParser(description='CLI tool with OAuth2 authentication.')
    parser.add_argument('command', choices=['login'], help='Command to execute')
    args = parser.parse_args()

    if args.command == 'login':
        authenticate()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()