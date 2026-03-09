import json


class FakeSSMClient:
    def __init__(self):
        self.put_calls = []

    def put_parameter(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"Version": len(self.put_calls)}


class FakeCredentials:
    refreshed_token = "refreshed-access-token"
    refreshed_refresh_token = None
    refresh_error = None
    last_instance = None

    def __init__(self, token, refresh_token, token_uri, client_id, client_secret):
        self.token = token
        self.refresh_token = refresh_token
        self.token_uri = token_uri
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_calls = 0
        self.refresh_request = None
        FakeCredentials.last_instance = self

    def refresh(self, request):
        self.refresh_calls += 1
        self.refresh_request = request
        if self.refresh_error:
            raise self.refresh_error
        self.token = self.refreshed_token
        if self.refreshed_refresh_token is not None:
            self.refresh_token = self.refreshed_refresh_token


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
    monkeypatch.setattr(ytplaylist_app, "put_playlist_record", lambda record: True)
    monkeypatch.setattr(ytplaylist_app, "update_playlist_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ytplaylist_app,
        "add_videos_to_playlist",
        lambda service, playlist_id, video_ids: (len(video_ids), [], None)
    )

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


def test_get_youtube_service_refreshes_and_persists_access_token(ytplaylist_app, monkeypatch):
    ssm_client = FakeSSMClient()
    build_calls = []

    FakeCredentials.refreshed_token = "fresh-access-token"
    FakeCredentials.refreshed_refresh_token = None
    FakeCredentials.refresh_error = None
    FakeCredentials.last_instance = None

    monkeypatch.setattr(
        ytplaylist_app,
        "load_client_secrets_from_ssm",
        lambda: {
            "token_uri": "https://oauth.example/token",
            "client_id": "client-id",
            "client_secret": "client-secret"
        }
    )
    monkeypatch.setattr(
        ytplaylist_app,
        "get_oauth_tokens_from_store",
        lambda: {
            "access_token": "stale-access-token",
            "refresh_token": "stable-refresh-token"
        }
    )
    monkeypatch.setattr(ytplaylist_app, "Credentials", FakeCredentials)
    monkeypatch.setattr(ytplaylist_app, "Request", lambda: "request-object")
    monkeypatch.setattr(ytplaylist_app.boto3, "client", lambda service_name: ssm_client)
    monkeypatch.setattr(
        ytplaylist_app,
        "build",
        lambda service_name, version, credentials: build_calls.append((service_name, version, credentials)) or object()
    )

    service = ytplaylist_app.get_youtube_service()

    assert service is not None
    assert FakeCredentials.last_instance.refresh_calls == 1
    assert FakeCredentials.last_instance.refresh_request == "request-object"
    assert build_calls[0][0:2] == ("youtube", "v3")
    assert build_calls[0][2].token == "fresh-access-token"
    assert [call["Name"] for call in ssm_client.put_calls] == ["/youtube/access_token"]


def test_get_youtube_service_persists_rotated_refresh_token(ytplaylist_app, monkeypatch):
    ssm_client = FakeSSMClient()

    FakeCredentials.refreshed_token = "fresh-access-token"
    FakeCredentials.refreshed_refresh_token = "rotated-refresh-token"
    FakeCredentials.refresh_error = None
    FakeCredentials.last_instance = None

    monkeypatch.setattr(
        ytplaylist_app,
        "load_client_secrets_from_ssm",
        lambda: {
            "token_uri": "https://oauth.example/token",
            "client_id": "client-id",
            "client_secret": "client-secret"
        }
    )
    monkeypatch.setattr(
        ytplaylist_app,
        "get_oauth_tokens_from_store",
        lambda: {
            "access_token": "stale-access-token",
            "refresh_token": "stable-refresh-token"
        }
    )
    monkeypatch.setattr(ytplaylist_app, "Credentials", FakeCredentials)
    monkeypatch.setattr(ytplaylist_app, "Request", lambda: "request-object")
    monkeypatch.setattr(ytplaylist_app.boto3, "client", lambda service_name: ssm_client)
    monkeypatch.setattr(ytplaylist_app, "build", lambda service_name, version, credentials: object())

    service = ytplaylist_app.get_youtube_service()

    assert service is not None
    assert [call["Name"] for call in ssm_client.put_calls] == [
        "/youtube/access_token",
        "/youtube/refresh_token"
    ]
    assert ssm_client.put_calls[1]["Value"] == "rotated-refresh-token"


