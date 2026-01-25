import json


def test_handle_direct_request_validation(ytmusic_app):
    response = ytmusic_app.handle_direct_request({"title": "Test"}, None)
    assert response["statusCode"] == 400

    response = ytmusic_app.handle_direct_request({"author": "Artist"}, None)
    assert response["statusCode"] == 400


def test_handle_sqs_events_success(ytmusic_app, monkeypatch):
    calls = {"update": [], "dlq": []}

    def fake_process(title, artist, track_id=None):
        return {"videoId": "abc123"}

    def fake_update(job_id):
        calls["update"].append(job_id)

    def fake_dlq(track_data, job_id, reason):
        calls["dlq"].append((track_data, job_id, reason))

    monkeypatch.setattr(ytmusic_app, "process_track_search", fake_process)
    monkeypatch.setattr(ytmusic_app, "update_job_counter", fake_update)
    monkeypatch.setattr(ytmusic_app, "send_track_to_dlq", fake_dlq)

    sns_message = {
        "track": {"title": "Song", "artist": "Artist", "track_id": "track123"},
        "job_id": "job-1"
    }
    event = {
        "Records": [
            {"body": json.dumps({"Message": json.dumps(sns_message)})}
        ]
    }

    response = ytmusic_app.handle_sqs_events(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["results"][0]["status"] == "success"
    assert calls["update"] == ["job-1"]
    assert calls["dlq"] == []


def test_handle_sqs_events_not_found(ytmusic_app, monkeypatch):
    calls = {"update": [], "dlq": []}

    def fake_process(title, artist, track_id=None):
        raise ytmusic_app.TrackNotFoundError("not found")

    def fake_update(job_id):
        calls["update"].append(job_id)

    def fake_dlq(track_data, job_id, reason):
        calls["dlq"].append((track_data, job_id, reason))

    monkeypatch.setattr(ytmusic_app, "process_track_search", fake_process)
    monkeypatch.setattr(ytmusic_app, "update_job_counter", fake_update)
    monkeypatch.setattr(ytmusic_app, "send_track_to_dlq", fake_dlq)

    sns_message = {
        "track": {"title": "Song", "artist": "Artist", "track_id": "track123"},
        "job_id": "job-2"
    }
    event = {
        "Records": [
            {"body": json.dumps({"Message": json.dumps(sns_message)})}
        ]
    }

    response = ytmusic_app.handle_sqs_events(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["results"][0]["status"] == "not_found"
    assert calls["update"] == ["job-2"]
    assert len(calls["dlq"]) == 1
