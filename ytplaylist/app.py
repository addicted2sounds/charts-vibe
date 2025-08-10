import json
import boto3
import os
import sys
from datetime import datetime
import uuid
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add the common directory to the path to import ssm_credentials
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common'))
from ssm_credentials import SSMCredentialsManager

def lambda_handler(event, context):
    """
    Create a public YouTube playlist from video IDs

    Expected event:
    {
        "playlist_name": "My Public Playlist",
        "video_ids": ["video_id_1", "video_id_2", "video_id_3"],
        "description": "Optional description"
    }
    """
    try:
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
        playlist_id = create_public_playlist(
            youtube_service,
            playlist_name,
            description
        )

        if not playlist_id:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to create playlist'})
            }

        # Add videos to playlist
        added_videos, failed_videos = add_videos_to_playlist(youtube_service, playlist_id, video_ids)

        # Return playlist URLs without saving anything
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
        access_token = os.environ.get('YOUTUBE_ACCESS_TOKEN')
        if not access_token:
            # Try Parameter Store as fallback
            try:
                oauth_tokens = get_oauth_tokens_from_store()
                if oauth_tokens:
                    access_token = oauth_tokens.get('access_token')
            except:
                pass

        if access_token:
            credentials = Credentials(
                token=access_token,
                token_uri=client_secrets['token_uri'],
                client_id=client_secrets['client_id'],
                client_secret=client_secrets['client_secret']
            )

            youtube = build('youtube', 'v3', credentials=credentials)
            return youtube

        print("No access token found. You need to complete OAuth flow first.")
        return None

    except Exception as e:
        print(f"Error getting YouTube service: {str(e)}")
        return None

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
            except ssm.exceptions.ParameterNotFound:
                if 'access_token' in param_name:
                    return None  # Access token is required

        return tokens if tokens.get('access_token') else None

    except Exception as e:
        print(f"Error getting OAuth tokens: {str(e)}")
        return None

def load_client_secrets_from_ssm():
    """Load client secrets from SSM Parameter Store"""
    try:
        ssm_manager = SSMCredentialsManager()
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
        print(f"YouTube API error creating playlist: {str(e)}")
        return None
    except Exception as e:
        print(f"Error creating playlist: {str(e)}")
        return None

def add_videos_to_playlist(youtube_service, playlist_id, video_ids):
    """Add videos to YouTube playlist and return success/failure counts"""
    added_count = 0
    failed_videos = []

    for i, video_id in enumerate(video_ids):
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

        except HttpError as e:
            error_details = {
                'video_id': video_id,
                'position': i + 1,
                'error': str(e)
            }
            failed_videos.append(error_details)
            print(f"Error adding video {video_id}: {str(e)}")
            continue
        except Exception as e:
            error_details = {
                'video_id': video_id,
                'position': i + 1,
                'error': f'Unexpected error: {str(e)}'
            }
            failed_videos.append(error_details)
            print(f"Unexpected error adding video {video_id}: {str(e)}")
            continue

    return added_count, failed_videos

# Test function
if __name__ == "__main__":
    # Test with sample video IDs
    test_event = {
        "playlist_name": "Test Public Playlist",
        "video_ids": [
            "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
            "kJQP7kiw5Fk",  # Luis Fonsi - Despacito
            "JGwWNGJdvx8"   # Ed Sheeran - Shape of You
        ],
        "description": "A test playlist with popular songs"
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
