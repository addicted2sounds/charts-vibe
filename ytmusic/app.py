from ytmusicapi import YTMusic
import boto3
import os
import json
import sys
import uuid
import hashlib
import re
from datetime import datetime
from decimal import Decimal
from utils import generate_track_id, check_track_exists_by_id


class TrackNotFoundError(Exception):
    """Raised when a track cannot be located on YouTube Music."""
    pass

def decimal_to_serializable(obj):
    """Convert Decimal objects to JSON-serializable types"""
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise to float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    elif isinstance(obj, dict):
        return {key: decimal_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_serializable(item) for item in obj]
    else:
        return obj

def lambda_handler(event, context):
    """
    Handle both SQS events (from SNS) and direct API calls
    """

    # Check if this is an SQS event
    if 'Records' in event:
        return handle_sqs_events(event, context)
    else:
        # Handle direct API call
        return handle_direct_request(event, context)

def handle_sqs_events(event, context):
    """
    Process SQS events containing SNS messages with track data
    """
    results = []

    for record in event['Records']:
        try:
            # Parse SQS message body (which contains the SNS message)
            message_body = json.loads(record['body'])

            # Extract SNS message
            if 'Message' in message_body:
                sns_message = json.loads(message_body['Message'])
                track_data = sns_message.get('track', {})
                job_id = sns_message.get('job_id')

                if track_data:
                    title = track_data.get('title', '').strip()
                    artist = track_data.get('artist', '').strip()
                    track_id = track_data.get('track_id', '').strip()  # Extract track_id from SNS message

                    if title and artist:
                        print(f"Processing track from SQS: {title} - {artist} (Job: {job_id}, Track ID: {track_id[:8] if track_id else 'None'}...)")

                        status = 'failed'
                        result = None
                        error_message = None

                        try:
                            result = process_track_search(title, artist, track_id)
                            if result:
                                status = 'success'
                        except TrackNotFoundError as not_found_error:
                            status = 'not_found'
                            error_message = str(not_found_error)
                            send_track_to_dlq(track_data, job_id, error_message)

                        if job_id and status in ('success', 'not_found'):
                            update_job_counter(job_id)

                        result_entry = {
                            'track': f"{title} - {artist}",
                            'job_id': job_id,
                            'track_id': track_id,
                            'status': status
                        }

                        if status == 'success':
                            result_entry['result'] = result
                        else:
                            result_entry['error'] = error_message or 'processing failed'

                        results.append(result_entry)
                    else:
                        print(f"Invalid track data in SQS message: missing title or artist")
                        results.append({
                            'track': 'unknown',
                            'job_id': job_id,
                            'track_id': track_data.get('track_id', ''),
                            'status': 'failed',
                            'error': 'missing title or artist'
                        })
                else:
                    print(f"No track data found in SNS message")
            else:
                print(f"Invalid SQS message format: no SNS Message found")

        except Exception as e:
            print(f"Error processing SQS record: {str(e)}")
            results.append({
                'status': 'error',
                'error': str(e)
            })

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Processed {len(event["Records"])} SQS messages',
            'results': results
        })
    }

def handle_direct_request(event, context):
    """
    Handle direct API requests (legacy functionality)
    """
    title = event.get("title")
    author = event.get("author")
    track_id = event.get("track_id")  # Optional track ID for updating existing record

    if not title or not author:
        return {"statusCode": 400, "body": "Missing title or author"}

    try:
        result = process_track_search(title, author, track_id)
    except TrackNotFoundError:
        return {"statusCode": 404, "body": "Track not found"}

    return {
        "statusCode": 200,
        "body": result
    }


def send_track_to_dlq(track_data, job_id, reason):
    """Send not-found tracks to the configured dead-letter queue."""
    queue_url = os.environ.get('YOUTUBE_MUSIC_DLQ_URL')

    if not queue_url:
        print(f"DLQ URL not configured; skipping DLQ send for track {track_data.get('track_id', 'unknown') if isinstance(track_data, dict) else 'unknown'}")
        return

    payload = {
        'track': track_data,
        'job_id': job_id,
        'failure_reason': reason,
        'timestamp': datetime.utcnow().isoformat()
    }

    try:
        sqs = boto3.client('sqs')
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(decimal_to_serializable(payload))
        )
        track_id = ''
        if isinstance(track_data, dict):
            track_id = track_data.get('track_id') or ''
        print(f"Sent track {track_id[:8] if track_id else 'unknown'}... to DLQ: {reason}")
    except Exception as e:
        print(f"Failed to send track to DLQ: {str(e)}")

