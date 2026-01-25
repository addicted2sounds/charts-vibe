import json
from pathlib import Path


def test_is_valid_s3_record(chart_app):
    assert chart_app.is_valid_s3_record({
        "s3": {"bucket": {"name": "bucket"}, "object": {"key": "key"}}
    })
    assert not chart_app.is_valid_s3_record({"s3": {"bucket": {"name": "bucket"}}})
    assert not chart_app.is_valid_s3_record({"s3": "not-a-dict"})


def test_extract_tracks_from_fixture(chart_app):
    payload = json.loads(Path("events/test-chart-data.json").read_text(encoding="utf-8"))
    tracks = chart_app.extract_tracks_from_chart(payload)

    assert len(tracks) == 3
    assert tracks[0]["title"] == "Summer Nights"
    assert tracks[0]["artist"] == "Calvin Harris"
    assert tracks[0]["track_id"]


def test_lambda_handler_counts(chart_app, monkeypatch):
    called = []

    def fake_process(record):
        called.append(record)

    monkeypatch.setattr(chart_app, "process_s3_upload_event", fake_process)

    good_body = json.dumps({
        "Records": [
            {
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": "charts-bucket"},
                    "object": {"key": "beatport/2025/01/01/top100.json"}
                }
            }
        ]
    })

    event = {
        "Records": [
            {"eventSource": "aws:sqs", "body": good_body},
            {"eventSource": "aws:sqs", "body": "not-json"},
            {"eventSource": "aws:s3"}
        ]
    }

    response = chart_app.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["processed"] == 1
    assert body["skipped"] == 2
    assert body["failed"] == 0
    assert len(called) == 1
