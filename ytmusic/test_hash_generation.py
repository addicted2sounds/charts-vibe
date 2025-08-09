#!/usr/bin/env python3
"""
Simple test for hash generation function without dependencies
"""

import hashlib
import re

def generate_track_id(title, artist):
    """
    Generate a deterministic track ID based on normalized title and artist using SHA-256
    """
    def normalize_string(s):
        if not s:
            return ""
        # Convert to lowercase, remove extra spaces, remove special chars
        s = s.lower().strip()
        s = re.sub(r'[^\w\s]', '', s)  # Remove special characters
        s = re.sub(r'\s+', ' ', s)     # Normalize whitespace
        return s

    normalized_title = normalize_string(title)
    normalized_artist = normalize_string(artist)

    # Create combined string
    combined = f"{normalized_artist}::{normalized_title}"

    # Generate SHA-256 hash
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return hash_obj.hexdigest()

def test_hash_generation():
    """Test the hash generation and normalization"""
    print("Testing SHA-256 hash-based ID generation:")
    print("=" * 50)

    test_cases = [
        ("Bohemian Rhapsody", "Queen"),
        ("bohemian rhapsody", "queen"),  # Should be same as above
        ("BOHEMIAN RHAPSODY!", "QUEEN."),  # Should be same as above
        ("  Bohemian   Rhapsody  ", "  Queen  "),  # Should be same as above
        ("Let It Be", "The Beatles"),
        ("Another One Bites the Dust", "Queen"),
        ("Verano en NY", "Toman"),
    ]

    for title, artist in test_cases:
        track_id = generate_track_id(title, artist)
        print(f'Title: "{title}" | Artist: "{artist}"')
        print(f'ID: {track_id}')
        print(f'Short ID: {track_id[:16]}...')
        print()

    # Test normalization - these should all produce the same ID
    print("Normalization Test:")
    print("-" * 30)

    variations = [
        ("Bohemian Rhapsody", "Queen"),
        ("bohemian rhapsody", "queen"),
        ("BOHEMIAN RHAPSODY", "QUEEN"),
        ("Bohemian Rhapsody!", "Queen."),
        ("  Bohemian   Rhapsody  ", "  Queen  "),
    ]

    ids = []
    for title, artist in variations:
        track_id = generate_track_id(title, artist)
        ids.append(track_id)
        print(f'"{title}" by "{artist}" -> {track_id[:16]}...')

    all_same = all(id == ids[0] for id in ids)
    print(f"\nAll normalized variations produce the same ID: {all_same}")

    if all_same:
        print("✅ Normalization working correctly!")
    else:
        print("❌ Normalization not working correctly!")

if __name__ == "__main__":
    test_hash_generation()