def process_track_search(title, artist, track_id=None):
    """
    Core logic for searching and storing track data

    Args:
        title: Track title
        artist: Track artist
        track_id: Optional track ID (from SNS message or direct API call)
                 If provided from SNS, this should be used to maintain consistency
    """
    try:
        ytmusic = YTMusic()
        results = ytmusic.search(query=f"{title} {artist}", filter="songs")

        if not results:
            message = f"No YouTube results found for: {title} - {artist}"
            print(message)
            raise TrackNotFoundError(message)

        track = results[0]
        youtube_data = {
            "title": track.get("title"),
            "artist": track.get("artists")[0].get("name") if track.get("artists") else artist,
            "videoId": track.get("videoId"),
            "url": f"https://music.youtube.com/watch?v={track.get('videoId')}"
        }

        stored_track_id = None

        # Priority 1: If track_id is provided (from SNS message), use it directly
        if track_id:
            try:
                # Try to create or update the track in a single operation
                success = create_or_update_track_with_id(track_id, title, artist, youtube_data)
                if success:
                    stored_track_id = track_id
                    print(f"Successfully processed track with provided ID: {track_id[:8]}...")
                else:
                    print(f"Failed to process track with provided ID: {track_id[:8]}...")
            except Exception as e:
                print(f"Error processing track with provided ID {track_id[:8]}...: {str(e)}")

        # Priority 2: Fallback to hash-based lookup if no track_id provided or if above failed
        if not stored_track_id:
            try:
                # Generate the expected track ID for this title/artist combination
                expected_track_id = generate_track_id(title, artist)
                existing_track = check_track_exists(title, artist)

                if existing_track:
                    # Track exists - update with YouTube data if it doesn't have it
                    if not existing_track.get('youtube_video_id'):
                        success = update_track_with_youtube_data(existing_track['track_id'], youtube_data)
                        if success:
                            stored_track_id = existing_track['track_id']
                            print(f"Updated existing track {stored_track_id[:8]}... with YouTube data")
                        else:
                            print(f"Failed to update existing track {existing_track['track_id'][:8]}...")
                    else:
                        stored_track_id = existing_track['track_id']
                        print(f"Track {stored_track_id[:8]}... already has YouTube data")
                else:
                    # No existing track found, create a new one with hash-based ID
                    stored_track_id = create_new_track(youtube_data)
                    if stored_track_id:
                        print(f"Created new track with hash-based ID: {stored_track_id[:8]}...")
            except Exception as e:
                print(f"Error finding/updating/creating track: {str(e)}")

        response_body = youtube_data.copy()
        if stored_track_id:
            response_body["stored_track_id"] = stored_track_id

        return response_body

    except TrackNotFoundError:
        raise
    except Exception as e:
        print(f"Error in process_track_search: {str(e)}")
        return None

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

