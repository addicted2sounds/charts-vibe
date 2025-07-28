#!/usr/bin/env python3
import json
import re
from bs4 import BeautifulSoup

def extract_top_100_tracks():
    """Extract top 100 tracks from Beatport HTML file"""
    with open('beatport_response.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # Parse the HTML
    soup = BeautifulSoup(html, 'html.parser')

    # Find the __NEXT_DATA__ script tag
    next_data_script = soup.find('script', string=re.compile('__NEXT_DATA__'))

    if next_data_script:
        script_content = next_data_script.string
        # Extract JSON from the script content
        json_match = re.search(r'__NEXT_DATA__.*?(\{.*\})', script_content, re.DOTALL)

        if json_match:
            json_str = json_match.group(1)
            try:
                data = json.loads(json_str)

                # Navigate through the data structure to find tracks
                if 'props' in data and 'pageProps' in data['props']:
                    page_props = data['props']['pageProps']

                    # First check for dehydratedState (React Query cache)
                    if 'dehydratedState' in page_props:
                        queries = page_props['dehydratedState'].get('queries', [])
                        for query in queries:
                            if 'queryKey' in query and 'top-100-tracks' in str(query['queryKey']):
                                if 'data' in query and 'data' in query['data']:
                                    tracks = query['data']['data']
                                    print(f"Found {len(tracks)} tracks in React Query cache")
                                    return tracks

                    # If no tracks found in dehydratedState, check other locations
                    print("Searching for tracks in other locations...")

                    # Print the structure to understand the data layout
                    def explore_structure(obj, path="", max_depth=3):
                        if max_depth <= 0:
                            return

                        if isinstance(obj, dict):
                            for key, value in obj.items():
                                current_path = f"{path}.{key}" if path else key
                                if key in ['tracks', 'data', 'results'] and isinstance(value, list) and len(value) > 0:
                                    print(f"Found array at {current_path} with {len(value)} items")
                                    # Check if first item looks like a track
                                    if value and isinstance(value[0], dict) and 'name' in value[0]:
                                        print(f"  - First item has name: {value[0].get('name', 'N/A')}")
                                        return value
                                explore_structure(value, current_path, max_depth - 1)
                        elif isinstance(obj, list) and obj:
                            explore_structure(obj[0], f"{path}[0]", max_depth - 1)

                    tracks = explore_structure(page_props)
                    if tracks:
                        return tracks

                print("No tracks found in expected locations")
                return None

            except json.JSONError as e:
                print(f"JSON parsing error: {e}")
                return None
        else:
            print("Could not extract JSON from __NEXT_DATA__ script")
            return None
    else:
        print("No __NEXT_DATA__ script tag found")
        return None

if __name__ == "__main__":
    tracks = extract_top_100_tracks()
    if tracks:
        print(f"\nFound {len(tracks)} tracks:")
        for i, track in enumerate(tracks[:5], 1):  # Show first 5 tracks
            name = track.get('name', 'Unknown')
            artists = track.get('artists', [])
            artist_names = [artist.get('name', 'Unknown') for artist in artists]
            mix_name = track.get('mix_name', '')
            print(f"{i}. {name} - {', '.join(artist_names)} ({mix_name})")
    else:
        print("No tracks found")
