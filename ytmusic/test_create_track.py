#!/usr/bin/env python3
"""
Test script to demonstrate the new track creation functionality with hash-based IDs
"""

import json
import sys
import os

# Add the current directory to the path so we can import our module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the lambda handler and helper functions
try:
    from app import lambda_handler, generate_track_id
except ImportError as e:
    print(f"Error importing app module: {e}")
    print("Make sure you're running this script from the ytmusic directory")
    sys.exit(1)

def test_id_generation():
    """Test the ID generation function"""
    print("Testing hash-based ID generation...")
    print("-" * 40)

    test_cases = [
        ("Bohemian Rhapsody", "Queen"),
        ("Another One Bites the Dust", "Queen"),
        ("Let It Be", "The Beatles"),
        ("let it be", "the beatles"),  # Test normalization
        ("LET IT BE", "THE BEATLES"),  # Test case insensitivity
        ("Let It Be!", "The Beatles."),  # Test special character removal
        ("  Let   It   Be  ", " The  Beatles "),  # Test whitespace normalization
    ]

    for title, artist in test_cases:
        track_id = generate_track_id(title, artist)
        print(f"'{title}' by '{artist}' -> {track_id[:16]}...")

    # Test that normalized versions produce the same ID
    id1 = generate_track_id("Let It Be", "The Beatles")
    id2 = generate_track_id("let it be", "the beatles")
    id3 = generate_track_id("LET IT BE!", "THE BEATLES.")

    print(f"\nNormalization test:")
    print(f"All IDs should be identical:")
    print(f"ID1: {id1[:16]}...")
    print(f"ID2: {id2[:16]}...")
    print(f"ID3: {id3[:16]}...")
    print(f"Normalization works: {id1 == id2 == id3}")
    print()

def test_create_new_track():
    """Test creating a new track when it doesn't exist in the database"""

    test_event = {
        "title": "Bohemian Rhapsody",
        "author": "Queen"
    }

    print("Testing track creation with hash-based ID...")
    expected_id = generate_track_id(test_event["title"], test_event["author"])
    print(f"Expected hash-based ID: {expected_id}")
    print(f"Searching for: {test_event['title']} by {test_event['author']}")
    print("-" * 50)

    try:
        # Call the lambda handler
        result = lambda_handler(test_event, None)

        # Print the result
        print("Lambda Response:")
        print(json.dumps(result, indent=2))

        if result["statusCode"] == 200:
            body = result["body"]
            print("\nYouTube Music Search Results:")
            print(f"Title: {body.get('title')}")
            print(f"Artist: {body.get('artist')}")
            print(f"Video ID: {body.get('videoId')}")
            print(f"URL: {body.get('url')}")

            if "stored_track_id" in body:
                print(f"\n✅ Track stored in database with ID: {body['stored_track_id']}")
            else:
                print("\n❌ Track was not stored in database")

        else:
            print(f"\n❌ Error: {result['body']}")

    except Exception as e:
        print(f"Error during test: {str(e)}")

def test_update_existing_track():
    """Test updating an existing track with a specific track_id"""

    # Test event with a track_id (you would replace this with a real track ID from your database)
    test_event = {
        "title": "Another One Bites the Dust",
        "author": "Queen",
        "track_id": "test-track-id-12345"  # This would be a real UUID in practice
    }

    print("\n" + "="*50)
    print("Testing track update functionality...")
    print(f"Updating track {test_event['track_id']} with YouTube data")
    print("-" * 50)

    try:
        # Call the lambda handler
        result = lambda_handler(test_event, None)

        # Print the result
        print("Lambda Response:")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error during test: {str(e)}")

if __name__ == "__main__":
    print("YouTube Music Track Creation Test with Hash-Based IDs")
    print("=" * 55)
    print("NOTE: This test requires:")
    print("1. LocalStack running with DynamoDB")
    print("2. The 'tracks' table created")
    print("3. Environment variable TRACKS_TABLE set")
    print("4. Internet connection for YouTube Music API")
    print("=" * 55)

    # Run tests
    test_id_generation()
    test_create_new_track()
    test_update_existing_track()

    print("\n" + "=" * 55)
    print("Test completed!")
