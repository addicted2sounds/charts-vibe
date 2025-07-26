#!/usr/bin/env python3
"""
Helper script to list and retrieve playlist data from S3
"""
import boto3
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional

class PlaylistS3Manager:
    """Manages playlist data stored in S3"""

    def __init__(self, bucket_name: str = None):
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name or os.environ.get('PLAYLISTS_BUCKET')

        if not self.bucket_name:
            raise ValueError("Bucket name must be provided or set in PLAYLISTS_BUCKET environment variable")

    def list_playlists(self, date_prefix: str = None) -> List[Dict]:
        """
        List all playlists in S3, optionally filtered by date

        Args:
            date_prefix: Optional date filter in format 'YYYY/MM/DD' or 'YYYY/MM' or 'YYYY'

        Returns:
            List of playlist metadata dictionaries
        """
        try:
            prefix = 'beatport/'
            if date_prefix:
                prefix += date_prefix.rstrip('/') + '/'

            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            playlists = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.json'):
                        # Extract metadata
                        head_response = self.s3_client.head_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )

                        playlist_info = {
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'metadata': head_response.get('Metadata', {}),
                            's3_url': f"s3://{self.bucket_name}/{obj['Key']}"
                        }
                        playlists.append(playlist_info)

            return sorted(playlists, key=lambda x: x['last_modified'], reverse=True)

        except Exception as e:
            print(f"Error listing playlists: {str(e)}")
            return []

    def get_playlist(self, playlist_key: str) -> Optional[Dict]:
        """
        Retrieve a specific playlist by S3 key

        Args:
            playlist_key: S3 key of the playlist file

        Returns:
            Playlist data dictionary or None if not found
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=playlist_key
            )

            playlist_data = json.loads(response['Body'].read().decode('utf-8'))
            return playlist_data

        except Exception as e:
            print(f"Error retrieving playlist {playlist_key}: {str(e)}")
            return None

    def get_latest_playlist(self) -> Optional[Dict]:
        """Get the most recently scraped playlist"""
        playlists = self.list_playlists()
        if playlists:
            return self.get_playlist(playlists[0]['key'])
        return None

    def compare_playlists(self, playlist_key1: str, playlist_key2: str) -> Dict:
        """
        Compare two playlists and show differences

        Args:
            playlist_key1: S3 key of first playlist
            playlist_key2: S3 key of second playlist

        Returns:
            Dictionary containing comparison results
        """
        playlist1 = self.get_playlist(playlist_key1)
        playlist2 = self.get_playlist(playlist_key2)

        if not playlist1 or not playlist2:
            return {"error": "Could not retrieve one or both playlists"}

        tracks1 = {track['beatport_id']: track for track in playlist1.get('tracks', [])}
        tracks2 = {track['beatport_id']: track for track in playlist2.get('tracks', [])}

        # Find new, removed, and position changes
        new_tracks = [tracks2[tid] for tid in tracks2 if tid not in tracks1]
        removed_tracks = [tracks1[tid] for tid in tracks1 if tid not in tracks2]

        position_changes = []
        for tid in tracks1:
            if tid in tracks2:
                old_pos = tracks1[tid].get('position')
                new_pos = tracks2[tid].get('position')
                if old_pos != new_pos:
                    position_changes.append({
                        'track': tracks2[tid],
                        'old_position': old_pos,
                        'new_position': new_pos,
                        'change': new_pos - old_pos if old_pos and new_pos else None
                    })

        return {
            'playlist1': {
                'key': playlist_key1,
                'created_at': playlist1.get('created_at'),
                'track_count': playlist1.get('track_count')
            },
            'playlist2': {
                'key': playlist_key2,
                'created_at': playlist2.get('created_at'),
                'track_count': playlist2.get('track_count')
            },
            'new_tracks': new_tracks,
            'removed_tracks': removed_tracks,
            'position_changes': sorted(position_changes, key=lambda x: abs(x['change']) if x['change'] else 0, reverse=True)
        }

def main():
    """Example usage of the PlaylistS3Manager"""

    # Example: Set your bucket name
    # manager = PlaylistS3Manager('your-bucket-name')

    try:
        manager = PlaylistS3Manager()

        print("📋 Listing recent playlists...")
        playlists = manager.list_playlists()

        if not playlists:
            print("No playlists found in S3")
            return

        print(f"Found {len(playlists)} playlists:")
        for i, playlist in enumerate(playlists[:5]):  # Show first 5
            print(f"  {i+1}. {playlist['key']} ({playlist['last_modified']})")

        print("\n🎵 Getting latest playlist...")
        latest = manager.get_latest_playlist()
        if latest:
            print(f"Latest playlist: {latest['name']}")
            print(f"Created: {latest['created_at']}")
            print(f"Tracks: {latest['track_count']}")

            # Show top 5 tracks
            print("\nTop 5 tracks:")
            for track in latest.get('tracks', [])[:5]:
                print(f"  {track.get('position', '?')}. {track.get('artist', 'Unknown')} - {track.get('title', 'Unknown')}")

        # Example of comparing two playlists (if you have at least 2)
        if len(playlists) >= 2:
            print(f"\n🔄 Comparing latest two playlists...")
            comparison = manager.compare_playlists(playlists[0]['key'], playlists[1]['key'])
            if 'error' not in comparison:
                print(f"New tracks: {len(comparison['new_tracks'])}")
                print(f"Removed tracks: {len(comparison['removed_tracks'])}")
                print(f"Position changes: {len(comparison['position_changes'])}")

    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure to set the PLAYLISTS_BUCKET environment variable or pass bucket name to constructor")

if __name__ == "__main__":
    main()
