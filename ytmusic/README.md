# YouTube Music Search SQS Integration

## Quick Setup

1. **Deploy the infrastructure:**
   ```bash
   sam build
   sam deploy --guided
   ```

2. **The system will automatically:**
   - Create an SQS queue for YouTube music processing
   - Subscribe the queue to the SNS topic for new tracks
   - Configure the YouTube Music Search Function to process SQS messages
   - Set up a dead letter queue for failed messages

## How it Works

```
Chart Files → Chart Processor → SNS Topic → SQS Queue → YouTube Music Function → DynamoDB
```

1. When new playlist files are uploaded to S3, the Chart Processor publishes new tracks to SNS
2. The SQS queue receives these track messages from SNS
3. The YouTube Music Search Function polls the SQS queue automatically
4. For each track, the function searches YouTube Music and updates/creates DynamoDB records
5. Failed messages go to a dead letter queue for troubleshooting

## Key Components Added

- **SQS Queue**: `{StackName}-youtube-music-processing`
- **Dead Letter Queue**: `{StackName}-youtube-music-processing-dlq`
- **SNS Subscription**: Connects SNS topic to SQS queue
- **Enhanced Lambda Function**: Handles both SQS events and direct API calls

## Configuration

The function maintains backward compatibility and handles both:
- **SQS Events**: Automatic processing from chart uploads (new)
- **Direct API Calls**: Manual searches via REST API (existing)

## Monitoring

Check CloudWatch for:
- Lambda function metrics and logs
- SQS queue depth and processing rates
- Dead letter queue for failed messages

## Testing

Run the message parsing test:
```bash
cd ytmusic
python test_message_parsing.py
```

See `ytmusic/SQS_INTEGRATION.md` for detailed documentation.
