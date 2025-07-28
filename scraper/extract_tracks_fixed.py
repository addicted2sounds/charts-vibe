#!/usr/bin/env python3

import json
import re
from bs4 import BeautifulSoup

def extract_tracks_corrected():
    with open('beatport_response.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the script tag containing __NEXT_DATA__
    next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content, re.DOTALL)

    if next_data_match:
        try:
            json_str = next_data_match.group(1)
            data = json.loads(json_str)

            # Navigate through the data structure
            props = data.get('props', {})
            page_props = props.get('pageProps', {})
            dehydrated_state = page_props.get('dehydratedState', {})
            queries = dehydrated_state.get('queries', [])

            for query in queries:
                state = query.get('state', {})
                query_data = state.get('data', {})

                if 'tracks' in query_data:
                    tracks = query_data['tracks']
                    print(f'Found {len(tracks)} tracks in the top 100:')
                    print('=' * 60)

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

                    # Check if "Verano" is in any track name
                    verano_tracks = [t for t in tracks if 'verano' in t.get('name', '').lower()]
                    if verano_tracks:
                        print('\n🎵 Found tracks with "Verano":')
                        for track in verano_tracks:
                            name = track.get('name', 'Unknown')
                            artists = [a.get('name', 'Unknown') for a in track.get('artists', [])]
                            print(f'   - {name} by {", ".join(artists)}')
                    else:
                        print('\n❌ No tracks containing "Verano" found in this dataset')

                    return tracks

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")

    print("No tracks found in HTML")
    return []

if __name__ == "__main__":
    tracks = extract_tracks_corrected()
