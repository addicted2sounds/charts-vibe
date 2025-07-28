import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import boto3
import os
from datetime import datetime, timezone

def store_playlist_in_s3(playlist_data, playlist_id):
    """Store playlist data in S3"""
    try:
        s3_client = boto3.client('s3')
        bu        bpm_element = find_element_by_selectors(element, bpm_selectors)
        if bpm_element:
            bpm_text = clean_text(bpm_element.get_text())
            bpm_match = re.search(r'(\d+)', bpm_text) if bpm_text else None
            if bpm_match:
                track_data["bpm"] = int(bpm_match.group(1))
                print(f"Found BPM: {track_data['bpm']}")me = os.environ.get('PLAYLISTS_BUCKET')

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
        # Read from local file instead of making web request
        print("Reading from local beatport_response.html file...")

        try:
            with open('beatport_response.html', 'r', encoding='utf-8') as f:
                html_content = f.read()
            print(f"Successfully read {len(html_content)} characters from file")
        except FileNotFoundError:
            return {
                "statusCode": 500,
                "body": "beatport_response.html file not found. Please run the scraper first to generate this file."
            }

        # Parse the HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        tracks = []

        # Debug: Let's see what elements we're actually finding
        print("=== DEBUGGING ELEMENT DETECTION ===")

        # Method 1: Look for script tags with track data first (most reliable for modern sites)
        print("Trying to extract from JavaScript/JSON data...")
        tracks = extract_tracks_from_scripts(soup)
        if tracks:
            print(f"Extracted {len(tracks)} tracks from JavaScript")

        # Method 2: If no tracks from JS, try HTML elements
        if not tracks:
            print("No tracks found in JavaScript, trying HTML elements...")

            # First try the specific data-testid that the user identified
            track_elements = soup.find_all('div', {'data-testid': 'tracks-table-row'})
            print(f"Found {len(track_elements)} elements with data-testid='tracks-table-row'")

            # If that doesn't work, fall back to other selectors
            if not track_elements:
                selectors_to_try = [
                    {'selector': 'attrs', 'value': {'data-ec-id': True}, 'name': 'data-ec-id'},
                    {'selector': 'attrs', 'value': {'data-track-id': True}, 'name': 'data-track-id'},
                    {'selector': 'class', 'value': re.compile(r'track.*row|chart.*item|playable.*track', re.I), 'name': 'track-related classes'},
                    {'selector': 'tag', 'value': 'tr', 'name': 'table rows'},
                    {'selector': 'tag', 'value': 'li', 'name': 'list items'},
                ]

                for selector_info in selectors_to_try:
                    if selector_info['selector'] == 'attrs':
                        elements = soup.find_all(attrs=selector_info['value'])
                    elif selector_info['selector'] == 'class':
                        elements = soup.find_all(['li', 'div', 'tr'], class_=selector_info['value'])
                    elif selector_info['selector'] == 'tag':
                        elements = soup.find_all(selector_info['value'])

                    print(f"Found {len(elements)} elements with {selector_info['name']}")

                    if elements:
                        track_elements = elements
                        print(f"Using {len(track_elements)} elements from {selector_info['name']}")
                        break

            # Process HTML elements
            if track_elements:
                print(f"Processing {len(track_elements)} track elements from HTML...")

                for idx, element in enumerate(track_elements):
                    try:
                        track_data = extract_track_data(element, idx + 1)

                        # Better validation - check if this looks like real track data
                        if (track_data and
                            track_data.get('title') and
                            track_data.get('artist') and
                            track_data['title'] not in ['Title / Artists', 'Title', 'Track Title', 'Track Name'] and
                            track_data['artist'] not in ['Artist', 'Artists', 'Toman', 'Artist Name'] and
                            len(track_data['title']) > 3 and len(track_data['artist']) > 2):

                            tracks.append(track_data)
                            print(f"Valid track {len(tracks)}: {track_data['title']} - {track_data['artist']}")
                        else:
                            print(f"Skipping invalid/placeholder track {idx + 1}: {track_data.get('title', 'No title')} - {track_data.get('artist', 'No artist')}")

                        # Continue processing all elements to get 100 tracks
                        if len(tracks) >= 100:
                            print("Reached 100 tracks, stopping...")
                            break

                    except Exception as e:
                        print(f"Error extracting track {idx + 1}: {str(e)}")
                        continue

        print(f"Final result: {len(tracks)} valid tracks extracted")

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
                # 'successfully_stored_in_db': len(stored_tracks)
            }
        }

        # Store playlist in S3
        # s3_result = store_playlist_in_s3(playlist_data, playlist_id)

        return {
            "statusCode": 200,
            "body": {
                "total_tracks": len(tracks),
                "tracks": tracks,
                "source": "beatport-top-100",
                "scraped_at": context.aws_request_id if context else "local",
                "playlist": {
                    "id": playlist_id,
                    # "s3_location": s3_result if s3_result else "Failed to store in S3"
                }
            }
        }

    except FileNotFoundError:
        return {
            "statusCode": 500,
            "body": "beatport_response.html file not found. Please run the scraper first to generate this file."
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Scraping error: {str(e)}"
        }

