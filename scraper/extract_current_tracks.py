#!/usr/bin/env python3

import json
import re
from bs4 import BeautifulSoup

def extract_tracks():
    with open('beatport_response.html', 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    scripts = soup.find_all('script')

    for script in scripts:
        if script.string and 'dehydratedState' in script.string:
            try:
                script_content = script.string

                # Extract the dehydratedState JSON
                start = script_content.find('{"queries"')
                end = script_content.rfind('}') + 1
                if start != -1 and end != -1:
                    json_str = script_content[start:end]
                    data = json.loads(json_str)

                    # Navigate to tracks data
                    if 'queries' in data:
                        for query in data['queries']:
                            if 'state' in query and 'data' in query['state']:
                                tracks_data = query['state']['data']
                                if isinstance(tracks_data, dict) and 'tracks' in tracks_data:
                                    tracks = tracks_data['tracks']
                                    print(f'Found {len(tracks)} tracks in the top 100:')
                                    print('=' * 50)

                                    for i, track in enumerate(tracks[:10]):  # Show first 10
                                        name = track.get('name', 'Unknown')
                                        artists = [a.get('name', 'Unknown') for a in track.get('artists', [])]
                                        mix_name = track.get('mix_name', 'Unknown Mix')
                                        bpm = track.get('bpm', 'Unknown')
                                        genre = track.get('genre', {}).get('name', 'Unknown')

                                        print(f'{i+1:2d}. {name} - {", ".join(artists)}')
                                        print(f'    Mix: {mix_name} | BPM: {bpm} | Genre: {genre}')
                                        print()

                                    print(f'... and {len(tracks) - 10} more tracks')
                                    return tracks

            except Exception as e:
                print(f"Error parsing script: {e}")
                continue

    print("No tracks found in HTML")
    return []

if __name__ == "__main__":
    tracks = extract_tracks()
