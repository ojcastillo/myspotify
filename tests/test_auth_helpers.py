import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_is_user_allowed_returns_true_for_known_user(db):
    from common.db_helpers import add_allowed_user
    from app import is_user_allowed

    add_allowed_user(db, spotify_user_id="abc123", display_name="alice")
    assert is_user_allowed(db, "abc123") is True


def test_is_user_allowed_returns_false_for_unknown(db):
    from app import is_user_allowed

    assert is_user_allowed(db, "nobody") is False


def test_persist_token_saves_to_db(db):
    from common.db_helpers import add_allowed_user, get_user_token
    from app import persist_token

    add_allowed_user(db, spotify_user_id="abc123", display_name="alice")
    token_info = {
        "access_token": "acc",
        "refresh_token": "ref",
        "expires_at": 1700000000,
    }
    persist_token(db, "abc123", token_info)
    saved = get_user_token(db, "abc123")
    assert saved["access_token"] == "acc"
    assert saved["refresh_token"] == "ref"