def extract_track_data(element, position):
    """Extract track data from a single track element"""
    track_data = {
        "position": position,
        "title": None,
        "artist": None,
        "remix": None,
        "label": None,
        "genre": None,
        "bpm": None,
        "key": None,
        "release_date": None,
        "beatport_id": None,
        "url": None
    }

    # Debug: Show the structure of the element we're working with
    print(f"\n=== DEBUGGING TRACK {position} ===")
    print(f"Element tag: {element.name}")
    print(f"Element classes: {element.get('class', [])}")
    print(f"Element data attributes: {[k for k in element.attrs.keys() if k.startswith('data-')]}")

    # Try to extract track ID from data attributes
    track_id = (element.get('data-track-id') or element.get('data-id') or
                element.get('data-ec-id') or element.get('data-testid'))
    if track_id and track_id != 'tracks-table-row':  # Don't use the testid as track id
        track_data["beatport_id"] = track_id
        track_data["url"] = f"https://www.beatport.com/track/track/{track_id}"

    # For Beatport's tracks-table-row structure, look for specific patterns
    if element.get('data-testid') == 'tracks-table-row':
        # Look for track title - often in a link or span with specific classes
        title_selectors = [
            'a[href*="/track/"]',  # Link to track page
            '.track-title', '.title',
            '[data-testid*="title"]', '[data-testid*="track"]',
            'span[class*="title"]', 'div[class*="title"]',
            # Look for any text that might be a title in the first few elements
            'span', 'div', 'a'
        ]

        title_element = find_element_by_selectors(element, title_selectors)
        if title_element:
            title_text = clean_text(title_element.get_text())
            if title_text and len(title_text) > 3:
                track_data["title"] = title_text
                print(f"Found title: {title_text}")

                # Extract track ID from URL if present
                href = title_element.get('href', '')
                if '/track/' in href:
                    track_id_match = re.search(r'/track/[^/]+/(\d+)', href)
                    if track_id_match:
                        track_data["beatport_id"] = track_id_match.group(1)
                        track_data["url"] = f"https://www.beatport.com{href}" if href.startswith('/') else href

        # Look for artists - often in links with /artist/ in href
        artist_selectors = [
            'a[href*="/artist/"]',  # Link to artist page
            '.track-artist', '.artist',
            '[data-testid*="artist"]',
            'span[class*="artist"]', 'div[class*="artist"]'
        ]

        artist_elements = []
        for selector in artist_selectors:
            found_elements = element.select(selector)
            if found_elements:
                artist_elements = found_elements
                break

        if artist_elements:
            artist_names = []
            for artist_elem in artist_elements:
                artist_name = clean_text(artist_elem.get_text())
                if artist_name and len(artist_name) > 1:
                    artist_names.append(artist_name)

            if artist_names:
                track_data["artist"] = ', '.join(artist_names)
                print(f"Found artists: {track_data['artist']}")

        # Look for label - often in links with /label/ in href
        label_selectors = [
            'a[href*="/label/"]',
            '.track-label', '.label',
            '[data-testid*="label"]',
            'span[class*="label"]', 'div[class*="label"]'
        ]

        label_element = find_element_by_selectors(element, label_selectors)
        if label_element:
            label_text = clean_text(label_element.get_text())
            if label_text and len(label_text) > 1:
                track_data["label"] = label_text
                print(f"Found label: {label_text}")

        # Look for genre - often in links with /genre/ in href
        genre_selectors = [
            'a[href*="/genre/"]',
            '.track-genre', '.genre',
            '[data-testid*="genre"]',
            'span[class*="genre"]', 'div[class*="genre"]'
        ]

        genre_element = find_element_by_selectors(element, genre_selectors)
        if genre_element:
            genre_text = clean_text(genre_element.get_text())
            if genre_text and len(genre_text) > 1:
                track_data["genre"] = genre_text
                print(f"Found genre: {genre_text}")

        # Look for BPM - usually just a number
        bpm_selectors = [
            '.track-bpm', '.bpm',
            '[data-testid*="bpm"]',
            'span[class*="bpm"]', 'div[class*="bpm"]'
        ]

        bpm_element = find_element_by_selectors(element, bpm_selectors)
        if bpm_element:
            bpm_text = clean_text(bpm_element.get_text())
            bpm_match = re.search(r'(\d+)', bpm_text) if bpm_text else None
            if bmp_match:
                track_data["bpm"] = int(bpm_match.group(1))
                print(f"Found BPM: {track_data['bpm']}")

        # Look for musical key
        key_selectors = [
            '.track-key', '.key',
            '[data-testid*="key"]',
            'span[class*="key"]', 'div[class*="key"]'
        ]

        key_element = find_element_by_selectors(element, key_selectors)
        if key_element:
            key_text = clean_text(key_element.get_text())
            if key_text and len(key_text) > 0:
                track_data["key"] = key_text
                print(f"Found key: {key_text}")

    return track_data

