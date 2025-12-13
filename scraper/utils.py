"""
Common utilities for music search project
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone

import boto3


def generate_track_id(title, artist):
    """
    Generate a deterministic track ID based on normalized title and artist using SHA-256

    This function creates a consistent hash-based ID for tracks that allows
    efficient lookups and prevents duplicates based on title/artist combinations.

    Args:
        title (str): The track title
        artist (str): The track artist

    Returns:
        str: SHA-256 hash of the normalized title and artist
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


def store_playlist_in_s3(
    playlist_data,
    source_prefix,
    filename_prefix,
    metadata_source,
    playlist_type
):
    """
    Store playlist data in S3 under the provided prefix and filename stub.

    Returns an S3 location dict or None if storage fails.
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('PLAYLISTS_BUCKET')

        if not bucket_name:
            print("No S3 bucket configured for playlists")
            return None

        now = datetime.now(timezone.utc)
        date_path = now.strftime('%Y/%m/%d')
        time_suffix = now.strftime('%H%M%S')
        s3_key = f"{source_prefix}/{date_path}/{filename_prefix}-{time_suffix}.json"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(playlist_data, indent=2, default=str),
            ContentType='application/json',
            Metadata={
                'source': metadata_source,
                'playlist-type': playlist_type,
                'scraped-at': now.isoformat()
            }
        )

        return {
            'bucket': bucket_name,
            'key': s3_key,
            'url': f"s3://{bucket_name}/{s3_key}"
        }

    except Exception as e:
        print(f"Error storing playlist in S3: {str(e)}")
        return None


def normalize_track_data(track):
    """
    Normalize track data to a consistent format with generated track ID

    Args:
        track (dict): Raw track data

    Returns:
        dict: Normalized track data with generated track_id, or None if invalid
    """
    try:
        normalized = {}

        # Handle different track data structures
        if isinstance(track, dict):
            # Extract title
            title = track.get('title') or track.get('track') or track.get('name')
            if not title:
                return None
            normalized['title'] = str(title).strip()

            # Extract artist
            artist = track.get('artist') or track.get('artists')
            if isinstance(artist, list):
                artist = ', '.join([str(a) for a in artist])
            if not artist:
                return None
            normalized['artist'] = str(artist).strip()

            # Generate deterministic track ID
            normalized['track_id'] = generate_track_id(normalized['title'], normalized['artist'])

            # Extract optional fields
            normalized['album'] = track.get('album', '')
            normalized['genre'] = track.get('genre', '')
            normalized['label'] = track.get('label', '')
            normalized['bpm'] = track.get('bpm')
            normalized['key'] = track.get('key', '')
            normalized['rank'] = track.get('rank') or track.get('position')
            normalized['rating'] = track.get('rating')
            normalized['release_date'] = track.get('release_date') or track.get('released')
            normalized['beatport_url'] = track.get('beatport_url') or track.get('url')
            normalized['beatport_id'] = track.get('beatport_id') or track.get('id')

            # Store original data as metadata
            normalized['metadata'] = {
                'original_data': track,
                'source': 'chart-processor'
            }

            return normalized

    except Exception as e:
        print(f"Error normalizing track data: {str(e)}")
        return None
