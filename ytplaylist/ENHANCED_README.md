# YouTube Playlist Lambda - Enhanced with S3 and DynamoDB Integration

## Overview

The YouTube Playlist Lambda function has been enhanced to accept S3 playlist data and automatically enrich it with YouTube video IDs from DynamoDB. This creates a powerful pipeline where playlists stored in S3 can be automatically converted to YouTube playlists using pre-scraped and enriched track data.

## Key Features

### 🆕 New S3-Based Playlist Creation
- Accepts S3 bucket and key for playlist data
- Downloads and parses playlist JSON from S3
- Queries DynamoDB for enriched track data with YouTube video IDs
- Creates playlists using enriched data from the database

### 🔄 Backward Compatibility
- Still supports the original direct video IDs format
- Automatic detection of event format (S3 vs legacy)
- No breaking changes to existing implementations

### 🎯 Smart Track Matching
- Uses deterministic hash-based track IDs for efficient lookups
- Matches playlist tracks with database tracks using title/artist
- Filters out tracks without YouTube video IDs
- Provides detailed matching results

### 📊 Enhanced Response Data
- Returns both playlist creation results and enriched track data
- Includes source information (S3 path, track counts, etc.)
- Detailed success/failure reporting for each track

## Event Formats

### New S3-Based Format

```json
{
  "s3_bucket": "charts-vibe-bucket",
  "s3_key": "beatport/2024/07/30/top100-120000.json",
  "playlist_name": "Custom Playlist Name (optional)",
  "description": "Custom description (optional)"
}
```

### Legacy Direct Video IDs Format (Still Supported)

```json
{
  "playlist_name": "My Public Playlist",
  "video_ids": ["dQw4w9WgXcQ", "kJQP7kiw5Fk", "JGwWNGJdvx8"],
  "description": "Optional description"
}
```

## Expected S3 Playlist Data Structure

The function expects S3 files to contain playlist data in this format (typically produced by the chart-processor lambda):

```json
{
  "playlist_id": "beatport-top100-20240730",
  "name": "Beatport Top 100",
  "description": "Top 100 tracks from Beatport",
  "source": "beatport",
  "created_at": "2024-07-30T12:00:00.000Z",
  "track_count": 100,
  "tracks": [
    {
      "title": "Song Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "genre": "Electronic",
      "rank": 1,
      "beatport_id": "123456",
      "beatport_url": "https://www.beatport.com/track/...",
      "release_date": "2024-07-15"
    }
  ]
}
```

## Function Flow

### S3-Based Flow
1. **Event Detection**: Detects S3-based event format (`s3_bucket` + `s3_key`)
2. **S3 Download**: Downloads playlist JSON from specified S3 location
3. **Track Extraction**: Extracts track list from playlist data
4. **DynamoDB Enrichment**:
   - Generates deterministic track IDs from title/artist
   - Queries DynamoDB tracks table for each track
   - Filters tracks that have YouTube video IDs
5. **Playlist Creation**: Creates YouTube playlist using enriched video IDs
6. **Response**: Returns detailed results with source info and enriched data

### Legacy Flow
1. **Event Detection**: Detects legacy format (`video_ids` present)
2. **Direct Processing**: Uses provided video IDs directly
3. **Playlist Creation**: Creates YouTube playlist as before
4. **Response**: Returns standard playlist creation results

## Response Format

### S3-Based Response
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "playlist_id": "PLrAK7zyaI-GWwM2G_MEE6aK6huiwVVzOt",
    "playlist_url": "https://www.youtube.com/playlist?list=PLrAK...",
    "music_url": "https://music.youtube.com/playlist?list=PLrAK...",
    "playlist_name": "Beatport Top 100",
    "s3_source": "s3://charts-vibe-bucket/beatport/2024/07/30/top100-120000.json",
    "total_tracks_in_source": 100,
    "tracks_with_video_ids": 75,
    "videos_added_successfully": 72,
    "failed_videos": [
      {
        "video_id": "invalid_id",
        "position": 23,
        "error": "Video not found"
      }
    ],
    "enriched_tracks": [
      {
        "source_track": {
          "title": "Strobe",
          "artist": "deadmau5",
          "rank": 1
        },
        "db_track": {
          "track_id": "abc123...",
          "title": "Strobe",
          "artist": "deadmau5",
          "youtube_video_id": "tKi9Z-f6qX4",
          "youtube_url": "https://www.youtube.com/watch?v=tKi9Z-f6qX4",
          "genre": "Progressive House",
          "bpm": 128
        },
        "youtube_video_id": "tKi9Z-f6qX4"
      }
    ]
  }
}
```

## Environment Variables

- `TRACKS_TABLE`: DynamoDB table name (default: 'tracks')
- `YOUTUBE_ACCESS_TOKEN`: YouTube API access token
- YouTube OAuth parameters stored in AWS Systems Manager Parameter Store

## Dependencies

Add to `requirements.txt`:
```
boto3
google-auth
google-auth-oauthlib
google-api-python-client
```

## Error Handling

### Common Error Scenarios
- **S3 Access Errors**: Invalid bucket/key, permissions issues
- **DynamoDB Errors**: Table not found, access denied
- **YouTube API Errors**: Invalid video IDs, quota exceeded, authentication failures
- **Data Format Errors**: Malformed playlist data, missing required fields

### Error Response Format
```json
{
  "statusCode": 400/500,
  "body": {
    "success": false,
    "error": "Detailed error message"
  }
}
```

## Integration with Existing Pipeline

This enhanced function integrates seamlessly with the existing music search pipeline:

1. **Scraper Lambda** → Scrapes chart data → Stores in S3
2. **Chart Processor Lambda** → Processes S3 files → Stores tracks in DynamoDB
3. **YouTube Music Lambda** → Enriches tracks → Adds YouTube video IDs to DynamoDB
4. **🆕 Enhanced Playlist Lambda** → Creates playlists from S3 data → Uses enriched DynamoDB data

## Usage Examples

### Create Playlist from Chart Data
```python
import boto3

lambda_client = boto3.client('lambda')

response = lambda_client.invoke(
    FunctionName='youtube-playlist-function',
    Payload=json.dumps({
        "s3_bucket": "charts-vibe-bucket",
        "s3_key": "beatport/top100/2024-07-30.json"
    })
)
```

### Create Playlist with Custom Name
```python
response = lambda_client.invoke(
    FunctionName='youtube-playlist-function',
    Payload=json.dumps({
        "s3_bucket": "charts-vibe-bucket",
        "s3_key": "beatport/top100/2024-07-30.json",
        "playlist_name": "My Weekly Electronic Mix",
        "description": "Best electronic tracks from this week"
    })
)
```

## Testing

Run the test suite to verify functionality:

```bash
python test_playlist_structure.py
```

This tests:
- Event format detection
- Track matching logic
- S3 data structure parsing
- Error handling scenarios

## Future Enhancements

- **Batch Processing**: Process multiple S3 files in one invocation
- **Playlist Templates**: Support for playlist templates and themes
- **Track Filtering**: Add genre, BPM, or other metadata-based filtering
- **Playlist Updates**: Support for updating existing playlists
- **Analytics**: Track playlist creation metrics and popular tracks
