import json
import boto3
import os
import uuid
from datetime import datetime
from urllib.parse import unquote_plus

# Import local utilities (bundled with Lambda function)
from utils import generate_track_id, normalize_track_data, check_track_exists_by_id

def lambda_handler(event, context):
    """
    Lambda function triggered by S3 ObjectCreated events in the charts bucket.
    Processes chart files, filters tracks that already exist in the tracks table,
    and publishes new tracks to SNS queue.
    """
    try:
        # Parse S3 event
        s3_event = event['Records'][0]['s3']
        bucket_name = s3_event['bucket']['name']
        object_key = unquote_plus(s3_event['object']['key'])

        print(f"Processing chart file: s3://{bucket_name}/{object_key}")

        # Download and parse chart file from S3
        chart_data = download_chart_from_s3(bucket_name, object_key)
        if not chart_data:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Failed to download or parse chart file'})
            }

        # Extract tracks from chart data
        tracks = extract_tracks_from_chart(chart_data)
        if not tracks:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No tracks found in chart file'})
            }

        print(f"Found {len(tracks)} tracks in chart")

        # Filter out tracks that already exist in the database
        new_tracks = filter_new_tracks(tracks)
        print(f"Found {len(new_tracks)} new tracks after filtering")

        # Publish new tracks to SNS queue
        if new_tracks:
            published_count = publish_tracks_to_sns(new_tracks, object_key)
            print(f"Published {published_count} tracks to SNS")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed chart file successfully',
                'total_tracks': len(tracks),
                'new_tracks': len(new_tracks),
                'published_to_sns': len(new_tracks)
            })
        }

    except Exception as e:
        print(f"Error processing chart file: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def download_chart_from_s3(bucket_name, object_key):
    """Download and parse chart file from S3"""
    try:
        s3_client = boto3.client('s3')

        # Download the file
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        file_content = response['Body'].read().decode('utf-8')

        # Parse JSON content
        chart_data = json.loads(file_content)
        return chart_data

    except Exception as e:
        print(f"Error downloading chart from S3: {str(e)}")
        return None

def extract_tracks_from_chart(chart_data):
    """Extract tracks from chart data structure (from scraper lambda output)"""
    tracks = []

    try:
        # Handle scraper lambda output format
        if isinstance(chart_data, dict):
            # Primary format: playlist object from scraper
            if 'tracks' in chart_data:
                tracks = chart_data['tracks']
                print(f"Found tracks in playlist format: {chart_data.get('name', 'Unknown')}")
            # Fallback: direct tracks array
            elif isinstance(chart_data, list):
                tracks = chart_data
            # Nested playlist structure
            elif 'playlist' in chart_data and 'tracks' in chart_data['playlist']:
                tracks = chart_data['playlist']['tracks']
            else:
                # Try to find tracks in any array field
                for key, value in chart_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        # Check if this looks like a tracks array
                        first_item = value[0]
                        if isinstance(first_item, dict) and ('title' in first_item or 'artist' in first_item):
                            tracks = value
                            print(f"Found tracks in field: {key}")
                            break
        elif isinstance(chart_data, list):
            # Chart data is directly a list of tracks
            tracks = chart_data

        # Normalize track data structure using common utilities
        normalized_tracks = []
        for track in tracks:
            normalized_track = normalize_track_data(track)
            if normalized_track:
                normalized_tracks.append(normalized_track)

        return normalized_tracks

    except Exception as e:
        print(f"Error extracting tracks from chart: {str(e)}")
        return []

def filter_new_tracks(tracks):
    """Filter out tracks that already exist in the tracks table using hash-based ID lookup"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'tracks')
        table = dynamodb.Table(table_name)

        new_tracks = []

        for track in tracks:
            # Track should already have a track_id from normalize_track_data
            track_id = track.get('track_id')
            title = track.get('title', '').strip()
            artist = track.get('artist', '').strip()

            if not title or not artist:
                continue

            # If track_id is missing, generate it
            if not track_id:
                track_id = generate_track_id(title, artist)
                track['track_id'] = track_id

            # Check if track exists using direct ID lookup (much more efficient than scanning)
            try:
                existing_track = check_track_exists_by_id(track_id, table)

                if not existing_track:
                    new_tracks.append(track)
                    print(f"New track found: {title} - {artist} (ID: {track_id[:8]}...)")
                else:
                    print(f"Track already exists: {title} - {artist} (ID: {track_id[:8]}...)")

            except Exception as e:
                print(f"Error checking track existence for {title} - {artist}: {str(e)}")
                # If there's an error checking, include the track to be safe
                new_tracks.append(track)

        return new_tracks

    except Exception as e:
        print(f"Error filtering tracks: {str(e)}")
        return tracks  # Return all tracks if filtering fails

def publish_tracks_to_sns(tracks, source_file):
    """Publish new tracks to SNS queue for further processing"""
    try:
        sns_client = boto3.client('sns')
        topic_arn = os.environ.get('NEW_TRACKS_TOPIC_ARN')

        if not topic_arn:
            print("No SNS topic ARN configured")
            return 0

        published_count = 0

        for track in tracks:
            try:
                # Create SNS message
                message = {
                    'track': track,
                    'source_file': source_file,
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'process_new_track'
                }

                # Publish to SNS
                response = sns_client.publish(
                    TopicArn=topic_arn,
                    Message=json.dumps(message),
                    Subject=f"New track: {track.get('title', 'Unknown')} - {track.get('artist', 'Unknown')}",
                    MessageAttributes={
                        'source_file': {
                            'DataType': 'String',
                            'StringValue': source_file
                        },
                        'track_title': {
                            'DataType': 'String',
                            'StringValue': track.get('title', 'Unknown')
                        },
                        'track_artist': {
                            'DataType': 'String',
                            'StringValue': track.get('artist', 'Unknown')
                        }
                    }
                )

                published_count += 1
                print(f"Published track to SNS: {track.get('title')} - {track.get('artist')}")

            except Exception as e:
                print(f"Error publishing track to SNS: {str(e)}")

        return published_count

    except Exception as e:
        print(f"Error publishing tracks to SNS: {str(e)}")
        return 0

if __name__ == "__main__":
    # Test with a sample S3 event
    test_event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "test-charts-bucket"},
                    "object": {"key": "beatport/2024/07/30/top100-120000.json"}
                }
            }
        ]
    }

    print(json.dumps(lambda_handler(test_event, None), indent=2))
