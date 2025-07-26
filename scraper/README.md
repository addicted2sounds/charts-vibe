# Beatport Top-100 Scraper

This Lambda function scrapes the Beatport Top-100 chart and returns structured track data. It also stores the complete playlist data in S3 for historical tracking and analysis.

## Features

- Scrapes track information from Beatport's top-100 page
- Extracts track details including title, artist, label, BPM, key, etc.
- Stores individual tracks in DynamoDB for search and retrieval
- Stores complete playlist snapshots in S3 with timestamps
- Handles multiple HTML structures and fallback methods
- Returns JSON response with track list and storage locations

## Architecture

The scraper now has dual storage functionality:
- **DynamoDB**: Individual track records for fast querying and search
- **S3**: Complete playlist snapshots for historical analysis and backup

## Storage Structure

### S3 Playlist Storage
Playlists are stored in S3 with the following structure:
```
s3://bucket-name/beatport/YYYY/MM/DD/top100-HHMMSS.json
```

### Playlist Data Format
```json
{
  "playlist_id": "beatport-top100-20250726-120000",
  "name": "Beatport Top 100",
  "description": "Top 100 tracks scraped from Beatport",
  "source": "beatport",
  "source_url": "https://www.beatport.com/top-100",
  "created_at": "2025-07-26T12:00:00Z",
  "track_count": 100,
  "tracks": [...],
  "metadata": {
    "scraper_version": "1.0",
    "scraped_at": "2025-07-26T12:00:00Z",
    "total_tracks_found": 100,
    "successfully_stored_in_db": 95
  }
}

## Response Format

```json
{
  "statusCode": 200,
  "body": {
    "total_tracks": 100,
    "tracks": [
      {
        "position": 1,
        "title": "Track Title",
        "artist": "Artist Name",
        "remix": "Remix Info",
        "label": "Record Label",
        "genre": "Genre",
        "bpm": 128,
        "key": "A minor",
        "release_date": "2023-01-01",
        "beatport_id": "12345",
        "url": "https://www.beatport.com/track/track/12345"
      }
    ],
    "stored_in_db": 95,
    "source": "beatport-top-100",
    "scraped_at": "request-id",
    "playlist": {
      "id": "beatport-top100-20250726-120000",
      "s3_location": {
        "bucket": "music-search-playlists",
        "key": "beatport/2025/07/26/top100-120000.json",
        "url": "s3://music-search-playlists/beatport/2025/07/26/top100-120000.json"
      }
    }
  }
}
```

## Environment Variables

The function uses the following environment variables:
- `TRACKS_TABLE`: DynamoDB table name for individual track storage
- `PLAYLISTS_BUCKET`: S3 bucket name for playlist storage
- `USER_AGENT`: Browser user agent for web requests

## Local Testing

To test the function locally:

```bash
cd scraper
pip install -r requirements.txt

# Test basic scraping functionality
python app.py

# Test S3 storage functionality (requires AWS credentials)
python test_s3_storage.py
```

## Deployment

The function is configured in the main `template.yaml` with:
- 30-second timeout to allow for web scraping
- S3 permissions for playlist storage
- DynamoDB permissions for track storage
- Environment variables for bucket and table names

## Error Handling

- Returns 500 status code with error message if scraping fails
- Includes request timeout and retry logic
- Gracefully handles missing track data
- Continues operation even if S3 storage fails (tracks are still stored in DynamoDB)

## Data Retention

- **S3**: Playlist snapshots are versioned and kept with lifecycle rules (old versions expire after 30 days)
- **DynamoDB**: Individual track records are persistent for querying and search

## Notes

- Uses proper User-Agent headers to avoid blocking
- Implements multiple fallback strategies for data extraction
- Respects Beatport's robots.txt and rate limiting
- S3 bucket has public access blocked for security
- Playlist files are stored with metadata including scrape timestamps
