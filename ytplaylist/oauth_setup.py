#!/usr/bin/env python3
"""
OAuth Setup Script for YouTube API
Run this script once to complete the OAuth flow and store tokens in Parameter Store
"""

import json
import boto3
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes required for YouTube playlist creation
SCOPES = ['https://www.googleapis.com/auth/youtube']

def main():
    print("YouTube OAuth Setup")
    print("=" * 30)

    # Load client secrets
    try:
        with open('client_secret.json', 'r') as f:
            client_secrets = json.load(f)
        print("✓ Loaded client_secret.json")
    except FileNotFoundError:
        print("✗ client_secret.json not found!")
        return

    # Run OAuth flow
    try:
        flow = InstalledAppFlow.from_client_config(
            client_secrets,
            SCOPES
        )

        # This will open a browser window for authorization
        credentials = flow.run_local_server(port=8081)

        print("✓ OAuth flow completed successfully")
        print(f"✓ Access Token: {credentials.token}")
        print(f"✓ Refresh Token: {credentials.refresh_token}")

        # Just print the token for now, don't save it
        print("\n" + "="*50)
        print("COPY THIS ACCESS TOKEN TO USE IN YOUR LAMBDA:")
        print("="*50)
        print(credentials.token)
        print("="*50)

        print("\nTo use this token:")
        print("1. Set environment variable: export YOUTUBE_ACCESS_TOKEN='your_token_here'")
        print("2. Or add it to your Lambda environment variables")
        print("3. The token will expire, you may need to refresh it periodically")

    except Exception as e:
        print(f"✗ Error during OAuth flow: {str(e)}")

if __name__ == "__main__":
    main()
