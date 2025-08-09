#!/usr/bin/env python3
"""
Simple test script to verify SQS event parsing logic
"""
import json

def test_sqs_message_parsing():
    """Test SQS message parsing without external dependencies"""

    # Simulate SQS event structure
    sqs_event = {
        "Records": [
            {
                "messageId": "test-message-1",
                "body": json.dumps({
                    "Type": "Notification",
                    "MessageId": "test-sns-message-1",
                    "Message": json.dumps({
                        "track": {
                            "title": "Verano en NY",
                            "artist": "Toman",
                            "album": "Test Album"
                        },
                        "source_file": "beatport/2024/07/30/top100.json",
                        "timestamp": "2024-07-30T12:00:00Z",
                        "action": "process_new_track"
                    })
                })
            },
            {
                "messageId": "test-message-2",
                "body": json.dumps({
                    "Type": "Notification",
                    "MessageId": "test-sns-message-2",
                    "Message": json.dumps({
                        "track": {
                            "title": "",  # Empty title should be handled gracefully
                            "artist": "Artist Name"
                        }
                    })
                })
            }
        ]
    }

    print("Testing SQS Message Parsing Logic...")
    print("=" * 50)

    # Parse SQS messages
    parsed_tracks = []
    for record in sqs_event['Records']:
        try:
            message_body = json.loads(record['body'])
            if 'Message' in message_body:
                sns_message = json.loads(message_body['Message'])
                track_data = sns_message.get('track', {})

                if track_data:
                    title = track_data.get('title', '').strip()
                    artist = track_data.get('artist', '').strip()

                    if title and artist:
                        parsed_tracks.append({
                            'title': title,
                            'artist': artist,
                            'source': sns_message.get('source_file', 'unknown')
                        })
                        print(f"✅ Parsed track: {title} - {artist}")
                    else:
                        print(f"❌ Invalid track: missing title or artist (title='{title}', artist='{artist}')")
                else:
                    print(f"❌ No track data in message {record['messageId']}")
        except Exception as e:
            print(f"❌ Error parsing record {record['messageId']}: {str(e)}")

    print(f"\nSuccessfully parsed {len(parsed_tracks)} tracks from {len(sqs_event['Records'])} messages")

    return parsed_tracks

def test_direct_event_detection():
    """Test detection of direct API calls vs SQS events"""

    print("\n" + "=" * 50)
    print("Testing Event Type Detection...")
    print("=" * 50)

    # SQS event
    sqs_event = {"Records": [{"messageId": "test"}]}
    print(f"SQS Event detected: {'Records' in sqs_event}")

    # Direct API event
    direct_event = {"title": "Test Song", "author": "Test Artist"}
    print(f"Direct Event detected: {'Records' not in direct_event}")

    # Empty event
    empty_event = {}
    print(f"Empty Event (should be direct): {'Records' not in empty_event}")

def test_message_format_variations():
    """Test different SNS message formats"""

    print("\n" + "=" * 50)
    print("Testing Message Format Variations...")
    print("=" * 50)

    # Valid track with all fields
    valid_message = {
        "track": {
            "title": "Amazing Track",
            "artist": "Great Artist",
            "album": "Awesome Album",
            "genre": "Electronic",
            "bpm": 128
        }
    }

    # Track with minimal required fields
    minimal_message = {
        "track": {
            "title": "Minimal Track",
            "artist": "Minimal Artist"
        }
    }

    # Invalid track - missing artist
    invalid_message = {
        "track": {
            "title": "Track Without Artist"
        }
    }

    # No track data
    no_track_message = {
        "source_file": "test.json",
        "timestamp": "2024-07-30T12:00:00Z"
    }

    messages = [
        ("Valid with all fields", valid_message),
        ("Minimal required fields", minimal_message),
        ("Missing artist", invalid_message),
        ("No track data", no_track_message)
    ]

    for name, message in messages:
        track_data = message.get('track', {})
        title = track_data.get('title', '').strip()
        artist = track_data.get('artist', '').strip()

        if track_data and title and artist:
            print(f"✅ {name}: {title} - {artist}")
        else:
            print(f"❌ {name}: Invalid (title='{title}', artist='{artist}')")

if __name__ == "__main__":
    print("YouTube Music SQS Integration - Logic Test")
    print("=" * 60)

    test_sqs_message_parsing()
    test_direct_event_detection()
    test_message_format_variations()

    print("\n" + "=" * 60)
    print("Logic test completed successfully!")
    print("Note: This only tests message parsing logic, not external API calls.")