def create_or_update_track_with_id(track_id, title, artist, youtube_data):
    """
    Create or update a track with the provided ID in a single DynamoDB operation.
    Uses conditional put/update to minimize API calls and charges.
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)
        timestamp = datetime.utcnow().isoformat()

        # First, try to update an existing item (if it exists and needs YouTube data)
        try:
            response = table.update_item(
                Key={'track_id': track_id},
                UpdateExpression="SET youtube_video_id = :video_id, youtube_url = :url, updated_at = :timestamp",
                ConditionExpression="attribute_exists(track_id) AND attribute_not_exists(youtube_video_id)",
                ExpressionAttributeValues={
                    ':video_id': youtube_data['videoId'],
                    ':url': youtube_data['url'],
                    ':timestamp': timestamp
                },
                ReturnValues='ALL_NEW'
            )
            print(f"Updated existing track {track_id[:8]}... with YouTube data")
            return True
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            # Either track doesn't exist, or it already has YouTube data
            pass

        # Try to create a new item (if it doesn't exist)
        try:
            item = {
                'track_id': track_id,
                'created_at': timestamp,
                'updated_at': timestamp,
                'title': title,
                'artist': artist,
                'youtube_video_id': youtube_data['videoId'],
                'youtube_url': youtube_data['url'],
                'source': 'ytmusic'
            }

            table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(track_id)"
            )
            print(f"Created new track with provided ID: {track_id[:8]}...")
            return True
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            # Track already exists and likely already has YouTube data
            print(f"Track {track_id[:8]}... already exists with YouTube data")
            return True

    except Exception as e:
        print(f"Error creating/updating track with ID {track_id[:8]}...: {str(e)}")
        return False

def check_track_exists(title, artist):
    """Check if a track already exists by generating its hash-based ID and looking it up directly"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)

        # Generate the expected track ID
        expected_track_id = generate_track_id(title, artist)

        # Use common utility for checking existence
        return check_track_exists_by_id(expected_track_id, table)

    except Exception as e:
        print(f"Error checking if track exists: {str(e)}")
        return None

def update_job_counter(job_id):
    """Update job processed_count and check if job is completed"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('JOBS_TABLE', 'jobs')
        table = dynamodb.Table(table_name)

        # Atomically increment processed_count
        response = table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET processed_count = processed_count + :inc, updated_at = :timestamp',
            ExpressionAttributeValues={
                ':inc': 1,
                ':timestamp': datetime.utcnow().isoformat()
            },
            ReturnValues='ALL_NEW'
        )

        # Check if job is completed
        updated_item = response['Attributes']
        processed_count = updated_item.get('processed_count', 0)
        expected_count = updated_item.get('expected_count', 0)

        print(f"Job {job_id}: processed {processed_count}/{expected_count}")

        if processed_count >= expected_count:
            # Mark job as completed and trigger playlist creation
            complete_job(job_id, updated_item)

    except Exception as e:
        print(f"Error updating job counter: {str(e)}")

def complete_job(job_id, job_data):
    """Mark job as completed and trigger playlist creation event"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('JOBS_TABLE', 'jobs')
        table = dynamodb.Table(table_name)

        # Update job status to completed
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #status = :status, completed_at = :timestamp',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'completed',
                ':timestamp': datetime.utcnow().isoformat()
            }
        )

        # Send JobCompleted event to EventBridge
        send_job_completed_event(job_id, job_data)
        print(f"Job {job_id} marked as completed and event sent")

    except Exception as e:
        print(f"Error completing job: {str(e)}")

def send_job_completed_event(job_id, job_data):
    """Send JobCompleted event to EventBridge to trigger playlist creation"""
    try:
        events_client = boto3.client('events')
        event_bus_name = os.environ.get('EVENT_BUS_NAME', 'default')

        # Convert Decimal objects to JSON-serializable types
        serializable_job_data = decimal_to_serializable(job_data)

        # Create event detail
        detail = {
            'job_id': job_id,
            'source_file': serializable_job_data.get('source_file'),
            'expected_count': serializable_job_data.get('expected_count'),
            'processed_count': serializable_job_data.get('processed_count'),
            'created_at': serializable_job_data.get('created_at'),
            'completed_at': datetime.utcnow().isoformat()
        }

        # Extract S3 info for playlist creation
        source_file = serializable_job_data.get('source_file', '')
        if source_file:
            # Assuming format like "beatport/2024/07/30/top100-120000.json"
            detail['s3_bucket'] = os.environ.get('PLAYLISTS_BUCKET')
            detail['s3_key'] = source_file

        # Send event
        response = events_client.put_events(
            Entries=[
                {
                    'Source': 'music-search.orchestrator',
                    'DetailType': 'Job Completed',
                    'Detail': json.dumps(detail),
                    'EventBusName': event_bus_name
                }
            ]
        )

        print(f"Sent JobCompleted event for job {job_id}: {response}")

    except Exception as e:
        print(f"Error sending job completed event: {str(e)}")

if __name__ == "__main__":
    import json
    event = {"title": "Verano en NY", "author": "Toman"}
    print(json.dumps(lambda_handler(event, None), indent=2))
