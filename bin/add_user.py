#!/usr/bin/env python3
"""
Add a user to the MySpotify allowed_users table.

Usage:
    add_user.py <display_name> <spotify_user_id> [--db-path PATH]

Options:
    -h --help       Show this help
    --db-path PATH  SQLite database path [default: ./assets/spotify_data.db]

Example:
    python bin/add_user.py orlando 1266569549
"""
import os
import sqlite3
import sys

from docopt import docopt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.common.db_helpers import add_allowed_user, create_schema

DEFAULT_DB_PATH = "./assets/spotify_data.db"


def add_user(conn, display_name, spotify_user_id):
    """Insert or replace a user in allowed_users. Exported for testing."""
    add_allowed_user(conn, spotify_user_id=spotify_user_id, display_name=display_name)
    print(f"Added user: {display_name} ({spotify_user_id})")


def main(args):
    db_path = args.get("--db-path") or DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)  # ensures tables exist (idempotent)
    try:
        add_user(conn, display_name=args["<display_name>"], spotify_user_id=args["<spotify_user_id>"])
    finally:
        conn.close()


if __name__ == "__main__":
    main(docopt(__doc__))
