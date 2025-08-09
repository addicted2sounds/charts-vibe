# SQS Integration for YouTube Music Search

## Overview

This document describes the SQS integration added to the YouTube Music Search Function, which allows it to process new tracks automatically via an SQS queue that subscribes to the SNS topic for new tracks.

## Architecture

```
Chart Processor → SNS Topic → SQS Queue → YouTube Music Search Function
                    ↓
                DynamoDB (Tracks Table)
```

1. **Chart Processor** processes new playlist files and publishes new track data to SNS topic
2. **SNS Topic** (`NewTracksQueue`) receives new track notifications
3. **SQS Queue** (`YouTubeMusicProcessingQueue`) subscribes to the SNS topic and receives messages
4. **YouTube Music Search Function** polls the SQS queue and processes track messages
5. **Dead Letter Queue** (`YouTubeMusicProcessingDLQ`) receives failed messages for troubleshooting

## Components Added

### SQS Queue
- **Name**: `{StackName}-youtube-music-processing`
- **Visibility Timeout**: 60 seconds (matches Lambda timeout)
- **Message Retention**: 14 days
- **Dead Letter Queue**: After 3 failed processing attempts

### Dead Letter Queue
- **Name**: `{StackName}-youtube-music-processing-dlq`
- **Message Retention**: 14 days
- **Purpose**: Store messages that failed processing for manual investigation

### SNS Subscription
- **Protocol**: SQS
- **Endpoint**: YouTube Music Processing Queue ARN
- **Delivery**: All messages published to `NewTracksQueue` are delivered to the SQS queue

## Function Updates

The YouTube Music Search Function (`ytmusic/app.py`) has been updated to handle both:

### 1. SQS Events (New)
- Processes batches of up to 10 SQS messages
- Each message contains an SNS message with track data
- Extracts track title and artist from the message
- Searches YouTube Music for the track
- Updates/creates track records in DynamoDB

### 2. Direct API Calls (Legacy)
- Maintains backward compatibility
- Handles direct REST API calls with title/author parameters

## Message Flow

### SNS Message Format (from Chart Processor)
```json
{
  "track": {
    "title": "Track Title",
    "artist": "Artist Name",
    "album": "Album Name",
    "genre": "Electronic",
    "label": "Label Name",
    "bpm": 128,
    "key": "Am",
    "rank": 1,
    "beatport_url": "https://beatport.com/track/123",
    "beatport_id": "123"
  },
  "source_file": "beatport/2024/07/30/top100.json",
  "timestamp": "2024-07-30T12:00:00Z",
  "action": "process_new_track"
}
```

### SQS Message Format (wrapped SNS message)
```json
{
  "Records": [
    {
      "messageId": "12345",
      "body": "{\"Type\":\"Notification\",\"Message\":\"{...}\"}",
      "eventSource": "aws:sqs",
      "eventSourceARN": "arn:aws:sqs:region:account:queue-name"
    }
  ]
}
```

## Processing Logic

For each track in the SQS message:
1. **Extract** track title and artist from SNS message
2. **Search** YouTube Music API for the track
3. **Check** if track already exists in DynamoDB (using hash-based ID)
4. **Update** existing track with YouTube data if missing
5. **Create** new track record if it doesn't exist
6. **Log** processing results

## Configuration

### Environment Variables
- `TRACKS_TABLE`: DynamoDB table name for tracks
- `YOUTUBE_MUSIC_PROCESSING_QUEUE_URL`: SQS queue URL (optional, for manual operations)

### IAM Permissions
The function requires:
- `DynamoDBCrudPolicy` for the tracks table
- `SQSPollerPolicy` for the processing queue
- Implicit permissions to receive SQS events

## Monitoring

### CloudWatch Metrics
- Lambda function metrics (invocations, duration, errors)
- SQS queue metrics (messages sent, received, deleted)
- DLQ metrics for failed messages

### Logging
- Processing results for each track
- Error messages for failed searches or database operations
- SQS message parsing issues

## Testing

Use the test script `ytmusic/test_sqs_integration.py` to verify:
- SQS event processing
- Direct API call compatibility
- Error handling for invalid messages

```bash
cd ytmusic
python test_sqs_integration.py
```

## Deployment

The SQS integration is included in the CloudFormation template (`template.yaml`). Deploy using:

```bash
sam build
sam deploy
```

## Troubleshooting

### Common Issues

1. **Messages in DLQ**: Check function logs for processing errors
2. **No messages processed**: Verify SNS subscription and SQS permissions
3. **YouTube API errors**: Check network connectivity and API limits
4. **Database errors**: Verify DynamoDB permissions and table configuration

### Useful Commands

```bash
# Check SQS queue status
aws sqs get-queue-attributes --queue-url <queue-url> --attribute-names All

# View DLQ messages
aws sqs receive-message --queue-url <dlq-url>

# Monitor function logs
aws logs tail /aws/lambda/<function-name> --follow
```

## Benefits

1. **Automatic Processing**: New tracks are processed automatically without manual intervention
2. **Scalability**: SQS provides buffering and can handle message bursts
3. **Reliability**: Dead letter queue captures failed messages for investigation
4. **Decoupling**: Chart processor and YouTube search are loosely coupled via messaging
5. **Batch Processing**: Processes multiple tracks efficiently in batches
6. **Backward Compatibility**: Maintains existing API functionality
