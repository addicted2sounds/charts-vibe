#!/usr/bin/env python3
import json
import requests
from bs4 import BeautifulSoup
import re
import boto3
import os
from datetime import datetime, timezone
from utils import generate_track_id

def store_playlist_in_s3(playlist_data, playlist_id):
    """Store playlist data in S3"""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('PLAYLISTS_BUCKET')

        if not bucket_name:
            print("No S3 bucket configured for playlists")
            return None

        # Generate S3 key with new format: beatport/YYYY/MM/DD/top100-HHMMSS.json
        now = datetime.now(timezone.utc)
        date_path = now.strftime('%Y/%m/%d')
        time_suffix = now.strftime('%H%M%S')
        s3_key = f"beatport/{date_path}/top100-{time_suffix}.json"

        # Upload playlist data to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(playlist_data, indent=2, default=str),
            ContentType='application/json',
            Metadata={
                'source': 'beatport-scraper',
                'playlist-type': 'top-100',
                'scraped-at': datetime.now(timezone.utc).isoformat()
            }
        )

        return {
            'bucket': bucket_name,
            'key': s3_key,
            'url': f"s3://{bucket_name}/{s3_key}"
        }

    except Exception as e:
        print(f"Error storing playlist in S3: {str(e)}")
        return None

def lambda_handler(event, context):
    """
    Lambda function to scrape Beatport's top-100 tracks
    """
    try:
        # Fetch the page from Beatport
        print("Fetching Beatport top-100 page...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

        response = requests.get('https://www.beatport.com/top-100', headers=headers, timeout=30)
        response.raise_for_status()


        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all track rows using the working approach
        track_elements = soup.find_all('div', {'data-testid': 'tracks-table-row'})
        print(f"Found {len(track_elements)} track elements")

        if not track_elements:
            return {
                "statusCode": 500,
                "body": "No track elements found with data-testid='tracks-table-row'"
            }

        tracks = []

        # Process all tracks
        for idx, element in enumerate(track_elements, 1):
            try:
                track_data = extract_track_data_simple(element, idx)

                # Validate the track
                if track_data.get('title') and track_data.get('artist'):
                    tracks.append(track_data)
                    print(f"Valid track {len(tracks)}: {track_data['title']} - {track_data['artist']}")
                else:
                    print(f"Skipping invalid track {idx} - missing title or artist")

            except Exception as e:
                print(f"Error processing track {idx}: {e}")
                continue

        print(f"Successfully extracted {len(tracks)} valid tracks")

        # Create playlist data for S3 storage
        now = datetime.now(timezone.utc)
        playlist_id = f"beatport-top100-{now.strftime('%Y%m%d-%H%M%S')}"
        playlist_data = {
            'playlist_id': playlist_id,
            'name': 'Beatport Top 100',
            'description': 'Top 100 tracks scraped from Beatport',
            'source': 'beatport',
            'source_url': 'https://www.beatport.com/top-100',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'track_count': len(tracks),
            'scraped_by': context.aws_request_id if context else "local",
            'tracks': tracks,
            'metadata': {
                'scraper_version': '1.0',
                'scraped_at': datetime.now(timezone.utc).isoformat(),
                'total_tracks_found': len(tracks),
            }
        }

        # Store playlist in S3 (commented out for local testing)
        s3_result = store_playlist_in_s3(playlist_data, playlist_id)

        return {
            "statusCode": 200,
            "body": {
                "total_tracks": len(tracks),
                "tracks": tracks,
                "source": "beatport-top-100",
                "scraped_at": context.aws_request_id if context else "local",
                "playlist": {
                    "id": playlist_id,
                    "s3_location": s3_result if s3_result else "Failed to store in S3"
                }
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Scraping error: {str(e)}"
        }

def extract_track_data_simple(element, position):
    """Extract track data from a tracks-table-row element"""
    track_data = {
        "position": position,
        "title": None,
        "artist": None,
        "label": None,
        "genre": None,
        "bpm": None,
        "key": None,
        "beatport_id": None,
        "url": None
    }

    print(f"\n=== TRACK {position} ===")
    print(f"Element tag: {element.name}")
    print(f"Element classes: {element.get('class', [])}")

    # Look for track title - try different approaches
    title_found = False

    # Method 1: Look for links to track pages
    track_links = element.select('a[href*="/track/"]')
    if track_links:
        for link in track_links:
            title_text = link.get_text().strip()
            if title_text and len(title_text) > 3:
                track_data["title"] = title_text
                print(f"Found title from track link: {title_text}")

                # Extract track ID from URL
                href = link.get('href', '')
                track_id_match = re.search(r'/track/[^/]+/(\d+)', href)
                if track_id_match:
                    track_data["beatport_id"] = track_id_match.group(1)
                    track_data["url"] = f"https://www.beatport.com{href}" if href.startswith('/') else href
                    print(f"Found track ID: {track_data['beatport_id']}")

                title_found = True
                break

    # Method 2: If no title from links, look for any text that might be a title
    if not title_found:
        # Get all text elements and try to identify the title
        text_elements = element.find_all(['span', 'div', 'p'])
        for elem in text_elements:
            text = elem.get_text().strip()
            # Skip empty text, very short text, or common labels
            if (text and len(text) > 5 and
                not text.lower() in ['track', 'title', 'artist', 'label', 'genre', 'bpm', 'key'] and
                not text.isdigit() and
                not re.match(r'^\d+[A-G]?$', text)):  # Skip musical keys like "4A"

                track_data["title"] = text
                print(f"Found potential title: {text}")
                title_found = True
                break

    # Look for artists - links to artist pages
    artist_links = element.select('a[href*="/artist/"]')
    if artist_links:
        artist_names = []
        for link in artist_links:
            artist_name = link.get_text().strip()
            if artist_name and len(artist_name) > 1:
                artist_names.append(artist_name)

        if artist_names:
            track_data["artist"] = ', '.join(artist_names)
            print(f"Found artists: {track_data['artist']}")

    # Look for label
    label_links = element.select('a[href*="/label/"]')
    if label_links:
        label_name = label_links[0].get_text().strip()
        if label_name:
            track_data["label"] = label_name
            print(f"Found label: {label_name}")

    # Look for genre
    genre_links = element.select('a[href*="/genre/"]')
    if genre_links:
        genre_name = genre_links[0].get_text().strip()
        if genre_name:
            track_data["genre"] = genre_name
            print(f"Found genre: {genre_name}")

    # Look for BPM - usually just a number
    all_text = element.get_text()
    bpm_match = re.search(r'(\d{2,3})\s*BPM', all_text, re.IGNORECASE)
    if bpm_match:
        bpm_value = int(bpm_match.group(1))
        if 80 <= bpm_value <= 200:  # Reasonable BPM range
            track_data["bpm"] = bpm_value
            print(f"Found BPM: {bpm_value}")

    # Look for musical key - pattern like "4A", "12B", etc.
    key_match = re.search(r'([A-G](?:#|b)?\s+(?:Major|Minor))', all_text, re.IGNORECASE)
    if key_match:
        track_data["key"] = key_match.group(1)
        print(f"Found key: {track_data['key']}")

    # Generate track ID if we have title and artist
    if track_data.get('title') and track_data.get('artist'):
        track_data["track_id"] = generate_track_id(track_data['title'], track_data['artist'])
        print(f"Generated track ID: {track_data['track_id']}")

    return track_data

def main():
    """Test the extraction with the data-testid approach"""
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
