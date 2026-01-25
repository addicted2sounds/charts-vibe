import json


def test_derive_playlist_name(ytplaylist_app):
    assert ytplaylist_app.derive_playlist_name_from_s3_key("beatport/2025/01/01/top100.json") == "Beatport Top 100"
    assert ytplaylist_app.derive_playlist_name_from_s3_key("clubtone/2025/01/01/top100.json") == "Clubtone Top 100"
    assert ytplaylist_app.derive_playlist_name_from_s3_key("other/2025/01/01/file.json") == "Other Playlist"


def test_handle_direct_video_ids_validation(ytplaylist_app):
    response = ytplaylist_app.handle_direct_video_ids({"video_ids": ["abc"]})
    assert response["statusCode"] == 400

    response = ytplaylist_app.handle_direct_video_ids({"playlist_name": "Test"})
    assert response["statusCode"] == 400


def test_handle_direct_video_ids_success(ytplaylist_app, monkeypatch):
    monkeypatch.setattr(ytplaylist_app, "get_youtube_service", lambda: object())
    monkeypatch.setattr(ytplaylist_app, "create_public_playlist", lambda service, title, description: "pl123")
    monkeypatch.setattr(ytplaylist_app, "add_videos_to_playlist", lambda service, playlist_id, video_ids: (len(video_ids), []))

    event = {
        "playlist_name": "My Playlist",
        "video_ids": ["id1", "id2"],
        "description": "desc"
    }

    response = ytplaylist_app.handle_direct_video_ids(event)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["success"] is True
    assert body["playlist_id"] == "pl123"
    assert body["videos_added_successfully"] == 2


def test_handle_s3_playlist_creation_missing_data(ytplaylist_app, monkeypatch):
    monkeypatch.setattr(ytplaylist_app, "download_playlist_from_s3", lambda bucket, key: None)

    response = ytplaylist_app.handle_s3_playlist_creation({}, "bucket", "key")
    assert response["statusCode"] == 400


def test_handle_s3_playlist_creation_no_tracks(ytplaylist_app, monkeypatch):
    monkeypatch.setattr(ytplaylist_app, "download_playlist_from_s3", lambda bucket, key: {"tracks": []})

    response = ytplaylist_app.handle_s3_playlist_creation({}, "bucket", "key")
    assert response["statusCode"] == 400


def test_handle_s3_playlist_creation_no_video_ids(ytplaylist_app, monkeypatch):
    monkeypatch.setattr(
        ytplaylist_app,
        "download_playlist_from_s3",
        lambda bucket, key: {"tracks": [{"title": "Song", "artist": "Artist"}], "name": "Test"}
    )
    monkeypatch.setattr(
        ytplaylist_app,
        "get_enriched_tracks_from_dynamodb",
        lambda tracks: ([], [], ["Song - Artist"])
    )

    response = ytplaylist_app.handle_s3_playlist_creation({}, "bucket", "key")
    body = json.loads(response["body"])

    assert response["statusCode"] == 400
    assert "skipped_tracks" in body
