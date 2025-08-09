#!/usr/bin/env python3
"""
Test script to verify SQS integration with YouTube Music Search Function
"""
import json
import sys
import os

# Add the current directory to path so we can import app
sys.path.insert(0, os.path.dirname(__file__))

from app import lambda_handler

def test_sqs_event():
    """Test SQS event processing"""

    # Simulate an SQS event that would come from SNS
    sqs_event = {
        "Records": [
            {
                "messageId": "test-message-1",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "Type": "Notification",
                    "MessageId": "test-sns-message-1",
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:music-search-new-tracks",
                    "Subject": "New track: Verano en NY - Toman",
                    "Message": json.dumps({
                        "track": {
                            "title": "Verano en NY",
                            "artist": "Toman",
                            "album": "Test Album",
                            "genre": "Electronic",
                            "label": "Test Label",
                            "bpm": 128,
                            "key": "Am",
                            "rank": 1,
                            "beatport_url": "https://beatport.com/test",
                            "beatport_id": "12345"
                        },
                        "source_file": "beatport/2024/07/30/top100-120000.json",
                        "timestamp": "2024-07-30T12:00:00Z",
                        "action": "process_new_track"
                    }),
                    "Timestamp": "2024-07-30T12:00:00.000Z"
                }),
                "attributes": {},
                "messageAttributes": {},
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:music-search-youtube-music-processing",
                "awsRegion": "us-east-1"
            },
            {
                "messageId": "test-message-2",
                "receiptHandle": "test-receipt-handle-2",
                "body": json.dumps({
                    "Type": "Notification",
                    "MessageId": "test-sns-message-2",
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:music-search-new-tracks",
                    "Subject": "New track: Another Track - Another Artist",
                    "Message": json.dumps({
                        "track": {
                            "title": "Another Track",
                            "artist": "Another Artist",
                            "album": "Another Album"
                        },
                        "source_file": "beatport/2024/07/30/another-chart.json",
                        "timestamp": "2024-07-30T12:01:00Z",
                        "action": "process_new_track"
                    }),
                    "Timestamp": "2024-07-30T12:01:00.000Z"
                })
            }
        ]
    }

    print("Testing SQS Event Processing...")
    print("=" * 50)

    try:
        result = lambda_handler(sqs_event, None)
        print("SQS Event Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error processing SQS event: {str(e)}")
        import traceback
        traceback.print_exc()

def test_direct_api_call():
    """Test direct API call (legacy functionality)"""

    direct_event = {
        "title": "Verano en NY",
        "author": "Toman"
    }

    print("\n" + "=" * 50)
    print("Testing Direct API Call...")
    print("=" * 50)

    try:
        result = lambda_handler(direct_event, None)
        print("Direct API Call Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error processing direct API call: {str(e)}")
        import traceback
        traceback.print_exc()

def test_invalid_sqs_event():
    """Test handling of invalid SQS event"""

    invalid_sqs_event = {
        "Records": [
            {
                "messageId": "test-invalid-message",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "Type": "Notification",
                    "MessageId": "test-sns-message",
                    "Message": json.dumps({
                        "track": {
                            # Missing title and artist
                            "album": "Test Album"
                        },
                        "source_file": "test.json",
                        "timestamp": "2024-07-30T12:00:00Z"
                    })
                })
            }
        ]
    }

    print("\n" + "=" * 50)
    print("Testing Invalid SQS Event...")
    print("=" * 50)

    try:
        result = lambda_handler(invalid_sqs_event, None)
        print("Invalid SQS Event Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error processing invalid SQS event: {str(e)}")

if __name__ == "__main__":
    print("YouTube Music Search Function - SQS Integration Test")
    print("=" * 60)

    # Set environment variables for testing
    os.environ['TRACKS_TABLE'] = 'test-tracks-table'

    # Note: These tests will fail when trying to access DynamoDB and YouTube Music API
    # because they require actual AWS credentials and internet access.
    # This script is mainly for testing the event parsing and flow logic.

    test_sqs_event()
    test_direct_api_call()
    test_invalid_sqs_event()

    print("\n" + "=" * 60)
    print("Test completed. Note: Database and YouTube API calls will fail without proper credentials.")
