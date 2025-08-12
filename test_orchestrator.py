#!/usr/bin/env python3
"""
Test script for the simple orchestrator with job counters

This script simulates the full flow:
1. ChartProcessorFunction processes a chart file and creates job record
2. YoutubeMusicSearchFunction processes tracks and updates counters
3. When processed_count == expected_count, JobCompleted event is sent
4. YoutubePlaylistFunction creates playlist automatically

Run this script to test the orchestrator logic locally.
"""

import json
import sys
import os
import uuid
from datetime import datetime

# Add current directory to path so we can import from subdirectories
sys.path.append('/Users/addicted2sounds/Development/music_search')
sys.path.append('/Users/addicted2sounds/Development/music_search/chart-processor')
sys.path.append('/Users/addicted2sounds/Development/music_search/ytmusic')
sys.path.append('/Users/addicted2sounds/Development/music_search/ytplaylist')

def test_chart_processor():
    """Test ChartProcessorFunction with a simulated S3 event"""
    print("=" * 60)
    print("Testing Chart Processor Function")
    print("=" * 60)

    try:
        # Import chart processor app
        from chart_processor import app as chart_app

        # Create test S3 event
        test_event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-charts-bucket"},
                        "object": {"key": "beatport/2024/08/12/top100-test.json"}
                    }
                }
            ]
        }

        print("Simulating chart processor with test event...")
        result = chart_app.lambda_handler(test_event, None)

        print("Chart Processor Result:")
        print(json.dumps(result, indent=2))

        return result

    except Exception as e:
        print(f"Error testing chart processor: {str(e)}")
        return None

def test_ytmusic_processing():
    """Test YoutubeMusicSearchFunction with simulated SQS messages"""
    print("=" * 60)
    print("Testing YouTube Music Processing Function")
    print("=" * 60)

    try:
        # Import ytmusic app
        from ytmusic import app as ytmusic_app

        # Create test job ID
        job_id = str(uuid.uuid4())

        # Create test SQS event with SNS messages
        test_event = {
            "Records": [
                {
                    "body": json.dumps({
                        "Message": json.dumps({
                            "track": {
                                "title": "Verano en NY",
                                "artist": "Toman",
                                "track_id": "test-track-123"
                            },
                            "job_id": job_id,
                            "source_file": "beatport/2024/08/12/top100-test.json",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    })
                },
                {
                    "body": json.dumps({
                        "Message": json.dumps({
                            "track": {
                                "title": "Despacito",
                                "artist": "Luis Fonsi",
                                "track_id": "test-track-456"
                            },
                            "job_id": job_id,
                            "source_file": "beatport/2024/08/12/top100-test.json",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    })
                }
            ]
        }

        print(f"Simulating YouTube Music processing with job ID: {job_id}")
        result = ytmusic_app.lambda_handler(test_event, None)

        print("YouTube Music Processing Result:")
        print(json.dumps(result, indent=2))

        return result

    except Exception as e:
        print(f"Error testing YouTube Music processing: {str(e)}")
        return None

def test_playlist_creation():
    """Test YoutubePlaylistFunction with EventBridge job completion event"""
    print("=" * 60)
    print("Testing Playlist Creation Function")
    print("=" * 60)

    try:
        # Import playlist app
        from ytplaylist import app as playlist_app

        # Create test EventBridge job completion event
        job_id = str(uuid.uuid4())
        test_event = {
            "source": "music-search.orchestrator",
            "detail-type": "Job Completed",
            "detail": {
                "job_id": job_id,
                "s3_bucket": "test-charts-bucket",
                "s3_key": "beatport/2024/08/12/top100-test.json",
                "expected_count": 2,
                "processed_count": 2,
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat()
            }
        }

        print(f"Simulating playlist creation for completed job: {job_id}")
        result = playlist_app.lambda_handler(test_event, None)

        print("Playlist Creation Result:")
        print(json.dumps(result, indent=2))

        return result

    except Exception as e:
        print(f"Error testing playlist creation: {str(e)}")
        return None

def show_orchestrator_flow():
    """Show the complete orchestrator flow"""
    print("=" * 80)
    print("SIMPLE ORCHESTRATOR WITH JOB COUNTERS - COMPLETE FLOW")
    print("=" * 80)

    print("""
Flow Overview:
1. BeatportScraperFunction writes .json to PlaylistsBucket on schedule (EventBridge + S3)
2. ChartProcessorFunction gets S3 event, filters new tracks, creates job record, publishes to SNS
3. YoutubeMusicSearchFunction reads from SQS batches, updates TracksTable and job counters
4. When processed_count == expected_count, JobCompleted event → EventBridge
5. YoutubePlaylistFunction auto-triggered by EventBridge to create playlist

Key Components:
- Jobs Table: tracks expected_count vs processed_count per job
- EventBridge: orchestrates job completion → playlist creation
- Atomic counters: prevent race conditions
- Dead letter queues: handle failures
""")

def main():
    """Run orchestrator tests"""
    show_orchestrator_flow()

    # Test individual components
    print("\n" + "=" * 80)
    print("RUNNING COMPONENT TESTS")
    print("=" * 80)

    # Note: These tests will fail without proper AWS environment setup
    # They are primarily for understanding the flow and debugging logic

    print("\nNOTE: These tests require AWS environment setup and will fail locally.")
    print("They are for understanding the flow and debugging the orchestrator logic.\n")

    # Uncomment to run actual tests (requires AWS setup)
    # test_chart_processor()
    # test_ytmusic_processing()
    # test_playlist_creation()

if __name__ == "__main__":
    main()
