# Music Search Database Setup

This project now includes a complete database structure for storing fetched ratings and songs with YouTube Music URLs.

## Database Schema

The DynamoDB table `tracks` stores:

- **track_id** (Primary Key): Unique identifier for each track
- **created_at**: Timestamp when the track was first stored
- **updated_at**: Timestamp when the track was last modified
- **title**: Track title
- **artist**: Artist name
- **album**: Album or remix information
- **genre**: Music genre
- **rating**: Track rating/score
- **rank**: Position in charts (e.g., Beatport top 100)
- **bpm**: Beats per minute
- **key**: Musical key
- **label**: Record label
- **release_date**: Release date
- **beatport_url**: Original Beatport URL
- **youtube_video_id**: YouTube Music video ID
- **youtube_url**: YouTube Music URL
- **source**: Data source (e.g., "beatport")
- **metadata**: Additional metadata as JSON

## Components

### 1. Database Service (`database/`)
- RESTful API for CRUD operations on tracks
- Direct DynamoDB integration
- Helper functions for other Lambda functions

### 2. Updated Scraper (`scraper/`)
- Now stores scraped Beatport data directly to DynamoDB
- Maintains original scraping functionality
- Automatic database integration

### 3. Updated YouTube Music Search (`ytmusic/`)
- Searches for YouTube Music URLs
- Updates existing tracks with YouTube data
- Can work with track IDs or search by title/artist

## LocalStack Setup

### Prerequisites
```bash
# Install Docker and Docker Compose
# Install AWS SAM CLI
# Install LocalStack
pip install localstack
```

### Quick Start

1. **Start LocalStack:**
```bash
docker-compose up -d
```

2. **Deploy the application:**
```bash
./deploy-localstack.sh
```

3. **Test the setup:**
```bash
python test_db.py
```

### Manual Testing

#### Create a track:
```bash
curl -X POST http://localhost:4566/restapis/YOUR_API_ID/local/_user_request_/tracks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Track",
    "artist": "Test Artist",
    "genre": "Electronic",
    "rating": 85,
    "rank": 1
  }'
```

#### Get all tracks:
```bash
curl http://localhost:4566/restapis/YOUR_API_ID/local/_user_request_/tracks
```

#### Test scraper:
```bash
aws lambda invoke \
  --endpoint-url=http://localhost:4566 \
  --function-name music-search-stack-BeatportScraperFunction-XXXXX \
  --payload '{}' \
  response.json
```

#### Test YouTube Music search:
```bash
aws lambda invoke \
  --endpoint-url=http://localhost:4566 \
  --function-name music-search-stack-YoutubeMusicSearchFunction-XXXXX \
  --payload '{"title": "Bohemian Rhapsody", "author": "Queen"}' \
  response.json
```

## Workflow

1. **Scraper** fetches Beatport top 100 and stores tracks in DynamoDB
2. **YouTube Music function** finds YouTube URLs for tracks
3. **Database API** provides CRUD operations for managing stored tracks
4. All data is persisted in DynamoDB for further analysis

## Environment Variables

- `TRACKS_TABLE`: DynamoDB table name (automatically set by SAM)
- `AWS_ENDPOINT_URL`: LocalStack endpoint (for local testing)

## API Endpoints

- `POST /tracks` - Create a new track
- `GET /tracks` - Get all tracks
- `GET /tracks/{track_id}` - Get a specific track
- `PUT /tracks/{track_id}` - Update a track

The database structure is now ready for your LocalStack testing environment!
