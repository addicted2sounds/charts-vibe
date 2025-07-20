# YouTube Playlist Creation Lambda Function

This Lambda function creates public YouTube playlists from video IDs using the YouTube Data API v3.

## Features

- ✅ Creates public YouTube playlists
- ✅ Adds multiple videos to playlists in order
- ✅ Stores playlist metadata in DynamoDB
- ✅ Secure credential management with AWS Parameter Store
- ✅ Error handling and detailed response logging
- ✅ Works with LocalStack for testing

## Setup Instructions

### 1. Prerequisites

```bash
# Install required Python packages
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client boto3
```

### 2. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials
5. Download the credentials as `client_secret.json`

### 3. OAuth Flow Setup

Run the OAuth setup script to get access tokens:

```bash
cd ytplaylist
python oauth_setup.py
```

This will:
- Open a browser for Google OAuth authorization
- Store access/refresh tokens in AWS Parameter Store
- Store client credentials securely

### 4. Deploy with SAM

```bash
# For LocalStack
./deploy-localstack.sh

# For AWS
sam build && sam deploy --guided
```

## Usage

### API Request Format

```json
{
  "playlist_name": "My Awesome Playlist",
  "video_ids": [
    "dQw4w9WgXcQ",
    "kJQP7kiw5Fk",
    "JGwWNGJdvx8"
  ],
  "description": "Optional playlist description"
}
```

### API Response Format

```json
{
  "success": true,
  "playlist_id": "PLxxxxxxxxxxxxxxxxxxxxxxx",
  "playlist_url": "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxx",
  "music_url": "https://music.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxx",
  "playlist_name": "My Awesome Playlist",
  "total_videos_requested": 3,
  "videos_added_successfully": 3,
  "failed_videos": [],
  "database_stored": true
}
```

### cURL Example

```bash
curl -X POST https://your-api-gateway-url/playlists \
  -H "Content-Type: application/json" \
  -d '{
    "playlist_name": "Test Playlist",
    "video_ids": ["dQw4w9WgXcQ", "kJQP7kiw5Fk"],
    "description": "Test playlist from API"
  }'
```

### Lambda Direct Invocation

```bash
aws lambda invoke \
  --function-name music-search-stack-YoutubePlaylistFunction-XXXXX \
  --payload '{"playlist_name": "Test", "video_ids": ["dQw4w9WgXcQ"]}' \
  response.json
```

## Testing

### Local Testing

```bash
# Test the function locally
python test_playlist.py

# Test credentials setup
python -c "
import boto3
ssm = boto3.client('ssm', endpoint_url='http://localhost:4566')
try:
    ssm.get_parameter(Name='/youtube/access_token', WithDecryption=True)
    print('✅ Credentials found')
except:
    print('❌ No credentials found')
"
```

### Sample Video IDs for Testing

```python
test_videos = [
    "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
    "kJQP7kiw5Fk",  # Luis Fonsi - Despacito
    "JGwWNGJdvx8",  # Ed Sheeran - Shape of You
    "CevxZvSJLk8",  # Katy Perry - Roar
    "9bZkp7q19f0"   # PSY - Gangnam Style
]
```

## Files Structure

```
ytplaylist/
├── app.py                 # Main Lambda function
├── requirements.txt       # Python dependencies
├── client_secret.json     # Google OAuth credentials
├── oauth_setup.py         # OAuth flow setup script
└── test_playlist.py       # Test script
```

## Environment Variables

- `PLAYLISTS_TABLE` - DynamoDB table for storing playlist metadata
- `AWS_ENDPOINT_URL` - LocalStack endpoint (for testing)
- `YOUTUBE_API_KEY` - Alternative to OAuth (limited functionality)

## Error Handling

The function handles various error scenarios:

- **Invalid video IDs**: Logs errors but continues with valid videos
- **Authentication failures**: Returns 500 with error details
- **YouTube API errors**: Detailed error logging and graceful degradation
- **DynamoDB errors**: Continues execution even if database storage fails

## Security Considerations

- ✅ Credentials stored in AWS Parameter Store (encrypted)
- ✅ No credentials in source code or environment variables
- ✅ OAuth refresh token support for long-term access
- ⚠️ Remove `client_secret.json` from production deployments

## Limitations

- YouTube API quota limits (10,000 units/day by default)
- Maximum 50 videos per playlist creation request (API limit)
- Requires user consent for OAuth (one-time setup)
- Public playlists only (can be modified for private playlists)

## Troubleshooting

### Common Issues

1. **"No valid authentication found"**
   - Run `oauth_setup.py` to complete OAuth flow
   - Check Parameter Store for missing credentials

2. **"YouTube API error creating playlist"**
   - Check YouTube API quota in Google Cloud Console
   - Verify API is enabled for your project

3. **Invalid video IDs**
   - Ensure video IDs are valid YouTube video IDs
   - Check that videos are not private or restricted

### Debug Mode

Set environment variable for verbose logging:
```bash
export DEBUG=1
```

## API Quota Management

Monitor your YouTube API usage in [Google Cloud Console](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas).

Default quota costs:
- Create playlist: 50 units
- Add video to playlist: 50 units per video

## Next Steps

- Add support for private playlists
- Implement batch video addition for large playlists
- Add playlist update/delete functionality
- Integration with music search and scraper functions