def test_handle_direct_video_ids_returns_auth_failure_when_refresh_fails(ytplaylist_app, monkeypatch):
    calls = {
        "build": False,
        "create_public_playlist": False
    }

    FakeCredentials.refreshed_token = "fresh-access-token"
    FakeCredentials.refreshed_refresh_token = None
    FakeCredentials.refresh_error = RuntimeError("refresh failed")
    FakeCredentials.last_instance = None

    monkeypatch.setattr(
        ytplaylist_app,
        "load_client_secrets_from_ssm",
        lambda: {
            "token_uri": "https://oauth.example/token",
            "client_id": "client-id",
            "client_secret": "client-secret"
        }
    )
    monkeypatch.setattr(
        ytplaylist_app,
        "get_oauth_tokens_from_store",
        lambda: {
            "access_token": "stale-access-token",
            "refresh_token": "stable-refresh-token"
        }
    )
    monkeypatch.setattr(ytplaylist_app, "Credentials", FakeCredentials)
    monkeypatch.setattr(ytplaylist_app, "Request", lambda: "request-object")

    def fake_build(*args, **kwargs):
        calls["build"] = True
        return object()

    def fake_create_public_playlist(*args, **kwargs):
        calls["create_public_playlist"] = True
        return "pl123"

    monkeypatch.setattr(ytplaylist_app, "build", fake_build)
    monkeypatch.setattr(ytplaylist_app, "create_public_playlist", fake_create_public_playlist)

    response = ytplaylist_app.handle_direct_video_ids({
        "playlist_name": "My Playlist",
        "video_ids": ["id1"]
    })
    body = json.loads(response["body"])

    assert response["statusCode"] == 500
    assert body["error"] == "Failed to authenticate with YouTube"
    assert calls["build"] is False
    assert calls["create_public_playlist"] is False


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


def test_handle_s3_playlist_creation_resume_uses_existing_playlist_id(ytplaylist_app, monkeypatch):
    added_calls = []

    monkeypatch.setattr(
        ytplaylist_app,
        "download_playlist_from_s3",
        lambda bucket, key: {
            "playlist_id": "source-playlist",
            "name": "Test Playlist",
            "tracks": [{"title": "Song 1", "artist": "Artist 1"}, {"title": "Song 2", "artist": "Artist 2"}]
        }
    )
    monkeypatch.setattr(
        ytplaylist_app,
        "get_enriched_tracks_from_dynamodb",
        lambda tracks: (tracks, ["vid-1", "vid-2"], [])
    )
    monkeypatch.setattr(ytplaylist_app, "get_youtube_service", lambda: object())
    monkeypatch.setattr(
        ytplaylist_app,
        "create_public_playlist",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("resume path should not create a new playlist"))
    )
    monkeypatch.setattr(ytplaylist_app, "put_playlist_record", lambda record: True)
    monkeypatch.setattr(ytplaylist_app, "update_playlist_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ytplaylist_app,
        "add_videos_to_playlist",
        lambda service, playlist_id, video_ids, start_index=0: added_calls.append(
            (playlist_id, video_ids, start_index)
        ) or (1, [], None)
    )

    response = ytplaylist_app.handle_s3_playlist_creation(
        {
            "playlist_id": "existing-playlist-id",
            "resume": True,
            "resume_from": 1,
            "playlist_name": "Resume Playlist"
        },
        "bucket",
        "key"
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["playlist_id"] == "existing-playlist-id"
    assert body["videos_added_successfully"] == 1
    assert added_calls == [("existing-playlist-id", ["vid-1", "vid-2"], 1)]
