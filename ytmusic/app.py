from ytmusicapi import YTMusic
import boto3
import os
import json
import uuid
import hashlib
import re
from datetime import datetime

def generate_track_id(title, artist):
    """
    Generate a deterministic track ID based on normalized title and artist using SHA-256
    """
    def normalize_string(s):
        if not s:
            return ""
        # Convert to lowercase, remove extra spaces, remove special chars
        s = s.lower().strip()
        s = re.sub(r'[^\w\s]', '', s)  # Remove special characters
        s = re.sub(r'\s+', ' ', s)     # Normalize whitespace
        return s

    normalized_title = normalize_string(title)
    normalized_artist = normalize_string(artist)

    # Create combined string
    combined = f"{normalized_artist}::{normalized_title}"

    # Generate SHA-256 hash
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return hash_obj.hexdigest()

def lambda_handler(event, context):
    title = event.get("title")
    author = event.get("author")
    track_id = event.get("track_id")  # Optional track ID for updating existing record

    if not title or not author:
        return {"statusCode": 400, "body": "Missing title or author"}

    ytmusic = YTMusic()
    results = ytmusic.search(query=f"{title} {author}", filter="songs")

    if not results:
        return {"statusCode": 404, "body": "Track not found"}

    track = results[0]
    youtube_data = {
        "title": track.get("title"),
        "artist": track.get("artists")[0].get("name") if track.get("artists") else author,
        "videoId": track.get("videoId"),
        "url": f"https://music.youtube.com/watch?v={track.get('videoId')}"
    }

    stored_track_id = None

    # Update database if track_id is provided
    if track_id:
        try:
            success = update_track_with_youtube_data(track_id, youtube_data)
            if success:
                stored_track_id = track_id
                print(f"Updated track {track_id} with YouTube data")
            else:
                print(f"Failed to update track {track_id} - may not exist")
        except Exception as e:
            print(f"Error updating database: {str(e)}")

    # Try to find and update existing track by title/artist using hash-based lookup
    try:
        # Generate the expected track ID for this title/artist combination
        expected_track_id = generate_track_id(title, author)
        existing_track = check_track_exists(title, author)

        if existing_track:
            # Track exists - update with YouTube data if it doesn't have it
            if not existing_track.get('youtube_video_id'):
                success = update_track_with_youtube_data(existing_track['track_id'], youtube_data)
                if success:
                    stored_track_id = existing_track['track_id']
                    print(f"Updated existing track {stored_track_id} with YouTube data")
                else:
                    print(f"Failed to update existing track {existing_track['track_id']}")
            else:
                stored_track_id = existing_track['track_id']
                print(f"Track {stored_track_id} already has YouTube data")
        else:
            # No existing track found, create a new one with hash-based ID
            stored_track_id = create_new_track(youtube_data)
            if stored_track_id:
                print(f"Created new track with hash-based ID: {stored_track_id}")
    except Exception as e:
        print(f"Error finding/updating/creating track: {str(e)}")

    response_body = youtube_data.copy()
    if stored_track_id:
        response_body["stored_track_id"] = stored_track_id

    return {
        "statusCode": 200,
        "body": response_body
    }

def update_track_with_youtube_data(track_id, youtube_data):
    """Update existing track with YouTube data"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)

        # Check if track exists first
        response = table.get_item(Key={'track_id': track_id})
        if 'Item' not in response:
            print(f"Track with ID {track_id} not found")
            return False

        table.update_item(
            Key={'track_id': track_id},
            UpdateExpression="SET youtube_video_id = :video_id, youtube_url = :url, updated_at = :timestamp",
            ExpressionAttributeValues={
                ':video_id': youtube_data['videoId'],
                ':url': youtube_data['url'],
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
        return True
    except Exception as e:
        print(f"Error updating track: {str(e)}")
        return False

def find_and_update_existing_track(title, artist, youtube_data):
    """Find existing track by title/artist and update with YouTube data"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)

        # Scan for matching tracks (in production, consider using GSI for better performance)
        response = table.scan(
            FilterExpression='title = :title AND artist = :artist',
            ExpressionAttributeValues={
                ':title': title,
                ':artist': artist
            }
        )

        items = response.get('Items', [])
        for item in items:
            if not item.get('youtube_video_id'):  # Only update if YouTube data is missing
                table.update_item(
                    Key={'track_id': item['track_id']},
                    UpdateExpression="SET youtube_video_id = :video_id, youtube_url = :url, updated_at = :timestamp",
                    ExpressionAttributeValues={
                        ':video_id': youtube_data['videoId'],
                        ':url': youtube_data['url'],
                        ':timestamp': datetime.utcnow().isoformat()
                    }
                )

        return len(items)
    except Exception as e:
        print(f"Error finding/updating tracks: {str(e)}")
        return 0

def create_new_track(youtube_data):
    """Create a new track record with YouTube data using hash-based ID"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)

        # Generate deterministic ID based on title and artist
        track_id = generate_track_id(youtube_data['title'], youtube_data['artist'])
        timestamp = datetime.utcnow().isoformat()

        # Check if track with this ID already exists
        existing_response = table.get_item(Key={'track_id': track_id})
        if 'Item' in existing_response:
            print(f"Track with ID {track_id} already exists, returning existing ID")
            return track_id

        item = {
            'track_id': track_id,
            'created_at': timestamp,
            'updated_at': timestamp,
            'title': youtube_data['title'],
            'artist': youtube_data['artist'],
            'youtube_video_id': youtube_data['videoId'],
            'youtube_url': youtube_data['url'],
            'source': 'ytmusic'
        }

        table.put_item(Item=item)
        print(f"Created new track with hash-based ID: {track_id}")
        return track_id

    except Exception as e:
        print(f"Error creating new track: {str(e)}")
        return None

def check_track_exists(title, artist):
    """Check if a track already exists by generating its hash-based ID and looking it up directly"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)

        # Generate the expected track ID
        expected_track_id = generate_track_id(title, artist)

        # Direct lookup by ID (much more efficient than scanning)
        response = table.get_item(Key={'track_id': expected_track_id})

        if 'Item' in response:
            return response['Item']
        else:
            return None

    except Exception as e:
        print(f"Error checking if track exists: {str(e)}")
        return None

if __name__ == "__main__":
    import json
    event = {"title": "Verano en NY", "author": "Toman"}
    print(json.dumps(lambda_handler(event, None), indent=2))
