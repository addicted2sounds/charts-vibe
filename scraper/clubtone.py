#!/usr/bin/env python3
"""
Scraper for Clubtone Top 10 chart.

This lambda fetches the Top 10 page, extracts track metadata, and stores a
playlist snapshot in S3 so the rest of the pipeline can discover and process
new tracks.
"""

import json
import os
import re
from datetime import datetime, timezone

import boto3
import requests
from bs4 import BeautifulSoup

from utils import generate_track_id

CLUBTONE_TOP100_URL = "https://clubtone.do.am/top_100"


def lambda_handler(event, context):
    """Entrypoint for the Clubtone Top 10 scraper lambda."""
    try:
        target_url = os.environ.get("CLUBTONE_URL", CLUBTONE_TOP100_URL)

        print(f"Fetching Clubtone chart from {target_url}")
        html, used_url = fetch_chart_html(target_url)

        if not html:
            return {
                "statusCode": 500,
                "body": "Failed to fetch Clubtone chart"
            }

        tracks = extract_tracks(html, limit=100)
        print(f"Extracted {len(tracks)} tracks from Clubtone response")

        if not tracks:
            return {
                "statusCode": 500,
                "body": "No tracks found on Clubtone page"
            }

        now = datetime.now(timezone.utc)
        playlist_id = f"clubtone-top100-{now.strftime('%Y%m%d-%H%M%S')}"
        playlist_data = {
            "playlist_id": playlist_id,
            "name": "Clubtone Top 100",
            "description": "Top 100 tracks scraped from Clubtone",
            "source": "clubtone",
            "source_url": used_url,
            "created_at": now.isoformat(),
            "track_count": len(tracks),
            "scraped_by": context.aws_request_id if context else "local",
            "tracks": tracks,
            "metadata": {
                "scraper_version": "1.0",
                "scraped_at": now.isoformat(),
                "total_tracks_found": len(tracks),
                "target_url": target_url
            }
        }

        s3_result = store_playlist_in_s3(playlist_data)

        return {
            "statusCode": 200,
            "body": {
                "total_tracks": len(tracks),
                "tracks": tracks,
                "source": "clubtone-top-100",
                "scraped_at": context.aws_request_id if context else "local",
                "playlist": {
                    "id": playlist_id,
                    "s3_location": s3_result if s3_result else "Failed to store in S3"
                }
            }
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"Clubtone scraper failed: {exc}")
        return {
            "statusCode": 500,
            "body": f"Scraping error: {str(exc)}"
        }


def fetch_chart_html(url):
    """
    Fetch the chart page HTML.
    Returns a tuple of (html, url_used).
    """
    headers = {
        "User-Agent": os.environ.get(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"Fetched Clubtone page: {url} (status {response.status_code})")
        return response.text, url
    except Exception as exc:
        print(f"Failed to fetch {url}: {exc}")
        return None, None


def extract_tracks(html, limit=None):
    """Parse track data from the Clubtone chart HTML."""
    soup = BeautifulSoup(html, "html.parser")
    track_elements = soup.select(".t100")
    if limit:
        track_elements = track_elements[:limit]

    tracks = []
    for idx, element in enumerate(track_elements, 1):
        track_data = extract_track_data(element, idx)
        if track_data and track_data.get("title") and track_data.get("artist"):
            tracks.append(track_data)
            print(f"Track {idx}: {track_data['artist']} - {track_data['title']}")
        else:
            print(f"Skipping track at position {idx}: missing title or artist")

    return tracks


def extract_track_data(element, position):
    """Extract a single track's data from a .t100 element."""
    title_node = element.select_one(".entryLink")
    genre_node = element.select_one(".t1s")
    cover_node = element.select_one("span.tc img")

    title_text = title_node.get_text(strip=True) if title_node else ""
    artist, title = split_artist_title(title_text)

    entry_url = title_node.get("href") if title_node else None
    clubtone_id = parse_clubtone_id(element, entry_url)

    cover_url = None
    if cover_node and cover_node.get("src"):
        cover_src = cover_node.get("src")
        if cover_src.startswith("//"):
            cover_url = f"https:{cover_src}"
        else:
            cover_url = cover_src

    track = {
        "position": position,
        "title": title,
        "artist": artist,
        "genre": genre_node.get_text(strip=True) if genre_node else None,
        "clubtone_id": clubtone_id,
        "source": "clubtone",
        "source_url": entry_url,
        "cover_url": cover_url
    }

    if title and artist:
        track["track_id"] = generate_track_id(title, artist)

    return track


def split_artist_title(title_text):
    """Split combined 'Artist - Title' strings into components."""
    if not title_text or " - " not in title_text:
        return None, title_text

    artist_part, title_part = title_text.split(" - ", 1)
    return artist_part.strip(), title_part.strip()


def parse_clubtone_id(element, entry_url=None):
    """Extract the numeric Clubtone entry id from element id or link."""
    if entry_url:
        # URLs look like .../2-1-0-659064 – use the trailing numeric segment
        match = re.search(r"(\d+)(?:\\.html)?$", entry_url)
        if not match:
            match = re.search(r"-(\\d+)(?:\\.html)?", entry_url)
        if match:
            return match.group(1)

    element_id = element.get("id", "")
    match = re.search(r"(\d+)", element_id)
    if match:
        return match.group(1)

    return None


def store_playlist_in_s3(playlist_data):
    """Store playlist data in S3 under the clubtone prefix."""
    try:
        bucket_name = os.environ.get("PLAYLISTS_BUCKET")
        if not bucket_name:
            print("No S3 bucket configured for playlists")
            return None

        s3_client = boto3.client("s3")

        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")
        time_suffix = now.strftime("%H%M%S")
        s3_key = f"clubtone/{date_path}/top10-{time_suffix}.json"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(playlist_data, indent=2, default=str),
            ContentType="application/json",
            Metadata={
                "source": "clubtone-scraper",
                "playlist-type": "top-10",
                "scraped-at": now.isoformat()
            }
        )

        return {
            "bucket": bucket_name,
            "key": s3_key,
            "url": f"s3://{bucket_name}/{s3_key}"
        }

    except Exception as exc:
        print(f"Error storing playlist in S3: {exc}")
        return None


if __name__ == "__main__":
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))
