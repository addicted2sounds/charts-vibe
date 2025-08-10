# S3 Bucket Configuration for YouTube Playlist Function

## Global Template Reference

The YouTube Playlist Lambda function now uses the S3 bucket reference from the global CloudFormation template:

### Template Configuration

In `template.yaml`, the playlist bucket is defined as:

```yaml
Resources:
  PlaylistsBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "${AWS::StackName}-playlists"
      # ... other properties

Globals:
  Function:
    Environment:
      Variables:
        PLAYLISTS_BUCKET: !Ref PlaylistsBucket
        # ... other variables
```

### Function Permissions

The YouTubePlaylistFunction has been updated with the necessary permissions:

```yaml
YoutubePlaylistFunction:
  Type: AWS::Serverless::Function
  Properties:
    # ... other properties
    Policies:
      - DynamoDBCrudPolicy:
          TableName: !If [ShouldCreateTables, !Ref PlaylistsTable, !Ref ExistingPlaylistsTableName]
      - DynamoDBCrudPolicy:
          TableName: !If [ShouldCreateTables, !Ref TracksTable, !Ref ExistingTracksTableName]
      - S3ReadPolicy:
          BucketName: !Ref PlaylistsBucket  # <- NEW: S3 read access
      - SSMParameterReadPolicy:
          ParameterName: /youtube/*
```

### Usage in Events

When calling the function, use the template-generated bucket name:

```json
{
  "s3_bucket": "${AWS_STACK_NAME}-playlists",
  "s3_key": "beatport/2024/08/10/top100-120000.json",
  "playlist_name": "My Custom Playlist"
}
```

### Runtime Bucket Resolution

The function can access the actual bucket name via the environment variable:

```python
import os
bucket_name = os.environ.get('PLAYLISTS_BUCKET')
# This will resolve to something like: "music-search-stack-playlists"
```

### Benefits

1. **Consistency**: Uses the same bucket as other functions (scraper, chart-processor)
2. **Auto-naming**: Bucket name automatically includes stack name to avoid conflicts
3. **Proper permissions**: Function has the exact permissions needed
4. **Environment variables**: Bucket name available at runtime via `PLAYLISTS_BUCKET`

### Integration Flow

```
1. Scraper Lambda -> Stores playlist data -> S3 (PlaylistsBucket)
2. Chart Processor -> Processes S3 files -> DynamoDB (TracksTable)
3. YouTube Music Lambda -> Enriches tracks -> DynamoDB (TracksTable)
4. YouTube Playlist Lambda -> Reads S3 + DynamoDB -> Creates YouTube playlists
```

All functions use the same S3 bucket reference from the global template, ensuring consistency across the entire pipeline.
