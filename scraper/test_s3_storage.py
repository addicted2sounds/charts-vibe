#!/usr/bin/env python3
"""
Test script for S3 playlist storage functionality
"""
import json
import os
from datetime import datetime, timezone
from app import store_playlist_in_s3

def test_playlist_storage():
    """Test the S3 playlist storage functionality"""

    # Mock playlist data
    test_playlist_data = {
        'playlist_id': 'test-playlist-123',
        'name': 'Test Beatport Top 100',
        'description': 'Test playlist for S3 storage',
        'source': 'beatport',
        'source_url': 'https://www.beatport.com/top-100',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'track_count': 2,
        'tracks': [
            {
                'position': 1,
                'title': 'Test Track 1',
                'artist': 'Test Artist 1',
                'genre': 'House',
                'bpm': 128,
                'beatport_id': 'test123'
            },
            {
                'position': 2,
                'title': 'Test Track 2',
                'artist': 'Test Artist 2',
                'genre': 'Techno',
                'bpm': 132,
                'beatport_id': 'test456'
            }
        ],
        'metadata': {
            'scraper_version': '1.0',
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }
    }

    # Note: This will only work if AWS credentials are configured and the S3 bucket exists
    # For local testing, you might want to use LocalStack or mock the S3 calls

    print("Testing S3 playlist storage...")
    print(f"Playlist data: {json.dumps(test_playlist_data, indent=2, default=str)}")

    # Set environment variable for testing (replace with actual bucket name when deployed)
    os.environ['PLAYLISTS_BUCKET'] = 'test-music-search-playlists'

    try:
        result = store_playlist_in_s3(test_playlist_data, test_playlist_data['playlist_id'])
        if result:
            print(f"✅ Successfully stored playlist in S3: {result}")
        else:
            print("❌ Failed to store playlist in S3")
    except Exception as e:
        print(f"❌ Error testing S3 storage: {str(e)}")
        print("Note: This test requires AWS credentials and an existing S3 bucket")

if __name__ == "__main__":
    test_playlist_storage()
