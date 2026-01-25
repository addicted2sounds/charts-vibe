def test_clubtone_fixture_parsing(clubtone_html, clubtone_module):
    tracks = clubtone_module.extract_tracks(clubtone_html, limit=5)

    assert len(tracks) == 5

    first = tracks[0]
    assert first["position"] == 1
    assert first["title"] == "Discoteka (Extended Mix)"
    assert first["artist"] == "Benny Benassi & Tobias Gerard"
    assert first["genre"] == "Melodic House & Techno"
    assert first["clubtone_id"] == "660060"
    assert first["url"].startswith("https://clubtone.do.am/music/")
    assert first["track_id"]
