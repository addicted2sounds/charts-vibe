#!/usr/bin/env python3
"""
Test script for the Chart Processor Lambda function
"""

import json
import os
import sys
import boto3
from moto import mock_dynamodb, mock_s3, mock_sns
import pytest

# Add the current directory to the path so we can import the lambda function
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import lambda_handler, extract_tracks_from_chart, normalize_track_data, filter_new_tracks

@mock_dynamodb
@mock_s3
@mock_sns
def test_chart_processor_with_new_tracks():
    """Test the chart processor with new tracks"""

    # Setup mock AWS resources
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    s3_client = boto3.client('s3', region_name='us-east-1')
    sns_client = boto3.client('sns', region_name='us-east-1')

    # Create DynamoDB table
    table = dynamodb.create_table(
        TableName='tracks',
        KeySchema=[
            {'AttributeName': 'track_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'track_id', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Create S3 bucket
    bucket_name = 'test-playlists-bucket'
    s3_client.create_bucket(Bucket=bucket_name)

    # Create SNS topic
    topic_response = sns_client.create_topic(Name='new-tracks')
    topic_arn = topic_response['TopicArn']

    # Set environment variables
    os.environ['TRACKS_TABLE'] = 'tracks'
    os.environ['NEW_TRACKS_TOPIC_ARN'] = topic_arn

    # Create test chart data in scraper format
    chart_data = {
        "playlist_id": "beatport-top100-20240730-120000",
        "name": "Beatport Top 100",
        "description": "Top 100 tracks scraped from Beatport",
        "source": "beatport",
        "created_at": "2024-07-30T12:00:00.000Z",
        "track_count": 2,
        "tracks": [
            {
                "title": "Test Track 1",
                "artist": "Test Artist 1",
                "album": "Test Album",
                "genre": "Electronic",
                "bpm": 128,
                "key": "Am",
                "rank": 1
            },
            {
                "title": "Test Track 2",
                "artist": "Test Artist 2",
                "genre": "House",
                "bpm": 125,
                "rank": 2
            }
        ]
    }

    # Upload chart data to S3
    s3_key = 'beatport/2024/07/30/top100-120000.json'
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(chart_data),
        ContentType='application/json'
    )

    # Create S3 event
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket_name},
                    "object": {"key": s3_key}
                }
            }
        ]
    }

    # Execute lambda function
    result = lambda_handler(event, None)

    # Assertions
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['total_tracks'] == 2
    assert body['new_tracks'] == 2
    assert body['published_to_sns'] == 2

def test_extract_tracks_from_chart():
    """Test track extraction from different chart formats"""

    # Test direct array format
    chart_data_array = [
        {"title": "Track 1", "artist": "Artist 1"},
        {"title": "Track 2", "artist": "Artist 2"}
    ]

    tracks = extract_tracks_from_chart(chart_data_array)
    assert len(tracks) == 2
    assert tracks[0]['title'] == "Track 1"

    # Test object with tracks property
    chart_data_object = {
        "tracks": [
            {"title": "Track 3", "artist": "Artist 3"},
            {"title": "Track 4", "artist": "Artist 4"}
        ]
    }

    tracks = extract_tracks_from_chart(chart_data_object)
    assert len(tracks) == 2
    assert tracks[0]['title'] == "Track 3"

    # Test playlist format
    chart_data_playlist = {
        "playlist": {
            "name": "Top 100",
            "tracks": [
                {"title": "Track 5", "artist": "Artist 5"}
            ]
        }
    }

    tracks = extract_tracks_from_chart(chart_data_playlist)
    assert len(tracks) == 1
    assert tracks[0]['title'] == "Track 5"

def test_normalize_track_data():
    """Test track data normalization"""

    # Test with complete track data
    track_data = {
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "genre": "Electronic",
        "bpm": 128,
        "key": "Am",
        "rank": 1
    }

    normalized = normalize_track_data(track_data)
    assert normalized is not None
    assert normalized['title'] == "Test Track"
    assert normalized['artist'] == "Test Artist"
    assert normalized['bpm'] == 128
    assert 'metadata' in normalized

    # Test with artist as array
    track_data_artists = {
        "title": "Test Track",
        "artists": ["Artist 1", "Artist 2"],
        "genre": "House"
    }

    normalized = normalize_track_data(track_data_artists)
    assert normalized is not None
    assert normalized['artist'] == "Artist 1, Artist 2"

    # Test with missing required fields
    incomplete_track = {
        "album": "Test Album",
        "genre": "Electronic"
    }

    normalized = normalize_track_data(incomplete_track)
    assert normalized is None

@mock_dynamodb
def test_filter_new_tracks():
    """Test filtering of existing tracks"""

    # Setup mock DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='tracks',
        KeySchema=[
            {'AttributeName': 'track_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'track_id', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Set environment variable
    os.environ['TRACKS_TABLE'] = 'tracks'

    # Add an existing track
    table.put_item(Item={
        'track_id': 'existing-track-1',
        'title': 'Existing Track',
        'artist': 'Existing Artist'
    })

    # Test tracks (one existing, one new)
    test_tracks = [
        {'title': 'Existing Track', 'artist': 'Existing Artist'},
        {'title': 'New Track', 'artist': 'New Artist'}
    ]

    new_tracks = filter_new_tracks(test_tracks)

    # Should only return the new track
    assert len(new_tracks) == 1
    assert new_tracks[0]['title'] == 'New Track'

if __name__ == "__main__":
    # Run tests
    test_extract_tracks_from_chart()
    print("✓ Test extract_tracks_from_chart passed")

    test_normalize_track_data()
    print("✓ Test normalize_track_data passed")

    test_filter_new_tracks()
    print("✓ Test filter_new_tracks passed")

    test_chart_processor_with_new_tracks()
    print("✓ Test chart_processor_with_new_tracks passed")

    print("\n🎉 All tests passed!")
