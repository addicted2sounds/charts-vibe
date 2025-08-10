#!/usr/bin/env python3
"""
Local test script for the scraper function to debug import issues
"""

import sys
import os

# Add the scraper directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scraper'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'common'))

try:
    print("Testing imports...")
    import requests
    print("✓ requests imported successfully")

    from bs4 import BeautifulSoup
    print("✓ BeautifulSoup imported successfully")

    import boto3
    print("✓ boto3 imported successfully")

    # Test the utils import
    from scraper.utils import generate_track_id
    print("✓ utils.generate_track_id imported successfully")

    # Test generating a track ID
    test_id = generate_track_id("Test Track", "Test Artist")
    print(f"✓ Generated test track ID: {test_id}")

    # Test importing the main scraper app
    from scraper.app import lambda_handler, extract_track_data_simple
    print("✓ scraper.app functions imported successfully")

    print("\nAll imports successful! The scraper should work locally.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("This could be the same issue happening in LocalStack.")

    # Check if requirements are installed
    print("\nChecking installed packages...")
    import subprocess
    result = subprocess.run([sys.executable, '-m', 'pip', 'list'], capture_output=True, text=True)
    if 'requests' in result.stdout:
        print("✓ requests is installed in current environment")
    else:
        print("❌ requests is NOT installed in current environment")

    if 'beautifulsoup4' in result.stdout:
        print("✓ beautifulsoup4 is installed in current environment")
    else:
        print("❌ beautifulsoup4 is NOT installed in current environment")

except Exception as e:
    print(f"❌ Other error: {e}")
