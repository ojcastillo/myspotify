#!/usr/bin/env python3
"""
Download Spotify library for a user and save to SQLite.

Credentials are read from a .env file (SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET,
SPOTIPY_REDIRECT_URI). The user must first be added via bin/add_user.py and must
have a stored token (obtained by logging in via /auth).

Usage:
    download_library.py <spotify_user_id> [-h] [--regenerate] [--db-path PATH]

Options:
    -h --help           Show this help information
    --regenerate        Download ALL tracks (full refresh, not just new ones)
    --db-path PATH      SQLite database path [default: ./assets/spotify_data.db]

Example:
    python bin/download_library.py 1266569549
"""
import os
import sys

from docopt import docopt
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.common.sync import run_sync


def main(args):
    spotify_user_id = args["<spotify_user_id>"]
    db_path = args.get("--db-path") or "./assets/spotify_data.db"
    regenerate = bool(args.get("--regenerate"))

    print(f"Syncing library for user: {spotify_user_id}")
    run_sync(spotify_user_id=spotify_user_id, db_path=db_path, regenerate=regenerate)
    print("Done.")


if __name__ == "__main__":
    main(docopt(__doc__))
