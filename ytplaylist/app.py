import json
import boto3
import os
import time
import random
from datetime import datetime
import uuid
from decimal import Decimal
from botocore.exceptions import ClientError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ssm_credentials import SSMCredentialsManager

RATE_LIMIT_REASONS = {
    'quotaExceeded',
    'dailyLimitExceeded',
    'userRateLimitExceeded',
    'rateLimitExceeded'
}

RATE_LIMIT_STATUSES = {429}


class RateLimitError(Exception):
    """Raised when the YouTube API signals a rate limit/quota error."""
    def __init__(self, message, status=None, reason=None):
        super().__init__(message)
        self.status = status
        self.reason = reason


def is_rate_limit_error(status, reason):
    """Return True when the error indicates a rate limit/quota issue."""
    if status in RATE_LIMIT_STATUSES:
        return True
    if reason and reason in RATE_LIMIT_REASONS:
        return True
    return False


def get_playlists_table():
    """Return the DynamoDB playlists table."""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('PLAYLISTS_TABLE', 'charts-vibe-playlists')
    return dynamodb.Table(table_name)


def build_playlist_record(
    playlist_id,
    playlist_name,
    description,
    status,
    source_type,
    created_at,
    s3_bucket=None,
    s3_key=None,
    job_id=None,
    source_playlist_id=None,
    total_tracks=None,
    tracks_with_video_ids=None
):
    record = {
        'playlist_id': playlist_id,
        'created_at': created_at,
        'status': status,
        'playlist_name': playlist_name,
        'description': description,
        'source_type': source_type
    }

    if s3_bucket:
        record['s3_bucket'] = s3_bucket
    if s3_key:
        record['s3_key'] = s3_key
    if job_id:
        record['job_id'] = job_id
    if source_playlist_id:
        record['source_playlist_id'] = source_playlist_id
    if total_tracks is not None:
        record['total_tracks'] = total_tracks
    if tracks_with_video_ids is not None:
        record['tracks_with_video_ids'] = tracks_with_video_ids

    record['videos_added'] = 0
    return record


def put_playlist_record(record):
    """Create a playlist record if it does not already exist."""
    try:
        table = get_playlists_table()
        table.put_item(
            Item=record,
            ConditionExpression='attribute_not_exists(playlist_id)'
        )
        return True
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            print(f"Playlist record already exists for {record.get('playlist_id')}")
            return False
        raise


