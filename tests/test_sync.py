import sqlite3
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.sync import run_sync
from common.db_helpers import add_allowed_user, save_user_token, get_user_token


def make_fake_track(track_id="t1"):
    return {
        "track": {
            "id": track_id,
            "name": "Song",
            "duration_ms": 200000,
            "popularity": 80,
            "explicit": False,
            "is_local": False,
            "disc_number": 1,
            "track_number": 1,
            "uri": f"spotify:track:{track_id}",
            "href": "http://example.com",
            "external_urls": {"spotify": "http://example.com"},
            "preview_url": None,
            "external_ids": {"isrc": "ABC123"},
            "available_markets": [],
            "artists": [{"id": "a1", "name": "Artist"}],
            "album": {
                "id": "alb1",
                "name": "Album",
                "album_type": "album",
                "release_date": "2020-01-01",
                "release_date_precision": "day",
                "total_tracks": 10,
                "uri": "spotify:album:alb1",
                "href": "http://example.com",
                "external_urls": {"spotify": "http://example.com"},
                "images": [],
                "artists": [],
            },
        },
        "added_at": "2024-01-01T00:00:00Z",
    }


def test_run_sync_inserts_tracks(db_path):
    add_allowed_user(
        __import__("sqlite3").connect(db_path), spotify_user_id="uid1", display_name="alice"
    )
    conn = __import__("sqlite3").connect(db_path)
    save_user_token(conn, "uid1", access_token="tok", refresh_token=None, token_expiry=None)
    conn.close()

    mock_sp = MagicMock()
    mock_sp.current_user_saved_tracks.return_value = {"items": [make_fake_track("t1")], "next": None}
    mock_sp.artists.return_value = {"artists": [{"id": "a1", "name": "Artist", "genres": [], "images": []}]}

    with patch("common.sync._build_spotify_client", return_value=mock_sp):
        run_sync(spotify_user_id="uid1", db_path=db_path)

    conn = __import__("sqlite3").connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM user_tracks WHERE user_id = 'uid1'")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_run_sync_raises_when_no_token(db_path):
    add_allowed_user(
        __import__("sqlite3").connect(db_path), spotify_user_id="uid2", display_name="bob"
    )
    with pytest.raises(ValueError, match="No stored token"):
        run_sync(spotify_user_id="uid2", db_path=db_path)
