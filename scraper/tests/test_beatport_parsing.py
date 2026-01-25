import beatport


def test_beatport_fixture_parsing(beatport_html):
    tracks = beatport.extract_tracks(beatport_html, limit=5)

    assert len(tracks) == 5

    first = tracks[0]
    assert first["position"] == 1
    assert first["title"] == "Greece 2000 Max Styler Extended Rework"
    assert first["artist"] == "Three Drives, Three Drives On A Vinyl, Max Styler"
    assert first["beatport_id"] == "23011269"
    assert first["url"].startswith("https://www.beatport.com/track/")
    assert first["bpm"] == 129
    assert first["key"] == "Ab Major"
    assert first["track_id"]
