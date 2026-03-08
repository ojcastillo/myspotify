import sqlite3

import pytest

from common.db_helpers import (
    create_schema,
    add_allowed_user,
    get_allowed_user,
    save_user_token,
    get_user_token,
)


def test_create_schema_creates_allowed_users_table(db):
    cursor = db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='allowed_users'")
    assert cursor.fetchone() is not None


def test_create_schema_creates_user_tokens_table(db):
    cursor = db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_tokens'")
    assert cursor.fetchone() is not None


def test_add_allowed_user_inserts_row(db):
    add_allowed_user(db, spotify_user_id="abc123", display_name="alice")
    row = get_allowed_user(db, "abc123")
    assert row["spotify_user_id"] == "abc123"
    assert row["display_name"] == "alice"
    assert row["created_at"] is not None


def test_add_allowed_user_is_idempotent(db):
    add_allowed_user(db, spotify_user_id="abc123", display_name="alice")
    add_allowed_user(db, spotify_user_id="abc123", display_name="alice_updated")  # should not raise
    # INSERT OR REPLACE means the name updates
    row = get_allowed_user(db, "abc123")
    assert row["display_name"] == "alice_updated"


def test_get_allowed_user_returns_none_for_unknown(db):
    assert get_allowed_user(db, "unknown_id") is None


def test_save_user_token_inserts_row(db):
    add_allowed_user(db, spotify_user_id="abc123", display_name="alice")
    save_user_token(db, "abc123", access_token="tok_a", refresh_token="tok_r", token_expiry="2026-01-01T00:00:00")
    token = get_user_token(db, "abc123")
    assert token["access_token"] == "tok_a"
    assert token["refresh_token"] == "tok_r"


def test_save_user_token_upserts(db):
    add_allowed_user(db, spotify_user_id="abc123", display_name="alice")
    save_user_token(db, "abc123", access_token="old", refresh_token="r", token_expiry="2026-01-01T00:00:00")
    save_user_token(db, "abc123", access_token="new", refresh_token="r2", token_expiry="2026-06-01T00:00:00")
    token = get_user_token(db, "abc123")
    assert token["access_token"] == "new"


def test_get_user_token_returns_none_for_unknown(db):
    assert get_user_token(db, "nobody") is None


from common.db_helpers import get_available_users


def test_get_available_users_returns_empty_when_no_data(db_path):
    # No users in allowed_users or user_tracks → empty list
    result = get_available_users(db_path)
    assert result == []


def test_get_available_users_uses_allowed_users_display_name(db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    from common.db_helpers import add_allowed_user
    add_allowed_user(conn, "111", "alice")
    # Insert a user_tracks row directly
    conn.execute(
        "INSERT OR IGNORE INTO user_tracks (user_id, track_id, added_at) VALUES (?, ?, ?)",
        ("111", "fake_track_id", "2024-01-01T00:00:00"),
    )
    # Need a track row for the FK to work — insert a minimal one
    conn.execute(
        """INSERT OR IGNORE INTO artists (artist_id, artist_name) VALUES ('a1', 'Artist')"""
    )
    conn.execute(
        """INSERT OR IGNORE INTO tracks
           (track_id, track_name, track_duration_ms, album_id, album_name, track_artists, first_artist_id)
           VALUES ('fake_track_id', 'T', 1000, 'alb1', 'Album', '[]', 'a1')"""
    )
    conn.commit()
    conn.close()

    result = get_available_users(db_path)
    assert len(result) == 1
    assert result[0]["user_id"] == "111"
    assert result[0]["display_name"] == "alice"


def test_get_available_users_falls_back_to_user_id_when_not_in_allowed(db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT OR IGNORE INTO artists (artist_id, artist_name) VALUES ('a1', 'Artist')")
    conn.execute(
        """INSERT OR IGNORE INTO tracks
           (track_id, track_name, track_duration_ms, album_id, album_name, track_artists, first_artist_id)
           VALUES ('fake_track_id', 'T', 1000, 'alb1', 'Album', '[]', 'a1')"""
    )
    conn.execute(
        "INSERT OR IGNORE INTO user_tracks (user_id, track_id, added_at) VALUES ('999', 'fake_track_id', '2024-01-01')"
    )
    conn.commit()
    conn.close()

    result = get_available_users(db_path)
    assert len(result) == 1
    assert result[0]["user_id"] == "999"
    assert result[0]["display_name"] == "999"  # falls back to user_id
