import argparse
import os
import webbrowser
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth
import requests
import toml

CLIENT_ID = '3MVG9cHH2bfKACZbozJZ6VCTB.WIZcgxpPRcobzSVrhJW3.IEaOjkgUIVgWZkjJSIxZ2Zohhdg5uXjrqUF4HC'
CLIENT_SECRET = 'C888F0F7EC1282FEB7D5A1A2C332811F12141656EFA903021CC696A799D4FCEF'
AUTHORIZATION_BASE_URL = 'https://login.salesforce.com/services/oauth2/authorize'
TOKEN_URL = 'https://login.salesforce.com/services/oauth2/token'
REDIRECT_URI = 'https://localhost/callback'
SCOPE = 'full'

def main():
    # Create an OAuth2 session
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)

    # Get the authorization URL
    authorization_url, state = oauth.authorization_url(AUTHORIZATION_BASE_URL)

    # Open the authorization URL in the browser
    print("Opening the following URL in your browser for authentication:")
    print(authorization_url)
    webbrowser.open(authorization_url)

    # Ask the user to enter the response URL after authorization
    redirect_response = input("Paste the full redirect URL here: ")

    # Fetch the access token
    oauth.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=redirect_response)

    # Now you can use the OAuth2 session to make authorized API requests
    response = oauth.get('https://www.googleapis.com/oauth2/v2/userinfo')
    print("User info:")
    print(response.json())

if __name__ == "__main__":
    main()