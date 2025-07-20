#!/usr/bin/env python3
"""
Test script for YouTube Playlist Lambda function
"""

import json
import sys
import os

# Add the ytplaylist directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ytplaylist'))

from ytplaylist.app import lambda_handler

def test_playlist_creation():
    """Test creating a YouTube playlist"""

    # Test event with sample video IDs
    test_event = {
        "playlist_name": "Test Public Playlist from Lambda",
        "video_ids": [
            "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
            "kJQP7kiw5Fk",  # Luis Fonsi - Despacito ft. Daddy Yankee
            "JGwWNGJdvx8",  # Ed Sheeran - Shape of You
            "CevxZvSJLk8",  # Katy Perry - Roar
            "9bZkp7q19f0"   # Gangnam Style
        ],
        "description": "A test playlist created by AWS Lambda with popular YouTube videos"
    }

    print("Testing YouTube Playlist Creation Lambda Function")
    print("=" * 50)
    print(f"Playlist Name: {test_event['playlist_name']}")
    print(f"Number of Videos: {len(test_event['video_ids'])}")
    print(f"Description: {test_event['description']}")
    print("\nInvoking Lambda function...")

    try:
        # Call the Lambda handler
        result = lambda_handler(test_event, None)

        print("\nResponse:")
        print("-" * 20)
        print(json.dumps(result, indent=2))

        # Parse the response
        if result['statusCode'] == 200:
            body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']

            if body.get('success'):
                print(f"\n🎉 SUCCESS!")
                print(f"Playlist ID: {body['playlist_id']}")
                print(f"Playlist URL: {body['playlist_url']}")
                print(f"YouTube Music URL: {body['music_url']}")
                print(f"Videos Added: {body['videos_added_successfully']}/{body['total_videos_requested']}")

                if body['failed_videos']:
                    print(f"\nFailed Videos: {len(body['failed_videos'])}")
                    for failed in body['failed_videos']:
                        print(f"  - {failed['video_id']}: {failed['error']}")
            else:
                print(f"\n❌ FAILED: {body.get('error', 'Unknown error')}")
        else:
            error_body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
            print(f"\n❌ HTTP {result['statusCode']}: {error_body.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"\n❌ Exception occurred: {str(e)}")

def test_credentials():
    """Test if credentials are properly configured"""
    print("\nTesting Credentials Setup")
    print("-" * 30)

    try:
        import boto3

        # Check Parameter Store
        ssm = boto3.client('ssm')

        required_params = [
            '/youtube/client_id',
            '/youtube/client_secret',
            '/youtube/access_token'
        ]

        missing_params = []

        for param in required_params:
            try:
                ssm.get_parameter(Name=param, WithDecryption=True)
                print(f"✓ {param}")
            except ssm.exceptions.ParameterNotFound:
                print(f"✗ {param} - NOT FOUND")
                missing_params.append(param)

        if missing_params:
            print(f"\n⚠️  Missing parameters: {missing_params}")
            print("Run oauth_setup.py to complete the OAuth flow.")
        else:
            print("\n✅ All required parameters found!")

    except Exception as e:
        print(f"Error checking credentials: {str(e)}")

if __name__ == "__main__":
    print("YouTube Playlist Lambda Test Suite")
    print("=" * 40)

    # Test credentials first
    test_credentials()

    # Test playlist creation
    test_playlist_creation()
