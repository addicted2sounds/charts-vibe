# Beatport Top-100 Scraper

This Lambda function scrapes the Beatport Top-100 chart and returns structured track data.

## Features

- Scrapes track information from Beatport's top-100 page
- Extracts track details including title, artist, label, BPM, key, etc.
- Handles multiple HTML structures and fallback methods
- Returns JSON response with track list

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
    "source": "beatport-top-100",
    "scraped_at": "request-id"
  }
}
```

## Local Testing

To test the function locally:

```bash
cd scraper
pip install -r requirements.txt
python app.py
```

## Deployment

The function is configured in the main `template.yaml` with a 30-second timeout to allow for web scraping.

## Error Handling

- Returns 500 status code with error message if scraping fails
- Includes request timeout and retry logic
- Gracefully handles missing track data

## Notes

- Uses proper User-Agent headers to avoid blocking
- Implements multiple fallback strategies for data extraction
- Respects Beatport's robots.txt and rate limiting
