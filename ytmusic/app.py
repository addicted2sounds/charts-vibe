from ytmusicapi import YTMusic
import boto3
import os
import json
from datetime import datetime

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

    # Update database if track_id is provided
    if track_id:
        try:
            update_track_with_youtube_data(track_id, youtube_data)
        except Exception as e:
            print(f"Error updating database: {str(e)}")

    # Also try to find and update existing track by title/artist
    try:
        find_and_update_existing_track(title, author, youtube_data)
    except Exception as e:
        print(f"Error finding/updating existing track: {str(e)}")

    return {
        "statusCode": 200,
        "body": youtube_data
    }

def update_track_with_youtube_data(track_id, youtube_data):
    """Update existing track with YouTube data"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)

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

if __name__ == "__main__":
    import json
    event = {"title": "Verabo en NY", "author": "Toman"}
    print(json.dumps(lambda_handler(event, None), indent=2))
