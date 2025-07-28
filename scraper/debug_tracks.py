#!/usr/bin/env python3
"""
Debug script to find the correct track data structure in beatport_response.html
"""
import json
import re
from bs4 import BeautifulSoup

def debug_beatport_html():
    """Debug the Beatport HTML to find the correct track structure"""

    try:
        with open('beatport_response.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        print(f"Successfully read {len(html_content)} characters from beatport_response.html")
    except FileNotFoundError:
        print("❌ beatport_response.html file not found!")
        print("Please run: python app.py first to generate this file")
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    # Search for "Verano en NY" in the HTML
    print("🔍 Searching for 'Verano en NY' in the HTML...")

    # Method 1: Search in plain text
    if 'Verano en NY' in html_content:
        print("✅ Found 'Verano en NY' in HTML content!")

        # Find the context around it
        verano_matches = []
        for match in re.finditer(r'.{0,200}Verano en NY.{0,200}', html_content, re.IGNORECASE):
            verano_matches.append(match.group())

        print(f"Found {len(verano_matches)} instances:")
        for i, match in enumerate(verano_matches[:3]):  # Show first 3
            print(f"\nMatch {i+1}:")
            print(match)
    else:
        print("❌ 'Verano en NY' not found in HTML content")

    # Method 2: Search in script tags for JSON data
    print("\n🔍 Searching for 'Verano en NY' in script tags...")
    script_tags = soup.find_all('script')

    verano_scripts = []
    for i, script in enumerate(script_tags):
        if script.string and 'Verano en NY' in script.string:
            verano_scripts.append((i, script.string))

    if verano_scripts:
        print(f"✅ Found 'Verano en NY' in {len(verano_scripts)} script tags!")

        for script_idx, script_content in verano_scripts:
            print(f"\n--- Script {script_idx} ---")
            # Find the specific part containing Verano en NY
            for match in re.finditer(r'.{0,500}Verano en NY.{0,500}', script_content, re.IGNORECASE):
                print(f"Context around 'Verano en NY':")
                print(match.group())

                # Try to extract JSON object containing this track
                expanded_match = re.search(r'\{[^{}]*Verano en NY[^{}]*\}', script_content, re.IGNORECASE)
                if expanded_match:
                    print(f"\nPotential JSON object:")
                    try:
                        json_obj = json.loads(expanded_match.group())
                        print(json.dumps(json_obj, indent=2))
                    except json.JSONDecodeError:
                        print(expanded_match.group())

                print("-" * 80)
    else:
        print("❌ 'Verano en NY' not found in any script tags")

    # Method 3: Look for common JavaScript data patterns
    print("\n🔍 Looking for common JavaScript data patterns...")

    patterns_to_check = [
        (r'__NEXT_DATA__', 'Next.js data'),
        (r'window\.__INITIAL_STATE__', 'Initial state'),
        (r'window\.pageData', 'Page data'),
        (r'"tracks"\s*:', 'Tracks array'),
        (r'"chart"\s*:', 'Chart data'),
        (r'playlistData', 'Playlist data'),
    ]

    for pattern, description in patterns_to_check:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        if matches:
            print(f"✅ Found {len(matches)} instances of {description}")

            # For each match, try to extract surrounding JSON
            for match_obj in re.finditer(pattern, html_content, re.IGNORECASE):
                start = match_obj.start()
                # Look for JSON structure around this match
                json_match = re.search(r'\{.{0,2000}\}', html_content[start:start+5000])
                if json_match:
                    try:
                        # Try to parse as JSON
                        potential_json = json_match.group()
                        if 'Verano' in potential_json:
                            print(f"\n{description} containing 'Verano':")
                            # Try to parse and pretty print
                            try:
                                parsed = json.loads(potential_json)
                                print(json.dumps(parsed, indent=2)[:1000] + "..." if len(str(parsed)) > 1000 else json.dumps(parsed, indent=2))
                            except json.JSONDecodeError:
                                print(potential_json[:500] + "..." if len(potential_json) > 500 else potential_json)
                            break
                    except:
                        continue
        else:
            print(f"❌ No {description} found")

    # Method 4: Search for HTML elements that might contain track data
    print("\n🔍 Searching for HTML elements containing 'Verano en NY'...")

    # Find all elements containing this text
    elements_with_verano = soup.find_all(string=re.compile(r'Verano en NY', re.IGNORECASE))

    if elements_with_verano:
        print(f"✅ Found 'Verano en NY' in {len(elements_with_verano)} HTML elements!")

        for i, element in enumerate(elements_with_verano):
            parent = element.parent
            print(f"\nElement {i+1}:")
            print(f"Tag: {parent.name}")
            print(f"Classes: {parent.get('class', [])}")
            print(f"Attributes: {dict(parent.attrs)}")
            print(f"Text: {element.strip()}")

            # Check the parent's parent for more context
            if parent.parent:
                grandparent = parent.parent
                print(f"Parent tag: {grandparent.name}")
                print(f"Parent classes: {grandparent.get('class', [])}")
                print(f"Parent attributes: {dict(grandparent.attrs)}")

            print("-" * 60)
    else:
        print("❌ 'Verano en NY' not found in any HTML elements")

    # Method 5: Look for data attributes that might contain track info
    print("\n🔍 Looking for elements with data attributes...")

    data_attrs_to_check = ['data-track-id', 'data-ec-id', 'data-ec-name', 'data-test-id']

    for attr in data_attrs_to_check:
        elements = soup.find_all(attrs={attr: True})
        print(f"{attr}: {len(elements)} elements")

        # Check first few elements for content
        for elem in elements[:3]:
            if 'Verano' in elem.get_text():
                print(f"  ✅ Found 'Verano' in element with {attr}={elem.get(attr)}")
                print(f"     Text: {elem.get_text()[:100]}...")

if __name__ == "__main__":
    debug_beatport_html()
