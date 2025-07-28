#!/usr/bin/env python3
import json
from bs4 import BeautifulSoup
import re

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
    bpm_match = re.search(r'\b(\d{2,3})\b', all_text)  # 2-3 digit numbers
    if bpm_match:
        bpm_value = int(bpm_match.group(1))
        if 80 <= bpm_value <= 200:  # Reasonable BPM range
            track_data["bpm"] = bpm_value
            print(f"Found BPM: {bpm_value}")

    # Look for musical key - pattern like "4A", "12B", etc.
    key_match = re.search(r'\b(\d{1,2}[A-G])\b', all_text)
    if key_match:
        track_data["key"] = key_match.group(1)
        print(f"Found key: {track_data['key']}")

    return track_data

def main():
    """Test the extraction with the data-testid approach"""
    print("Testing track extraction with data-testid='tracks-table-row'...")

    with open('beatport_response.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all track rows
    track_elements = soup.find_all('div', {'data-testid': 'tracks-table-row'})
    print(f"Found {len(track_elements)} track elements")

    if not track_elements:
        print("No track elements found!")
        return

    tracks = []

    # Process first 10 tracks to see the pattern
    for idx, element in enumerate(track_elements[:10], 1):
        try:
            track_data = extract_track_data_simple(element, idx)

            # Validate the track
            if track_data.get('title') and track_data.get('artist'):
                tracks.append(track_data)
                print(f"✓ Valid track: {track_data['title']} - {track_data['artist']}")
            else:
                print(f"✗ Invalid track - missing title or artist")
                print(f"  Title: {track_data.get('title')}")
                print(f"  Artist: {track_data.get('artist')}")

        except Exception as e:
            print(f"Error processing track {idx}: {e}")

    print(f"\nSuccessfully extracted {len(tracks)} valid tracks")

    # Show first few tracks
    if tracks:
        print("\nFirst few tracks:")
        for track in tracks[:5]:
            print(f"{track['position']}. {track['title']} - {track['artist']}")
            if track.get('label'):
                print(f"   Label: {track['label']}")
            if track.get('genre'):
                print(f"   Genre: {track['genre']}")
            print()

if __name__ == "__main__":
    main()
