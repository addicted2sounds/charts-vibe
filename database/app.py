import json
import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TRACKS_TABLE', 'tracks')
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    """
    Lambda function to handle CRUD operations for tracks
    """
    try:
        http_method = event.get('httpMethod', '')
        path_parameters = event.get('pathParameters') or {}
        body = event.get('body', '{}')

        if body:
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = {}

        if http_method == 'POST' and event.get('resource') == '/tracks':
            return create_track(body)
        elif http_method == 'GET' and event.get('resource') == '/tracks/{track_id}':
            track_id = path_parameters.get('track_id')
            return get_track(track_id)
        elif http_method == 'GET' and event.get('resource') == '/tracks':
            return get_all_tracks()
        elif http_method == 'PUT' and event.get('resource') == '/tracks/{track_id}':
            track_id = path_parameters.get('track_id')
            return update_track(track_id, body)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid request method or path'})
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def create_track(track_data):
    """Create a new track record"""
    track_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    item = {
        'track_id': track_id,
        'created_at': timestamp,
        'updated_at': timestamp,
        'title': track_data.get('title', ''),
        'artist': track_data.get('artist', ''),
        'album': track_data.get('album', ''),
        'genre': track_data.get('genre', ''),
        'rating': track_data.get('rating'),
        'rank': track_data.get('rank'),
        'bpm': track_data.get('bpm'),
        'key': track_data.get('key', ''),
        'label': track_data.get('label', ''),
        'release_date': track_data.get('release_date', ''),
        'beatport_url': track_data.get('beatport_url', ''),
        'youtube_video_id': track_data.get('youtube_video_id', ''),
        'youtube_url': track_data.get('youtube_url', ''),
        'source': track_data.get('source', 'beatport'),
        'metadata': track_data.get('metadata', {})
    }

    # Remove None values to save space
    item = {k: v for k, v in item.items() if v is not None and v != ''}

    table.put_item(Item=item)

    return {
        'statusCode': 201,
        'body': json.dumps({
            'message': 'Track created successfully',
            'track_id': track_id,
            'track': item
        }, default=str)
    }

def get_track(track_id):
    """Get a specific track by ID"""
    if not track_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'track_id is required'})
        }

    response = table.get_item(Key={'track_id': track_id})

    if 'Item' not in response:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Track not found'})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            'track': response['Item']
        }, default=str)
    }

def get_all_tracks():
    """Get all tracks with pagination support"""
    try:
        response = table.scan(
            Limit=100  # Limit to prevent large responses
        )

        tracks = response.get('Items', [])

        return {
            'statusCode': 200,
            'body': json.dumps({
                'tracks': tracks,
                'count': len(tracks)
            }, default=str)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Error fetching tracks: {str(e)}'})
        }

def update_track(track_id, update_data):
    """Update an existing track"""
    if not track_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'track_id is required'})
        }

    # Check if track exists
    existing = table.get_item(Key={'track_id': track_id})
    if 'Item' not in existing:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Track not found'})
        }

    # Build update expression
    update_expression = "SET updated_at = :timestamp"
    expression_values = {':timestamp': datetime.utcnow().isoformat()}

    # Add updateable fields
    updateable_fields = [
        'title', 'artist', 'album', 'genre', 'rating', 'rank', 'bpm',
        'key', 'label', 'release_date', 'beatport_url', 'youtube_video_id',
        'youtube_url', 'source', 'metadata'
    ]

    for field in updateable_fields:
        if field in update_data:
            update_expression += f", {field} = :{field}"
            expression_values[f':{field}'] = update_data[field]

    table.update_item(
        Key={'track_id': track_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values
    )

    # Get updated item
    updated_item = table.get_item(Key={'track_id': track_id})['Item']

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Track updated successfully',
            'track': updated_item
        }, default=str)
    }

# Helper function for other Lambda functions to store tracks
def store_track_data(track_data):
    """
    Helper function to store track data from other Lambda functions
    Can be imported and used by scraper and ytmusic functions
    """
    return create_track(track_data)

# Helper function to find tracks by title and artist
def find_track_by_title_artist(title, artist):
    """
    Find track by title and artist
    """
    try:
        response = table.scan(
            FilterExpression='title = :title AND artist = :artist',
            ExpressionAttributeValues={
                ':title': title,
                ':artist': artist
            }
        )

        items = response.get('Items', [])
        return items[0] if items else None

    except Exception as e:
        print(f"Error finding track: {str(e)}")
        return None