def update_playlist_record(
    playlist_id,
    status,
    added_videos=0,
    failed_videos=None,
    resume_from=None,
    last_error=None,
    last_error_reason=None,
    last_error_status=None,
    completed_at=None,
    rate_limited_at=None
):
    """Update playlist record with minimal writes."""
    table = get_playlists_table()
    now = datetime.utcnow().isoformat()
    failed_videos = failed_videos or []

    expression_values = {
        ':status': status,
        ':updated_at': now,
        ':added_inc': int(added_videos),
        ':failed_count': len(failed_videos)
    }
    expression_names = {
        '#status': 'status'
    }

    set_parts = [
        '#status = :status',
        'updated_at = :updated_at',
        'failed_videos_count = :failed_count'
    ]

    if failed_videos:
        expression_values[':failed_sample'] = failed_videos[:10]
        set_parts.append('failed_videos_sample = :failed_sample')

    if resume_from is not None:
        expression_values[':resume_from'] = int(resume_from)
        set_parts.append('resume_from = :resume_from')

    if last_error:
        expression_values[':last_error'] = str(last_error)
        set_parts.append('last_error = :last_error')

    if last_error_reason:
        expression_values[':last_error_reason'] = str(last_error_reason)
        set_parts.append('last_error_reason = :last_error_reason')

    if last_error_status is not None:
        expression_values[':last_error_status'] = int(last_error_status)
        set_parts.append('last_error_status = :last_error_status')

    if completed_at:
        expression_values[':completed_at'] = completed_at
        set_parts.append('completed_at = :completed_at')

    if rate_limited_at:
        expression_values[':rate_limited_at'] = rate_limited_at
        set_parts.append('rate_limited_at = :rate_limited_at')

    update_expression = f"SET {', '.join(set_parts)} ADD videos_added :added_inc"

    table.update_item(
        Key={'playlist_id': playlist_id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_names,
        ExpressionAttributeValues=expression_values
    )


def safe_update_playlist_record(**kwargs):
    """Update playlist record but don't fail the playlist flow if storage is unavailable."""
    try:
        update_playlist_record(**kwargs)
    except Exception as e:
        print(f"Error updating playlist record: {str(e)}")


def to_serializable(value):
    """Convert Decimal values from DynamoDB into JSON-serializable native types."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: to_serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_serializable(item) for item in value]
    return value


def derive_playlist_name_from_s3_key(s3_key):
    """Return a human-friendly playlist name based on the S3 prefix."""
    if not s3_key:
        return f"Playlist created on {datetime.utcnow().strftime('%Y-%m-%d')}"

    prefix = s3_key.split("/", 1)[0].lower()
    if prefix == "beatport":
        return "Beatport Top 100"
    if prefix == "clubtone":
        return "Clubtone Top 100"

    return f"{prefix.title()} Playlist"

def lambda_handler(event, context):
    """
    Create a public YouTube playlist from S3 playlist data with enriched video IDs from DynamoDB

    Expected event formats:

    1. EventBridge event (from job completion):
    {
        "source": ["music-search.orchestrator"],
        "detail-type": ["Job Completed"],
        "detail": {
            "job_id": "uuid",
            "s3_bucket": "bucket-name",
            "s3_key": "path/to/file.json",
            "expected_count": 10,
            "processed_count": 10
        }
    }

    2. Direct API call with S3 data:
    {
        "s3_bucket": "charts-vibe-playlists",
        "s3_key": "beatport/2025/10/27/top100-060056.json",
        "playlist_name": "Beatport Top 100",
        "description": "2025/10/27 Beatport Top 100 Playlist"
    }

    3. Legacy direct video IDs format:
    {
        "playlist_name": "My Public Playlist",
        "video_ids": ["video_id_1", "video_id_2", "video_id_3"],
        "description": "Optional description"
    }

    4. Resume existing playlist creation:
    {
        "s3_bucket": "charts-vibe-playlists",
        "s3_key": "beatport/2025/10/27/top100-060056.json",
        "playlist_id": "PLxxxxxxxxxxxxxxxxxxxxxxx",
        "resume_from": 25
    }
    """
    try:
        # Check if this is an EventBridge event from job completion
        if event.get('source') == 'music-search.orchestrator' and event.get('detail-type') == 'Job Completed':
            print("Processing EventBridge job completion event")
            return handle_job_completed_event(event)

        # Check if using new S3-based format or legacy direct video IDs format
        s3_bucket = event.get('s3_bucket')
        s3_key = event.get('s3_key')

        if s3_bucket and s3_key:
            # New S3-based format
            return handle_s3_playlist_creation(event, s3_bucket, s3_key)
        else:
            # Legacy direct video IDs format
            return handle_direct_video_ids(event)

    except Exception as e:
        print(f"Error creating playlist: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            })
        }

def handle_job_completed_event(event):
    """Handle EventBridge job completion event and create playlist"""
    try:
        detail = event.get('detail', {})
        job_id = detail.get('job_id')
        s3_bucket = detail.get('s3_bucket')
        s3_key = detail.get('s3_key')

        if not s3_bucket or not s3_key:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing s3_bucket or s3_key in job completion event'})
            }

        print(f"Creating playlist for completed job {job_id} from s3://{s3_bucket}/{s3_key}")

        # Create playlist name based on source file and job completion
        base_name = event.get('playlist_name') or derive_playlist_name_from_s3_key(s3_key)
        playlist_name = f"{base_name} ({datetime.utcnow().strftime('%Y-%m-%d')})"
        description = event.get('description') or f"Automatically created playlist from job {job_id} completed on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}. Source: {s3_key}"

        # Use the same S3-based playlist creation logic
        modified_event = {
            's3_bucket': s3_bucket,
            's3_key': s3_key,
            'playlist_name': playlist_name,
            'description': description,
            'job_id': job_id  # Include for tracking
        }

        return handle_s3_playlist_creation(modified_event, s3_bucket, s3_key)

    except Exception as e:
        print(f"Error handling job completed event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Job completion event error: {str(e)}'})
        }

def handle_direct_video_ids(event):
    """Handle the legacy direct video IDs format"""
    # Parse request
    playlist_name = event.get('playlist_name')
    video_ids = event.get('video_ids', [])
    description = event.get('description', f'Public playlist created on {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}')

    if not playlist_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'playlist_name is required'})
        }

    if not video_ids or len(video_ids) == 0:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'video_ids array is required and cannot be empty'})
        }

    # Get YouTube service
    youtube_service = get_youtube_service()
    if not youtube_service:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to authenticate with YouTube'})
        }

    # Create public playlist
    try:
        playlist_id = create_public_playlist(
            youtube_service,
            playlist_name,
            description
        )
    except RateLimitError as e:
        print(f"Rate limit while creating playlist: {str(e)}")
        return {
            'statusCode': 429,
            'body': json.dumps({'error': 'Rate limit exceeded while creating playlist'})
        }

    if not playlist_id:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to create playlist'})
        }

    created_at = datetime.utcnow().isoformat()
    record = build_playlist_record(
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        description=description,
        status='in_progress',
        source_type='direct_video_ids',
        created_at=created_at,
        total_tracks=len(video_ids),
        tracks_with_video_ids=len(video_ids)
    )
    try:
        put_playlist_record(record)
    except Exception as e:
        print(f"Error writing playlist record: {str(e)}")

    # Add videos to playlist
    added_videos, failed_videos, stop_info = add_videos_to_playlist(
        youtube_service,
        playlist_id,
        video_ids
    )

    if stop_info and stop_info.get('reason') == 'rate_limited':
        safe_update_playlist_record(
            playlist_id=playlist_id,
            status='rate_limited',
            added_videos=added_videos,
            failed_videos=failed_videos,
            resume_from=stop_info.get('next_index'),
            last_error=stop_info.get('error'),
            last_error_reason=stop_info.get('error_reason'),
            last_error_status=stop_info.get('status'),
            rate_limited_at=datetime.utcnow().isoformat()
        )
        return {
            'statusCode': 429,
            'body': json.dumps({
                'success': False,
                'rate_limited': True,
                'playlist_id': playlist_id,
                'playlist_url': f'https://www.youtube.com/playlist?list={playlist_id}',
                'music_url': f'https://music.youtube.com/playlist?list={playlist_id}',
                'playlist_name': playlist_name,
                'total_videos_requested': len(video_ids),
                'videos_added_successfully': added_videos,
                'resume_from': stop_info.get('next_index'),
                'failed_videos': failed_videos
            })
        }

    safe_update_playlist_record(
        playlist_id=playlist_id,
        status='completed',
        added_videos=added_videos,
        failed_videos=failed_videos,
        completed_at=datetime.utcnow().isoformat()
    )

    # Return playlist URLs and summary
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'playlist_id': playlist_id,
            'playlist_url': f'https://www.youtube.com/playlist?list={playlist_id}',
            'music_url': f'https://music.youtube.com/playlist?list={playlist_id}',
            'playlist_name': playlist_name,
            'total_videos_requested': len(video_ids),
            'videos_added_successfully': added_videos,
            'failed_videos': failed_videos
        })
    }

def handle_s3_playlist_creation(event, s3_bucket, s3_key):
    """Handle S3-based playlist creation with DynamoDB enrichment"""
    try:
        # Download playlist data from S3
        playlist_data = download_playlist_from_s3(s3_bucket, s3_key)
        if not playlist_data:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Failed to download playlist data from S3'})
            }

        # Extract playlist metadata
        playlist_name = event.get('playlist_name') or playlist_data.get('name', 'Playlist from S3')
        description = event.get('description') or playlist_data.get('description',
                                                f'Playlist created from {s3_key} on {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}')

        # Extract tracks from playlist data
        tracks = playlist_data.get('tracks', [])
        if not tracks:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No tracks found in playlist data'})
            }

        print(f"Found {len(tracks)} tracks in playlist: {playlist_name}")

        # Get enriched track data with YouTube video IDs from DynamoDB
        enriched_tracks, video_ids, skipped_tracks = get_enriched_tracks_from_dynamodb(tracks)

        if not video_ids:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'No tracks with YouTube video IDs found in database',
                    'skipped_tracks': skipped_tracks
                })
            }

        print(f"Found {len(video_ids)} tracks with YouTube video IDs")

        resume_from_raw = event.get('resume_from')
        try:
            resume_from = int(resume_from_raw) if resume_from_raw is not None else 0
        except (TypeError, ValueError):
            resume_from = 0
        if resume_from < 0:
            resume_from = 0

        resume_requested = resume_from_raw is not None or event.get('resume') is True
        existing_playlist_id = event.get('playlist_id') if resume_requested else None

        # Get YouTube service
        youtube_service = get_youtube_service()
        if not youtube_service:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to authenticate with YouTube'})
            }

        if resume_from >= len(video_ids):
            if existing_playlist_id:
                safe_update_playlist_record(
                    playlist_id=existing_playlist_id,
                    status='completed',
                    added_videos=0,
                    failed_videos=[],
                    completed_at=datetime.utcnow().isoformat()
                )
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'playlist_id': existing_playlist_id,
                    'playlist_name': playlist_name,
                    'message': 'Playlist already complete',
                    'total_tracks_in_source': len(tracks),
                    'tracks_with_video_ids': len(video_ids),
                    'skipped_tracks': skipped_tracks
                })
            }

        if existing_playlist_id:
            playlist_id = existing_playlist_id
            print(f"Resuming playlist {playlist_id} from index {resume_from}")
        else:
            # Create public playlist
            try:
                playlist_id = create_public_playlist(
                    youtube_service,
                    playlist_name,
                    description
                )
            except RateLimitError as e:
                print(f"Rate limit while creating playlist: {str(e)}")
                return {
                    'statusCode': 429,
                    'body': json.dumps({'error': 'Rate limit exceeded while creating playlist'})
                }

            if not playlist_id:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Failed to create playlist'})
                }

        created_at = datetime.utcnow().isoformat()
        record = build_playlist_record(
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            description=description,
            status='in_progress',
            source_type='s3',
            created_at=created_at,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            job_id=event.get('job_id'),
            source_playlist_id=playlist_data.get('playlist_id'),
            total_tracks=len(tracks),
            tracks_with_video_ids=len(video_ids)
        )
        try:
            put_playlist_record(record)
        except Exception as e:
            print(f"Error writing playlist record: {str(e)}")

        # Add videos to playlist
        added_videos, failed_videos, stop_info = add_videos_to_playlist(
            youtube_service,
            playlist_id,
            video_ids,
            start_index=resume_from
        )

        if stop_info and stop_info.get('reason') == 'rate_limited':
            safe_update_playlist_record(
                playlist_id=playlist_id,
                status='rate_limited',
                added_videos=added_videos,
                failed_videos=failed_videos,
                resume_from=stop_info.get('next_index'),
                last_error=stop_info.get('error'),
                last_error_reason=stop_info.get('error_reason'),
                last_error_status=stop_info.get('status'),
                rate_limited_at=datetime.utcnow().isoformat()
            )
            return {
                'statusCode': 429,
                'body': json.dumps({
                    'success': False,
                    'rate_limited': True,
                    'playlist_id': playlist_id,
                    'playlist_url': f'https://www.youtube.com/playlist?list={playlist_id}',
                    'music_url': f'https://music.youtube.com/playlist?list={playlist_id}',
                    'playlist_name': playlist_name,
                    'job_id': event.get('job_id'),
                    's3_source': f's3://{s3_bucket}/{s3_key}',
                    'total_tracks_in_source': len(tracks),
                    'tracks_with_video_ids': len(video_ids),
                    'videos_added_successfully': added_videos,
                    'resume_from': stop_info.get('next_index'),
                    'failed_videos': failed_videos,
                    'skipped_tracks': skipped_tracks
                })
            }

        safe_update_playlist_record(
            playlist_id=playlist_id,
            status='completed',
            added_videos=added_videos,
            failed_videos=failed_videos,
            completed_at=datetime.utcnow().isoformat()
        )

        # Return detailed results
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'playlist_id': playlist_id,
                'playlist_url': f'https://www.youtube.com/playlist?list={playlist_id}',
                'music_url': f'https://music.youtube.com/playlist?list={playlist_id}',
                'playlist_name': playlist_name,
                'job_id': event.get('job_id'),  # Include job_id if available
                's3_source': f's3://{s3_bucket}/{s3_key}',
                'total_tracks_in_source': len(tracks),
                'tracks_with_video_ids': len(video_ids),
                'videos_added_successfully': added_videos,
                'failed_videos': failed_videos,
                'enriched_tracks': enriched_tracks,  # Include enriched track data for reference
                'skipped_tracks': skipped_tracks
            })
        }

    except Exception as e:
        print(f"Error handling S3 playlist creation: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'S3 playlist creation error: {str(e)}'})
        }

    except Exception as e:
        print(f"Error creating playlist: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            })
        }

def get_youtube_service():
    """Get authenticated YouTube service using credentials from SSM Parameter Store"""
    try:
        # Load client secrets from SSM Parameter Store
        client_secrets = load_client_secrets_from_ssm()
        if not client_secrets:
            print("No client secrets found in SSM Parameter Store")
            return None

        # Try to get existing tokens from environment or Parameter Store
        oauth_tokens = get_oauth_tokens_from_store()
        if not oauth_tokens:
            print("No OAuth tokens found in Parameter Store")
            return None

        credentials = refresh_youtube_credentials(client_secrets, oauth_tokens)
        if not credentials:
            return None

        print("Creating YouTube service with refreshed credentials")
        youtube = build('youtube', 'v3', credentials=credentials)
        return youtube

    except Exception as e:
        print(f"Error getting YouTube service: {str(e)}")
        return None

def refresh_youtube_credentials(client_secrets, oauth_tokens):
    """Refresh the YouTube access token and persist the updated tokens to SSM."""
    access_token = oauth_tokens.get('access_token')
    refresh_token = oauth_tokens.get('refresh_token')

    if refresh_token == "NOT_SET" or not refresh_token:
        print("Refresh token is not configured. Please run 'python ytplaylist/oauth_setup.py' to complete OAuth flow.")
        return None

    if access_token == "NOT_SET":
        print("Stored access token is a placeholder; refreshing it before use")
        access_token = None

    print(f"Found access_token: {'Yes' if access_token else 'No'}")
    print(f"Found refresh_token: {'Yes' if refresh_token else 'No'}")

    try:
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=client_secrets['token_uri'],
            client_id=client_secrets['client_id'],
            client_secret=client_secrets['client_secret']
        )

        print("Refreshing YouTube access token")
        credentials.refresh(Request())

        refreshed_access_token = credentials.token
        refreshed_refresh_token = credentials.refresh_token or refresh_token

        if not refreshed_access_token:
            print("Token refresh succeeded but no access token was returned")
            return None

        print("YouTube access token refreshed successfully")

        if not persist_oauth_tokens_to_store(
            refreshed_access_token,
            refreshed_refresh_token,
            existing_refresh_token=refresh_token
        ):
            return None

        return credentials
    except Exception as e:
        print(f"Failed to refresh YouTube OAuth token: {str(e)}")
        print("Re-run 'python ytplaylist/oauth_setup.py' if the refresh token is no longer valid.")
        return None

def persist_oauth_tokens_to_store(access_token, refresh_token, existing_refresh_token=None):
    """Persist refreshed OAuth tokens to SSM Parameter Store."""
    if not access_token:
        print("Cannot persist refreshed OAuth tokens without an access token")
        return False

    try:
        ssm = boto3.client('ssm')
        ssm.put_parameter(
            Name='/youtube/access_token',
            Value=access_token,
            Type='SecureString',
            Description='YouTube OAuth2 Access Token',
            Overwrite=True
        )
        print("Persisted refreshed access token to Parameter Store")

        if refresh_token and refresh_token != existing_refresh_token:
            ssm.put_parameter(
                Name='/youtube/refresh_token',
                Value=refresh_token,
                Type='SecureString',
                Description='YouTube OAuth2 Refresh Token',
                Overwrite=True
            )
            print("Persisted rotated refresh token to Parameter Store")
        else:
            print("Refresh token unchanged; skipping Parameter Store update")

        return True
    except Exception as e:
        print(f"Failed to persist refreshed OAuth tokens: {str(e)}")
        return False

def get_oauth_tokens_from_store():
    """Get OAuth tokens from Parameter Store"""
    try:
        ssm = boto3.client('ssm')

        tokens = {}
        token_params = [
            '/youtube/access_token',
            '/youtube/refresh_token'
        ]

        for param_name in token_params:
            try:
                response = ssm.get_parameter(Name=param_name, WithDecryption=True)
                key = param_name.split('/')[-1]
                tokens[key] = response['Parameter']['Value']
                print(f"Successfully retrieved {key} from Parameter Store")
            except ssm.exceptions.ParameterNotFound:
                print(f"Parameter {param_name} not found in Parameter Store")

        return tokens if tokens.get('refresh_token') else None

    except Exception as e:
        print(f"Error getting OAuth tokens: {str(e)}")
        return None

def load_client_secrets_from_ssm():
    """Load client secrets from SSM Parameter Store"""
    try:
        # Use /youtube prefix to match the setup script and app expectations
        ssm_manager = SSMCredentialsManager(ssm_prefix="/youtube")
        config = ssm_manager.get_google_oauth_config()
        return config['installed']
    except Exception as e:
        print(f"Error loading client secrets from SSM: {str(e)}")
        return None

def load_client_secrets():
    """
    DEPRECATED: Load client secrets from client_secret.json file
    This function is kept for backward compatibility but should not be used.
    Use load_client_secrets_from_ssm() instead.
    """
    print("WARNING: load_client_secrets() is deprecated. The client_secret.json file should not exist in production.")
    print("Use SSM Parameter Store instead by calling load_client_secrets_from_ssm()")

    try:
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        client_secrets_path = os.path.join(current_dir, 'client_secret.json')

        with open(client_secrets_path, 'r') as f:
            client_secrets = json.load(f)

        return client_secrets['installed']

    except FileNotFoundError:
        print("client_secret.json file not found")
        return None
    except json.JSONDecodeError:
        print("Invalid JSON in client_secret.json")
        return None
    except KeyError:
        print("Invalid structure in client_secret.json")
        return None
    except Exception as e:
        print(f"Error loading client secrets: {str(e)}")
        return None

def get_stored_credentials():
    """Retrieve stored YouTube credentials from AWS Parameter Store"""
    try:
        ssm = boto3.client('ssm')

        # Get credentials from Parameter Store
        required_params = [
            '/youtube/client_id',
            '/youtube/client_secret',
            '/youtube/access_token'
        ]

        optional_params = [
            '/youtube/refresh_token'
        ]

        credentials = {}

        # Get required parameters
        for param_name in required_params:
            try:
                response = ssm.get_parameter(Name=param_name, WithDecryption=True)
                key = param_name.split('/')[-1]
                credentials[key] = response['Parameter']['Value']
            except ssm.exceptions.ParameterNotFound:
                print(f"Required parameter {param_name} not found")
                return None

        # Get optional parameters
        for param_name in optional_params:
            try:
                response = ssm.get_parameter(Name=param_name, WithDecryption=True)
                key = param_name.split('/')[-1]
                credentials[key] = response['Parameter']['Value']
            except ssm.exceptions.ParameterNotFound:
                print(f"Optional parameter {param_name} not found")

        return credentials

    except Exception as e:
        print(f"Error retrieving credentials: {str(e)}")
        return None

def create_public_playlist(youtube_service, title, description):
    """Create a public YouTube playlist"""
    try:
        playlist_body = {
            'snippet': {
                'title': title,
                'description': description,
                'defaultLanguage': 'en'
            },
            'status': {
                'privacyStatus': 'public'  # Make playlist public
            }
        }

        response = youtube_service.playlists().insert(
            part='snippet,status',
            body=playlist_body
        ).execute()

        playlist_id = response['id']
        print(f"Created public playlist: {playlist_id}")
        return playlist_id

    except HttpError as e:
        status = getattr(e.resp, 'status', None)
        reason = extract_youtube_error_reason(e)
        if is_rate_limit_error(status, reason):
            raise RateLimitError("YouTube API rate limit while creating playlist", status=status, reason=reason)
        print(f"YouTube API error creating playlist: {str(e)}")
        return None
    except Exception as e:
        print(f"Error creating playlist: {str(e)}")
        return None

def add_videos_to_playlist(youtube_service, playlist_id, video_ids, start_index=0, stop_on_rate_limit=True):
    """Add videos to YouTube playlist with retries for transient API failures"""
    added_count = 0
    failed_videos = []
    stop_info = None
    max_retries = int(os.environ.get('YT_PLAYLIST_MAX_RETRIES', '5'))
    base_sleep = float(os.environ.get('YT_PLAYLIST_RETRY_BASE_SECONDS', '1'))
    max_sleep = float(os.environ.get('YT_PLAYLIST_RETRY_MAX_SECONDS', '10'))

    if start_index < 0:
        start_index = 0
    if start_index > len(video_ids):
        start_index = len(video_ids)

    for i in range(start_index, len(video_ids)):
        video_id = video_ids[i]
        attempt = 0

        while True:
            try:
                playlist_item_body = {
                    'snippet': {
                        'playlistId': playlist_id,
                        'position': i,  # Maintain order
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        }
                    }
                }

                youtube_service.playlistItems().insert(
                    part='snippet',
                    body=playlist_item_body
                ).execute()

                added_count += 1
                print(f"Added video {video_id} to playlist (position {i+1})")
                break

            except HttpError as e:
                status = getattr(e.resp, 'status', None)
                reason = extract_youtube_error_reason(e)
                attempt += 1

                if stop_on_rate_limit and is_rate_limit_error(status, reason):
                    error_details = {
                        'video_id': video_id,
                        'position': i + 1,
                        'error': str(e),
                        'status': status,
                        'reason': reason,
                        'attempts': attempt,
                        'rate_limited': True
                    }
                    failed_videos.append(error_details)
                    stop_info = {
                        'reason': 'rate_limited',
                        'status': status,
                        'error_reason': reason,
                        'error': str(e),
                        'video_id': video_id,
                        'next_index': i
                    }
                    print(f"Rate limit hit while adding video {video_id}: {str(e)} (status={status}, reason={reason})")
                    return added_count, failed_videos, stop_info

                retryable = is_retryable_youtube_error(status, reason)

                if attempt > max_retries or not retryable:
                    error_details = {
                        'video_id': video_id,
                        'position': i + 1,
                        'error': str(e),
                        'status': status,
                        'reason': reason,
                        'attempts': attempt
                    }
                    failed_videos.append(error_details)
                    print(f"Error adding video {video_id}: {str(e)} (status={status}, reason={reason}, attempts={attempt})")
                    break

                sleep_time = min(max_sleep, base_sleep * (2 ** (attempt - 1)))
                sleep_time += random.uniform(0, 0.5)  # jitter
                print(f"Retrying video {video_id} (attempt {attempt}/{max_retries}) after {sleep_time:.2f}s due to {status} / {reason}")
                time.sleep(sleep_time)
                continue

            except Exception as e:
                attempt += 1
                if attempt > max_retries:
                    error_details = {
                        'video_id': video_id,
                        'position': i + 1,
                        'error': f'Unexpected error: {str(e)}',
                        'attempts': attempt
                    }
                    failed_videos.append(error_details)
                    print(f"Unexpected error adding video {video_id}: {str(e)} (attempts={attempt})")
                    break

                sleep_time = min(max_sleep, base_sleep * (2 ** (attempt - 1)))
                sleep_time += random.uniform(0, 0.5)
                print(f"Retrying video {video_id} after unexpected error (attempt {attempt}/{max_retries}) in {sleep_time:.2f}s: {str(e)}")
                time.sleep(sleep_time)
                continue

    return added_count, failed_videos, stop_info

def extract_youtube_error_reason(error):
    """Best-effort extraction of reason string from HttpError"""
    try:
        if hasattr(error, 'content') and error.content:
            content = error.content
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')
            data = json.loads(content)
            errors = data.get('error', {}).get('errors', [])
            if errors and isinstance(errors, list):
                return errors[0].get('reason')
    except Exception:
        pass
    return None

def is_retryable_youtube_error(status, reason):
    """Identify transient errors that should be retried"""
    retryable_statuses = {409, 500, 502, 503, 504}
    retryable_reasons = {
        'backendError',
        'internalError',
        'serviceUnavailable',
        'SERVICE_UNAVAILABLE',
        'playlistItemAlreadyExists',
    }

    if status in retryable_statuses:
        return True

    if reason and reason in retryable_reasons:
        return True

    return False

def download_playlist_from_s3(bucket_name, object_key):
    """Download and parse playlist data from S3"""
    try:
        s3_client = boto3.client('s3')
        print(f"Downloading playlist data from s3://{bucket_name}/{object_key}")

        # Download the file
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        file_content = response['Body'].read().decode('utf-8')

        # Parse JSON content
        playlist_data = json.loads(file_content)
        return playlist_data

    except Exception as e:
        print(f"Error downloading playlist from S3: {str(e)}")
        return None

def get_enriched_tracks_from_dynamodb(tracks):
    """
    Query DynamoDB to get enriched track data with YouTube video IDs

    Args:
        tracks: List of track data from playlist

    Returns:
        tuple: (enriched_tracks, video_ids) where enriched_tracks contains full track data
               and video_ids is a list of YouTube video IDs for playlist creation
    """
    try:
        # Initialize DynamoDB
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TRACKS_TABLE', 'charts-vibe-tracks')
        table = dynamodb.Table(table_name)

        enriched_tracks = []
        video_ids = []
        skipped_tracks = []

        for track in tracks:
            try:
                title = (track.get('title') or '').strip()
                artist = (track.get('artist') or '').strip()
                track_id = (track.get('track_id') or '').strip()

                if not title or not artist:
                    print(f"Skipping track with missing title or artist: {track}")
                    skipped_tracks.append({
                        'track': to_serializable(track),
                        'reason': 'missing title or artist'
                    })
                    continue

                if not track_id:
                    print(f"Skipping track with missing track_id: {title} - {artist}")
                    skipped_tracks.append({
                        'track': to_serializable(track),
                        'reason': 'missing track_id'
                    })
                    continue

                # Query DynamoDB for the track using the track_id from playlist JSON
                response = table.get_item(Key={'track_id': track_id})

                if 'Item' in response:
                    db_track = response['Item']
                    youtube_video_id = db_track.get('youtube_video_id')

                    if youtube_video_id:
                        # Track found with YouTube video ID
                        enriched_track = {
                            'source_track': to_serializable(track),  # Original track from playlist
                            'db_track': to_serializable(dict(db_track)),  # Convert DynamoDB item to JSON-safe dict
                            'title': title,
                            'artist': artist,
                            'track_id': track_id,
                            'youtube_video_id': youtube_video_id,
                            'youtube_url': db_track.get('youtube_url', f'https://www.youtube.com/watch?v={youtube_video_id}')
                        }
                        enriched_tracks.append(enriched_track)
                        video_ids.append(youtube_video_id)
                        print(f"Found YouTube video ID for: {title} - {artist} (ID: {track_id[:8]}...) -> {youtube_video_id}")
                    else:
                        print(f"Track found in DB but no YouTube video ID: {title} - {artist} (ID: {track_id[:8]}...)")
                        skipped_tracks.append({
                            'track': to_serializable(track),
                            'reason': 'youtube_video_id missing in database'
                        })
                else:
                    print(f"Track not found in database: {title} - {artist} (ID: {track_id[:8]}...)")
                    skipped_tracks.append({
                        'track': to_serializable(track),
                        'reason': 'track not found in database'
                    })

            except Exception as e:
                print(f"Error processing track {track}: {str(e)}")
                skipped_tracks.append({
                    'track': to_serializable(track),
                    'reason': f'error fetching from database: {str(e)}'
                })
                continue

        print(f"Enriched {len(enriched_tracks)} tracks with YouTube video IDs out of {len(tracks)} source tracks")
        return enriched_tracks, video_ids, skipped_tracks

    except Exception as e:
        print(f"Error enriching tracks from DynamoDB: {str(e)}")
        return [], [], [{'track': to_serializable(track), 'reason': 'unexpected error during enrichment'} for track in tracks]

# Test function
if __name__ == "__main__":
    print("Testing YouTube Playlist Lambda with both formats...")

    # Test 1: Legacy format with direct video IDs
    print("\n=== Test 1: Legacy Direct Video IDs Format ===")
    test_event_legacy = {
        "playlist_name": "Test Public Playlist - Legacy",
        "video_ids": [
            "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
            "kJQP7kiw5Fk",  # Luis Fonsi - Despacito
            "JGwWNGJdvx8"   # Ed Sheeran - Shape of You
        ],
        "description": "A test playlist with popular songs using legacy format"
    }

    result_legacy = lambda_handler(test_event_legacy, None)
    print(json.dumps(result_legacy, indent=2))

    # Test 2: New S3-based format (this will fail without actual S3 data, but shows structure)
    print("\n=== Test 2: New S3-based Format ===")
    test_event_s3 = {
        "s3_bucket": "charts-bucket",
        "s3_key": "beatport/2024/07/30/top100-120000.json",
        "playlist_name": "Beatport Top 100 Playlist",  # Optional override
        "description": "Top 100 tracks from Beatport chart with enriched YouTube data"
    }

    result_s3 = lambda_handler(test_event_s3, None)
    print(json.dumps(result_s3, indent=2))
