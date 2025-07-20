#!/usr/bin/env python3
"""
Simple test script for YouTube Playlist Lambda function
No database storage - just creates playlist and returns URL
"""

import json
import os

# Test the lambda function directly
def test_simple_playlist():
    """Test creating a YouTube playlist without any storage"""

    # Import the lambda handler
    from app import lambda_handler

    # Test event with sample video IDs
    test_event = {
        "playlist_name": "Quick Test Playlist",
        "video_ids": [
            "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
            "kJQP7kiw5Fk",  # Luis Fonsi - Despacito
            "JGwWNGJdvx8"   # Ed Sheeran - Shape of You
        ],
        "description": "Simple test playlist - no storage"
    }

    print("Simple YouTube Playlist Test")
    print("=" * 40)
    print(f"Playlist Name: {test_event['playlist_name']}")
    print(f"Number of Videos: {len(test_event['video_ids'])}")
    print("\nCreating playlist...")

    try:
        # Call the Lambda handler
        result = lambda_handler(test_event, None)

        print("\nResult:")
        print("-" * 20)
        print(json.dumps(result, indent=2))

        # Parse the response
        if result['statusCode'] == 200:
            body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']

            if body.get('success'):
                print(f"\n🎉 SUCCESS!")
                print(f"Playlist ID: {body['playlist_id']}")
                print(f"YouTube URL: {body['playlist_url']}")
                print(f"YouTube Music URL: {body['music_url']}")
                print(f"Videos Added: {body['videos_added_successfully']}/{body['total_videos_requested']}")

                if body.get('failed_videos'):
                    print(f"\nFailed Videos: {len(body['failed_videos'])}")
                    for failed in body['failed_videos']:
                        print(f"  - {failed['video_id']}: {failed['error']}")

                print(f"\n🔗 Open your playlist: {body['playlist_url']}")
            else:
                print(f"\n❌ FAILED: {body.get('error', 'Unknown error')}")
        else:
            error_body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
            print(f"\n❌ HTTP {result['statusCode']}: {error_body.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"\n❌ Exception occurred: {str(e)}")
        print("\nMake sure you have:")
        print("1. Run oauth_setup.py to get access token")
        print("2. Set YOUTUBE_ACCESS_TOKEN environment variable")

def check_setup():
    """Check if everything is set up correctly"""
    print("\nChecking Setup:")
    print("-" * 20)

    # Check if client_secret.json exists
    if os.path.exists('client_secret.json'):
        print("✓ client_secret.json found")
    else:
        print("✗ client_secret.json not found")

    # Check if access token is set
    token = os.environ.get('YOUTUBE_ACCESS_TOKEN')
    if token:
        print("✓ YOUTUBE_ACCESS_TOKEN environment variable set")
        print(f"  Token starts with: {token[:20]}...")
    else:
        print("✗ YOUTUBE_ACCESS_TOKEN environment variable not set")
        print("  Run: export YOUTUBE_ACCESS_TOKEN='your_token_here'")

if __name__ == "__main__":
    check_setup()
    test_simple_playlist()
