#!/usr/bin/env python3
"""
Test script for the music search database functionality with LocalStack
"""

import json
import requests
import time
import boto3
from botocore.exceptions import ClientError

# LocalStack configuration
LOCALSTACK_ENDPOINT = "http://localhost:4566"
API_GATEWAY_ENDPOINT = "http://localhost:4566/restapis"  # Will be updated after deployment

def setup_aws_client():
    """Setup AWS clients for LocalStack"""
    return boto3.client(
        'dynamodb',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def test_database_direct():
    """Test DynamoDB directly"""
    print("Testing DynamoDB directly...")

    dynamodb = setup_aws_client()

    try:
        # List tables
        tables = dynamodb.list_tables()
        print(f"Available tables: {tables['TableNames']}")

        # Check if our tracks table exists
        if 'tracks' in tables['TableNames']:
            print("✓ Tracks table found")

            # Describe the table
            table_info = dynamodb.describe_table(TableName='tracks')
            print(f"Table status: {table_info['Table']['TableStatus']}")

            # Scan for existing items
            dynamodb_resource = boto3.resource(
                'dynamodb',
                endpoint_url=LOCALSTACK_ENDPOINT,
                aws_access_key_id='test',
                aws_secret_access_key='test',
                region_name='us-east-1'
            )
            table = dynamodb_resource.Table('tracks')
            response = table.scan()
            print(f"Existing tracks count: {response['Count']}")

        else:
            print("✗ Tracks table not found")

    except ClientError as e:
        print(f"Error accessing DynamoDB: {e}")

def test_api_endpoints():
    """Test API Gateway endpoints"""
    print("\nTesting API Gateway endpoints...")

    # You'll need to update this with the actual API Gateway URL after deployment
    base_url = "YOUR_API_GATEWAY_URL_HERE"  # Replace with actual URL

    # Test data
    test_track = {
        "title": "Test Track",
        "artist": "Test Artist",
        "genre": "Electronic",
        "rating": 85,
        "rank": 1,
        "bpm": 128,
        "key": "Am",
        "source": "test"
    }

    try:
        # Create a track
        print("Creating test track...")
        response = requests.post(f"{base_url}/tracks", json=test_track)
        if response.status_code == 201:
            track_data = response.json()
            track_id = track_data.get('track_id')
            print(f"✓ Track created with ID: {track_id}")

            # Get the track
            print("Retrieving track...")
            response = requests.get(f"{base_url}/tracks/{track_id}")
            if response.status_code == 200:
                print("✓ Track retrieved successfully")
            else:
                print(f"✗ Failed to retrieve track: {response.status_code}")

            # Update the track
            print("Updating track...")
            update_data = {"rating": 90, "youtube_video_id": "test123", "youtube_url": "https://music.youtube.com/watch?v=test123"}
            response = requests.put(f"{base_url}/tracks/{track_id}", json=update_data)
            if response.status_code == 200:
                print("✓ Track updated successfully")
            else:
                print(f"✗ Failed to update track: {response.status_code}")

        else:
            print(f"✗ Failed to create track: {response.status_code}")

        # Get all tracks
        print("Getting all tracks...")
        response = requests.get(f"{base_url}/tracks")
        if response.status_code == 200:
            tracks_data = response.json()
            print(f"✓ Retrieved {tracks_data.get('count', 0)} tracks")
        else:
            print(f"✗ Failed to get tracks: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Error making API requests: {e}")

def test_scraper_integration():
    """Test the scraper Lambda function"""
    print("\nTesting scraper integration...")

    lambda_client = boto3.client(
        'lambda',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

    try:
        # Invoke the scraper function
        response = lambda_client.invoke(
            FunctionName='music-search-stack-BeatportScraperFunction-XXXXXXXXXX',  # Update with actual function name
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )

        payload = json.loads(response['Payload'].read())
        print(f"Scraper response: {payload}")

    except ClientError as e:
        print(f"Error invoking scraper: {e}")

def test_youtube_integration():
    """Test the YouTube Music Lambda function"""
    print("\nTesting YouTube Music integration...")

    lambda_client = boto3.client(
        'lambda',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

    try:
        # Test payload
        test_payload = {
            "title": "Bohemian Rhapsody",
            "author": "Queen"
        }

        response = lambda_client.invoke(
            FunctionName='music-search-stack-YoutubeMusicSearchFunction-XXXXXXXXXX',  # Update with actual function name
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )

        payload = json.loads(response['Payload'].read())
        print(f"YouTube Music response: {payload}")

    except ClientError as e:
        print(f"Error invoking YouTube Music function: {e}")

if __name__ == "__main__":
    print("Music Search Database Test Suite")
    print("=" * 40)

    # Wait for LocalStack to be ready
    print("Waiting for LocalStack to be ready...")
    time.sleep(5)

    # Run tests
    test_database_direct()
    test_api_endpoints()
    test_scraper_integration()
    test_youtube_integration()

    print("\n" + "=" * 40)
    print("Test suite completed!")
