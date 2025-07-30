# Chart Processor Lambda Function

This Lambda function processes playlist files uploaded to the S3 playlists bucket by the scraper lambda, filters out tracks that already exist in the tracks table, and publishes new tracks to an SNS queue for further processing.

## Function Overview

The Chart Processor Function is triggered automatically when new JSON files are uploaded to the playlists S3 bucket. It performs the following operations:

1. **Download and Parse**: Downloads the playlist file from S3 and parses the JSON content
2. **Extract Tracks**: Extracts track information from the scraper lambda output format
3. **Filter Existing**: Queries the DynamoDB tracks table to filter out tracks that already exist
4. **Publish New Tracks**: Publishes new tracks to the SNS queue for downstream processing

## Supported Data Format

The function is designed to work with the output format from the scraper lambda function:

### Scraper Lambda Output Format
```json
{
  "playlist_id": "beatport-top100-20240730-120000",
  "name": "Beatport Top 100",
  "description": "Top 100 tracks scraped from Beatport",
  "source": "beatport",
  "source_url": "https://www.beatport.com/top-100",
  "created_at": "2024-07-30T12:00:00.000Z",
  "track_count": 5,
  "scraped_by": "lambda-request-id",
  "tracks": [
    {
      "title": "Track Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "genre": "Electronic",
      "bpm": 128,
      "key": "Am",
      "label": "Record Label",
      "rank": 1,
      "beatport_id": "123456",
      "url": "https://www.beatport.com/track/track-title/123456",
      "release_date": "2024-07-15"
    }
  ],
  "metadata": {
    "scraper_version": "1.0",
    "scraped_at": "2024-07-30T12:00:00.000Z",
    "total_tracks_found": 5
  }
}
```

## Environment Variables

- `TRACKS_TABLE`: DynamoDB table name for existing tracks
- `NEW_TRACKS_TOPIC_ARN`: SNS topic ARN for publishing new tracks
- `PLAYLISTS_BUCKET`: S3 bucket name for playlist files (inherited from global environment)

## S3 Event Trigger

The function is triggered by S3 ObjectCreated events for files with the `.json` extension in the playlists bucket.

## Track Deduplication

The function uses title and artist as the primary keys for deduplication. It scans the tracks table looking for exact matches on both fields. If a match is found, the track is considered existing and not published to SNS.

## SNS Message Format

New tracks are published to SNS with the following message structure:

```json
{
  "track": {
    "title": "Track Title",
    "artist": "Artist Name",
    "album": "Album Name",
    "genre": "Electronic",
    "bpm": 128,
    "key": "Am",
    "label": "Record Label",
    "rank": 1,
    "metadata": {
      "original_data": { ... },
      "source": "chart-processor"
    }
  },
  "source_file": "charts/2024/07/30/top100-120000.json",
  "timestamp": "2024-07-30T12:00:00.000Z",
  "action": "process_new_track"
}
```

## Message Attributes

Each SNS message includes the following attributes:
- `source_file`: The S3 key of the source chart file
- `track_title`: The title of the track
- `track_artist`: The artist of the track

## Error Handling

The function includes comprehensive error handling:
- Failed S3 downloads are logged and return appropriate error responses
- Failed chart parsing attempts multiple data structure formats
- Database connection errors are logged but don't prevent processing other tracks
- SNS publishing errors are logged per track but don't stop the overall processing

## Performance Considerations

- **Database Queries**: Currently uses table scans for track existence checks. Consider implementing a Global Secondary Index (GSI) on title+artist for better performance in production
- **Batch Processing**: Processes tracks individually. For large charts, consider implementing batch operations
- **Memory Usage**: Loads entire chart file into memory. For very large files, consider streaming processing

## Testing

The function includes a test harness that can be run locally:

```python
if __name__ == "__main__":
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
```

## Deployment

The function is deployed as part of the SAM template and includes:
- IAM permissions for DynamoDB read access
- IAM permissions for S3 read access on the charts bucket
- IAM permissions for SNS publish to the new tracks topic
- S3 event trigger configuration
- Environment variable configuration
