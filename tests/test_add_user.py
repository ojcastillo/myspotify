import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bin.add_user import add_user
from common.db_helpers import get_allowed_user


def test_add_user_inserts_into_db(db):
    add_user(db, display_name="orlando", spotify_user_id="1266569549")
    row = get_allowed_user(db, "1266569549")
    assert row is not None
    assert row["display_name"] == "orlando"
    assert row["spotify_user_id"] == "1266569549"


def test_add_user_overwrites_existing(db):
    add_user(db, display_name="old_name", spotify_user_id="1266569549")
    add_user(db, display_name="new_name", spotify_user_id="1266569549")
    row = get_allowed_user(db, "1266569549")
    assert row["display_name"] == "new_name"
