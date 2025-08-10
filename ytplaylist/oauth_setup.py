#!/usr/bin/env python3
"""
OAuth Setup Script for YouTube API
Run this script once to complete the OAuth flow and store tokens in Parameter Store
"""

import json
import boto3
import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

# Add the common directory to the path to import ssm_credentials
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common'))
from ssm_credentials import SSMCredentialsManager

# Scopes required for YouTube playlist creation
SCOPES = ['https://www.googleapis.com/auth/youtube']

def main():
    print("YouTube OAuth Setup")
    print("=" * 30)

    # Load client secrets from SSM Parameter Store
    try:
        ssm_manager = SSMCredentialsManager()
        if not ssm_manager.test_connection():
            print("✗ Cannot connect to SSM Parameter Store or parameters don't exist")
            print("Please run bin/setup-ssm-parameters.sh first to store Google OAuth credentials")
            return

        client_config = ssm_manager.get_google_oauth_config()
        print("✓ Loaded credentials from SSM Parameter Store")
    except Exception as e:
        print(f"✗ Error loading credentials from SSM: {str(e)}")
        print("Make sure to run bin/setup-ssm-parameters.sh first")
        return

    # Run OAuth flow
    try:
        flow = InstalledAppFlow.from_client_config(
            client_config,
            SCOPES
        )

        # This will open a browser window for authorization
        credentials = flow.run_local_server(port=8081)

        print("✓ OAuth flow completed successfully")
        print(f"✓ Access Token: {credentials.token}")
        print(f"✓ Refresh Token: {credentials.refresh_token}")

        # Store tokens in Parameter Store
        store_tokens_in_ssm(credentials.token, credentials.refresh_token)

        print("\n" + "="*50)
        print("✅ TOKENS STORED IN SSM PARAMETER STORE")
        print("="*50)
        print("The OAuth tokens have been securely stored in AWS SSM Parameter Store:")
        print("- /youtube/access_token (SecureString)")
        print("- /youtube/refresh_token (SecureString)")
        print("\nYour Lambda functions will now automatically use these tokens.")
        print("="*50)

    except Exception as e:
        print(f"✗ Error during OAuth flow: {str(e)}")

def store_tokens_in_ssm(access_token, refresh_token):
    """Store OAuth tokens in SSM Parameter Store as SecureStrings"""
    try:
        ssm = boto3.client('ssm')

        # Store access token
        ssm.put_parameter(
            Name='/youtube/access_token',
            Value=access_token,
            Type='SecureString',
            Description='YouTube OAuth2 Access Token',
            Overwrite=True
        )

        # Store refresh token
        if refresh_token:
            ssm.put_parameter(
                Name='/youtube/refresh_token',
                Value=refresh_token,
                Type='SecureString',
                Description='YouTube OAuth2 Refresh Token',
                Overwrite=True
            )

        print("✓ Tokens stored in SSM Parameter Store")

    except Exception as e:
        print(f"✗ Error storing tokens in SSM: {str(e)}")
        print("Tokens printed above can be manually added to SSM Parameter Store")

if __name__ == "__main__":
    main()
