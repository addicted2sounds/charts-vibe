#!/usr/bin/env python3
import json
import re
from bs4 import BeautifulSoup

def extract_tracks_from_json_data():
    """Extract track data directly from the JSON data embedded in HTML"""
    with open('beatport_response.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    # The data appears to be directly in the HTML as JSON, let's find the track data pattern
    # Looking for the pattern where we have track objects with "artists", "name", "mix_name", etc.

    # Find the track data pattern - it starts with {"artists":[...] and contains track info
    track_pattern = r'\{"artists":\[\{[^}]+\}[^\]]*\],"publish_status":"published"[^}]+\}'

    # Find all matches
    matches = re.findall(track_pattern, html_content)

    tracks = []
    for match in matches:
        try:
            # Add closing braces to complete the JSON
            json_str = match
            track_data = json.loads(json_str)
            tracks.append(track_data)
        except json.JSONDecodeError as e:
            print(f"JSON decode error for match: {e}")
            continue

    if tracks:
        print(f"Found {len(tracks)} tracks using regex pattern")
        return tracks

    # Alternative approach: extract the large JSON structure
    # Look for the dehydratedState pattern we saw in the grep output
    dehydrated_pattern = r'"dehydratedState":\{"queries":\[.*?\]\}'
    dehydrated_match = re.search(dehydrated_pattern, html_content, re.DOTALL)

    if dehydrated_match:
        try:
            # Extract just the dehydratedState part
            dehydrated_json = '{' + dehydrated_match.group(0) + '}'
            data = json.loads(dehydrated_json)

            # Navigate to the tracks
            queries = data.get('dehydratedState', {}).get('queries', [])
            for query in queries:
                if 'top-100-tracks' in str(query.get('queryKey', [])):
                    query_data = query.get('data', {})
                    if 'data' in query_data:
                        tracks = query_data['data']
                        print(f"Found {len(tracks)} tracks in dehydratedState")
                        return tracks
        except json.JSONDecodeError as e:
            print(f"Error parsing dehydratedState: {e}")

    print("No tracks found")
    return []

def parse_track_info(track):
    """Parse individual track information"""
    try:
        name = track.get('name', 'Unknown')
        mix_name = track.get('mix_name', '')

        # Get artist names
        artists = track.get('artists', [])
        artist_names = [artist.get('name', 'Unknown') for artist in artists]

        # Get genre
        genre = track.get('genre', {}).get('name', 'Unknown')

        # Get label
        release = track.get('release', {})
        label = release.get('label', {}).get('name', 'Unknown')

        # Get BPM
        bpm = track.get('bpm', 0)

        # Get key
        key_info = track.get('key', {})
        key_name = key_info.get('name', 'Unknown')

        return {
            'name': name,
            'mix_name': mix_name,
            'artists': artist_names,
            'genre': genre,
            'label': label,
            'bpm': bpm,
            'key': key_name
        }
    except Exception as e:
        print(f"Error parsing track: {e}")
        return None

if __name__ == "__main__":
    tracks = extract_tracks_from_json_data()

    if tracks:
        print(f"\nSuccessfully extracted {len(tracks)} tracks:")

        for i, track in enumerate(tracks[:10], 1):  # Show first 10 tracks
            parsed = parse_track_info(track)
            if parsed:
                artists_str = ', '.join(parsed['artists'])
                mix_info = f" ({parsed['mix_name']})" if parsed['mix_name'] else ""
                print(f"{i}. {parsed['name']}{mix_info} - {artists_str}")
                print(f"   Genre: {parsed['genre']} | BPM: {parsed['bpm']} | Key: {parsed['key']} | Label: {parsed['label']}")
                print()
    else:
        print("Failed to extract tracks")
