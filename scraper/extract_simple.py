#!/usr/bin/env python3
import json
import re

def extract_tracks_simple():
    """Extract tracks using a simpler approach"""
    with open('beatport_response.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Look for the complete data array that contains all tracks
    # From the grep output, I can see there's a pattern like "data":[{track1},{track2}...]
    # Let's find the pattern where we have a data array containing track objects

    # Find the section with dehydratedState queries
    pattern = r'"queries":\s*\[\s*\{[^}]*"queryKey"[^}]*"top-100-tracks[^}]*\}[^}]*"data":\s*\{[^}]*"data":\s*(\[[^\]]*\])'

    match = re.search(pattern, content, re.DOTALL)
    if match:
        tracks_array_str = match.group(1)
        print(f"Found tracks array, length: {len(tracks_array_str)} characters")

        # The tracks array is very long, let's extract it more carefully
        # Find the complete array by counting brackets
        start_pos = content.find('"data":[{"artists":[')
        if start_pos == -1:
            print("Could not find start of tracks data")
            return None

        # Find the complete array by balancing brackets
        bracket_count = 0
        i = start_pos + 7  # Skip past '"data":'

        if content[i] != '[':
            print("Expected '[' after 'data:'")
            return None

        bracket_count = 1
        i += 1
        start_array = i - 1

        while i < len(content) and bracket_count > 0:
            if content[i] == '[':
                bracket_count += 1
            elif content[i] == ']':
                bracket_count -= 1
            i += 1

        if bracket_count == 0:
            tracks_json = content[start_array:i]
            print(f"Extracted tracks JSON, length: {len(tracks_json)} characters")

            try:
                tracks = json.loads(tracks_json)
                return tracks
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                # Try to fix common issues
                print("First 200 chars:", tracks_json[:200])
                print("Last 200 chars:", tracks_json[-200:])
                return None
        else:
            print("Could not find matching closing bracket")
            return None
    else:
        print("Could not find tracks pattern")
        return None

if __name__ == "__main__":
    tracks = extract_tracks_simple()

    if tracks:
        print(f"\nSuccessfully extracted {len(tracks)} tracks!")

        # Show first few tracks
        for i, track in enumerate(tracks[:5], 1):
            try:
                name = track.get('name', 'Unknown')
                mix_name = track.get('mix_name', '')
                artists = [artist.get('name', 'Unknown') for artist in track.get('artists', [])]
                artists_str = ', '.join(artists)

                print(f"{i}. {name} - {artists_str}")
                if mix_name:
                    print(f"   Mix: {mix_name}")
                print()
            except Exception as e:
                print(f"Error parsing track {i}: {e}")
    else:
        print("Failed to extract tracks")
