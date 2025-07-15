import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

def lambda_handler(event, context):
    """
    Lambda function to scrape Beatport's top-100 tracks
    """
    try:
        # Beatport top-100 URL
        url = "https://www.beatport.com/top-100"

        # Headers to mimic a real browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Make the request
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        tracks = []

        # Find track containers - Beatport uses different selectors
        # Look for track list items or containers
        track_elements = soup.find_all(['li', 'div'], class_=re.compile(r'track|item|row', re.I))

        if not track_elements:
            # Try alternative selectors
            track_elements = soup.find_all('tr')  # Table rows

        if not track_elements:
            # Try to find any container with track data
            track_elements = soup.find_all(attrs={'data-track-id': True})

        for idx, element in enumerate(track_elements[:100]):  # Limit to top 100
            try:
                track_data = extract_track_data(element, idx + 1)
                if track_data and track_data.get('title') and track_data.get('artist'):
                    tracks.append(track_data)

                # Stop if we have 100 tracks
                if len(tracks) >= 100:
                    break

            except Exception as e:
                print(f"Error extracting track {idx + 1}: {str(e)}")
                continue

        # If we didn't find tracks with the above method, try JSON data
        if not tracks:
            tracks = extract_tracks_from_scripts(soup)

        return {
            "statusCode": 200,
            "body": {
                "total_tracks": len(tracks),
                "tracks": tracks,
                "source": "beatport-top-100",
                "scraped_at": context.aws_request_id if context else "local"
            }
        }

    except requests.RequestException as e:
        return {
            "statusCode": 500,
            "body": f"Request error: {str(e)}"
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

    # Try to extract track ID from data attributes
    track_id = element.get('data-track-id') or element.get('data-id')
    if track_id:
        track_data["beatport_id"] = track_id
        track_data["url"] = f"https://www.beatport.com/track/track/{track_id}"

    # Extract title - try multiple selectors
    title_selectors = [
        '.track-title', '.title', '[data-track-title]', 'a[href*="/track/"]'
    ]
    title_element = find_element_by_selectors(element, title_selectors)
    if title_element:
        track_data["title"] = clean_text(title_element.get_text() or title_element.get('data-track-title', ''))

    # Extract artist - try multiple selectors
    artist_selectors = [
        '.track-artist', '.artist', '[data-track-artist]', 'a[href*="/artist/"]'
    ]
    artist_element = find_element_by_selectors(element, artist_selectors)
    if artist_element:
        track_data["artist"] = clean_text(artist_element.get_text() or artist_element.get('data-track-artist', ''))

    # Extract remix info
    remix_selectors = ['.track-remix', '.remix', '[data-track-remix]']
    remix_element = find_element_by_selectors(element, remix_selectors)
    if remix_element:
        track_data["remix"] = clean_text(remix_element.get_text())

    # Extract label
    label_selectors = ['.track-label', '.label', '[data-track-label]', 'a[href*="/label/"]']
    label_element = find_element_by_selectors(element, label_selectors)
    if label_element:
        track_data["label"] = clean_text(label_element.get_text())

    # Extract genre
    genre_selectors = ['.track-genre', '.genre', '[data-track-genre]', 'a[href*="/genre/"]']
    genre_element = find_element_by_selectors(element, genre_selectors)
    if genre_element:
        track_data["genre"] = clean_text(genre_element.get_text())

    # Extract BPM
    bpm_selectors = ['.track-bpm', '.bpm', '[data-track-bpm]']
    bpm_element = find_element_by_selectors(element, bpm_selectors)
    if bpm_element:
        bpm_text = clean_text(bpm_element.get_text())
        bpm_match = re.search(r'(\d+)', bpm_text)
        if bpm_match:
            track_data["bpm"] = int(bpm_match.group(1))

    # Extract musical key
    key_selectors = ['.track-key', '.key', '[data-track-key]']
    key_element = find_element_by_selectors(element, key_selectors)
    if key_element:
        track_data["key"] = clean_text(key_element.get_text())

    return track_data

def extract_tracks_from_scripts(soup):
    """Try to extract track data from JavaScript/JSON in script tags"""
    tracks = []

    # Look for script tags that might contain track data
    script_tags = soup.find_all('script')

    for script in script_tags:
        if script.string:
            # Look for JSON data patterns
            try:
                # Common patterns for track data in JS
                if 'tracks' in script.string.lower() or 'chart' in script.string.lower():
                    # Try to extract JSON objects
                    json_matches = re.findall(r'\{[^{}]*"title"[^{}]*\}', script.string)
                    for match in json_matches:
                        try:
                            track_obj = json.loads(match)
                            if 'title' in track_obj:
                                tracks.append({
                                    "position": len(tracks) + 1,
                                    "title": track_obj.get('title'),
                                    "artist": track_obj.get('artist') or track_obj.get('artists'),
                                    "beatport_id": track_obj.get('id'),
                                    "url": f"https://www.beatport.com/track/track/{track_obj.get('id')}" if track_obj.get('id') else None
                                })
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

    return tracks

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
