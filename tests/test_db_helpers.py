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