def extract_tracks_from_scripts(soup):
    """Try to extract track data from JavaScript/JSON in script tags"""
    tracks = []

    # Look for script tags that might contain track data
    script_tags = soup.find_all('script')
    print(f"Checking {len(script_tags)} script tags for track data...")

    for script_idx, script in enumerate(script_tags):
        if not script.string:
            continue

        script_content = script.string

        try:
            # Look for __NEXT_DATA__ (Next.js applications)
            if '__NEXT_DATA__' in script_content:
                print(f"Found __NEXT_DATA__ in script {script_idx}")
                json_match = re.search(r'__NEXT_DATA__">\s*({.+})\s*</script>', script_content, re.DOTALL)
                if not json_match:
                    json_match = re.search(r'__NEXT_DATA__.*?=\s*({.+})', script_content, re.DOTALL)

                if json_match:
                    try:
                        json_data = json.loads(json_match.group(1))
                        tracks.extend(parse_nextjs_data(json_data))
                        if tracks:
                            print(f"Successfully extracted {len(tracks)} tracks from __NEXT_DATA__")
                            break
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse __NEXT_DATA__: {e}")

            # Look for window data or other patterns
            elif any(keyword in script_content.lower() for keyword in ['window.', 'tracks', 'chart', 'beatport']):
                print(f"Found potential track data in script {script_idx}")

                # Look for various patterns that might contain track data
                patterns = [
                    r'"tracks"\s*:\s*(\[[^\]]*\])',  # "tracks": [...]
                    r'"chart"\s*:\s*(\[[^\]]*\])',   # "chart": [...]
                    r'"results"\s*:\s*(\[[^\]]*\])', # "results": [...]
                    r'window\.(?:__INITIAL_STATE__|INITIAL_DATA|pageData)\s*=\s*({.+?});',
                    r'(?:var|let|const)\s+(?:tracks|chartData|playlistData)\s*=\s*(\[.+?\]);',
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, script_content, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        try:
                            if isinstance(match, str):
                                data = json.loads(match)
                                parsed_tracks = parse_track_data(data)
                                if parsed_tracks and len(parsed_tracks) > len(tracks):
                                    tracks = parsed_tracks  # Use the better result
                                    print(f"Extracted {len(parsed_tracks)} tracks from pattern")
                        except json.JSONDecodeError:
                            continue

                if tracks and len(tracks) >= 50:  # If we found a good amount, break
                    break

        except Exception as e:
            print(f"Error parsing script {script_idx}: {str(e)}")
            continue

    # If we still don't have enough tracks, try a more aggressive approach
    if len(tracks) < 50:
        print("Trying more aggressive JSON extraction...")
        for script in script_tags:
            if script.string and len(script.string) > 1000:  # Focus on larger scripts
                # Look for any JSON-like structures with id and name
                json_objects = re.findall(r'\{[^{}]*"id"[^{}]*"name"[^{}]*\}', script.string)
                for obj_str in json_objects:
                    try:
                        obj = json.loads(obj_str)
                        if obj.get('id') and obj.get('name') and len(obj.get('name', '')) > 3:
                            track = {
                                "position": len(tracks) + 1,
                                "title": obj.get('name'),
                                "artist": obj.get('artist', {}).get('name') if isinstance(obj.get('artist'), dict) else str(obj.get('artist', '')),
                                "beatport_id": str(obj.get('id')),
                                "url": f"https://www.beatport.com/track/track/{obj.get('id')}" if obj.get('id') else None,
                                "genre": obj.get('genre', {}).get('name') if isinstance(obj.get('genre'), dict) else str(obj.get('genre', '')),
                                "label": obj.get('label', {}).get('name') if isinstance(obj.get('label'), dict) else str(obj.get('label', '')),
                                "bpm": obj.get('bpm'),
                                "key": obj.get('key', {}).get('name') if isinstance(obj.get('key'), dict) else str(obj.get('key', '')),
                            }
                            # Clean up empty strings
                            for key, value in track.items():
                                if value == '':
                                    track[key] = None

                            if track['title'] and len(track['title']) > 3:
                                tracks.append(track)
                                if len(tracks) >= 100:
                                    break
                    except json.JSONDecodeError:
                        continue

                if len(tracks) >= 100:
                    break

    return tracks[:100]  # Limit to top 100

def parse_nextjs_data(data):
    """Parse tracks from Next.js __NEXT_DATA__"""
    tracks = []

    def find_tracks_recursive(obj, path="", depth=0):
        if depth > 10:  # Prevent infinite recursion
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key

                # Look for arrays that might contain tracks
                if key.lower() in ['tracks', 'chart', 'items', 'results', 'data'] and isinstance(value, list) and len(value) > 10:
                    print(f"Found potential track array at: {new_path} with {len(value)} items")
                    for idx, item in enumerate(value):
                        track = parse_track_object(item, idx + 1)
                        if track:
                            tracks.append(track)
                            if len(tracks) >= 100:
                                return
                elif isinstance(value, (dict, list)) and len(tracks) < 100:
                    find_tracks_recursive(value, new_path, depth + 1)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if len(tracks) >= 100:
                    break
                find_tracks_recursive(item, f"{path}[{i}]", depth + 1)

    try:
        find_tracks_recursive(data)
    except Exception as e:
        print(f"Error in recursive search: {e}")

    return tracks[:100]

def parse_track_data(data):
    """Parse tracks from various data structures"""
    tracks = []

    try:
        if isinstance(data, list):
            for idx, item in enumerate(data):
                track = parse_track_object(item, idx + 1)
                if track:
                    tracks.append(track)
                    if len(tracks) >= 100:
                        break
        elif isinstance(data, dict):
            # Look for tracks array within the object
            for key, value in data.items():
                if key.lower() in ['tracks', 'chart', 'items', 'results'] and isinstance(value, list):
                    for idx, item in enumerate(value):
                        track = parse_track_object(item, idx + 1)
                        if track:
                            tracks.append(track)
                            if len(tracks) >= 100:
                                break
                elif isinstance(value, list) and len(value) > 50:  # Large arrays might be tracks
                    for idx, item in enumerate(value):
                        track = parse_track_object(item, idx + 1)
                        if track:
                            tracks.append(track)
                            if len(tracks) >= 100:
                                break
    except Exception as e:
        print(f"Error parsing track data: {str(e)}")

    return tracks

def parse_track_object(track_data, position):
    """Parse a single track object"""
    if not isinstance(track_data, dict):
        return None

    try:
        track = {
            "position": position,
            "title": None,
            "artist": None,
            "remix": None,
            "label": None,
            "genre": None,
            "bpm": None,
            "key": None,
            "release_date": None,
            "beatport_id": None,
            "url": None
        }

        # Extract basic info - try multiple field names
        track["beatport_id"] = str(track_data.get('id') or track_data.get('trackId') or track_data.get('track_id') or '')
        track["title"] = (track_data.get('name') or track_data.get('title') or
                         track_data.get('trackName') or track_data.get('track_name'))

        # Extract artists - handle different structures
        artists_data = track_data.get('artists') or track_data.get('artist')
        if isinstance(artists_data, list) and artists_data:
            artist_names = []
            for artist in artists_data:
                if isinstance(artist, dict):
                    name = artist.get('name') or artist.get('artistName')
                    if name:
                        artist_names.append(name)
                elif isinstance(artist, str):
                    artist_names.append(artist)
            track["artist"] = ', '.join(artist_names) if artist_names else None
        elif isinstance(artists_data, str):
            track["artist"] = artists_data
        elif isinstance(artists_data, dict):
            track["artist"] = artists_data.get('name') or artists_data.get('artistName')

        # Extract other fields with multiple possible names
        label_data = track_data.get('label') or track_data.get('recordLabel')
        if isinstance(label_data, dict):
            track["label"] = label_data.get('name')
        elif isinstance(label_data, str):
            track["label"] = label_data

        genre_data = track_data.get('genre') or track_data.get('genres')
        if isinstance(genre_data, dict):
            track["genre"] = genre_data.get('name')
        elif isinstance(genre_data, list) and genre_data:
            genre_names = []
            for g in genre_data:
                if isinstance(g, dict):
                    genre_names.append(g.get('name', ''))
                elif isinstance(g, str):
                    genre_names.append(g)
            track["genre"] = ' | '.join(g for g in genre_names if g)
        elif isinstance(genre_data, str):
            track["genre"] = genre_data

        track["bpm"] = track_data.get('bpm') or track_data.get('tempo')

        key_data = track_data.get('key') or track_data.get('musicalKey')
        if isinstance(key_data, dict):
            track["key"] = key_data.get('name')
        elif isinstance(key_data, str):
            track["key"] = key_data

        track["release_date"] = (track_data.get('release_date') or track_data.get('releaseDate') or
                                track_data.get('published_date') or track_data.get('date'))

        # Generate URL if we have an ID
        if track["beatport_id"]:
            track["url"] = f"https://www.beatport.com/track/track/{track['beatport_id']}"

        # Only return track if we have at least title and it's not placeholder text
        if (track["title"] and len(track["title"]) > 3 and
            track["title"] not in ['Title', 'Track Title', 'Track Name', 'Title / Artists']):
            return track

    except Exception as e:
        print(f"Error parsing track object: {str(e)}")

    return None

def find_element_by_selectors(parent, selectors):
    """Find an element using multiple CSS selectors"""
    for selector in selectors:
        element = parent.select_one(selector)
        if element:
            return element
    return None

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return None
    return re.sub(r'\s+', ' ', text.strip())

if __name__ == "__main__":
    # Test the function locally
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))
