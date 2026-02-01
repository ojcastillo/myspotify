#!/usr/bin/env python3
"""
Download Spotify metadata of songs in the user's library directly to SQLite database.

This script downloads liked songs, artist metadata, and saves them to a SQLite database.
Audio features download is currently disabled due to Spotify API deprecation (Nov 2024).

The first time you run this script, it will download ALL of your liked songs metadata.
For a ~10K library, this takes ~10mins. Subsequent runs will only download new liked songs
unless you pass the "--regenerate" flag.

Data is saved to a SQLite database (default: ./assets/spotify_data.db).

Usage:
    download_library.py <client_username> <client_id> <client_secret> <redirect_uri> [-h] [--regenerate] [--db-path PATH]

Options:
    -h --help           Show this help information
    --regenerate        Download ALL tracks liked by the user (full refresh)
    --db-path PATH      SQLite database path [default: ./assets/spotify_data.db]
"""
import json
import os
import sqlite3
import sys
from random import randint
from time import sleep

import spotipy
from docopt import docopt
from spotipy.oauth2 import SpotifyOAuth

# Add src directory to path to import shared database helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.common.db_helpers import (
    create_schema,
    insert_artists,
    insert_tracks,
    insert_track_artists,
    insert_audio_features,
    insert_user_tracks
)


# Max tracks to download if set to something greater than 0, otherwise downloads everything.
# Intended just for targeted small tests.
MAX_TRACKS = 0

# Fixed database path - single database for all users
DEFAULT_DB_PATH = "./assets/spotify_data.db"


# ============================================================================
# Database Helper Functions
# ============================================================================

def get_or_create_connection(db_path):
    """
    Connect to SQLite database and ensure schema exists.

    Args:
        db_path: Path to SQLite database file

    Returns:
        SQLite connection object
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Check if schema exists, create if not
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    if not existing_tables:
        print(f"Creating new database at: {db_path}")
        print("Creating database schema...")
        create_schema(conn)
        print("  Database schema created successfully")
    else:
        print(f"Using existing database at: {db_path}")

    return conn


def get_most_recent_track_from_db(conn, username):
    """
    Query user_tracks table for most recent track (for incremental downloads).

    Args:
        conn: SQLite database connection
        username: User ID

    Returns:
        Track object compatible with existing comparison logic, or None if no tracks exist
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ut.track_id, ut.added_at, t.track_artists
        FROM user_tracks ut
        JOIN tracks t ON ut.track_id = t.track_id
        WHERE ut.user_id = ?
        ORDER BY ut.added_at DESC
        LIMIT 1
    """, (username,))

    result = cursor.fetchone()
    if result:
        track_id, added_at, track_artists_json = result
        # Reconstruct track object for compatibility with get_user_library
        return {
            "track": {
                "id": track_id,
                "artists": json.loads(track_artists_json)
            },
            "added_at": added_at
        }
    return None


def get_existing_artist_ids(conn):
    """
    Query database for all existing artist IDs (for incremental downloads).

    Args:
        conn: SQLite database connection

    Returns:
        Set of artist IDs already in database
    """
    cursor = conn.cursor()
    cursor.execute("SELECT artist_id FROM artists")
    return {row[0] for row in cursor.fetchall()}


# ============================================================================
# Spotify API Download Functions (unchanged)
# ============================================================================

def get_user_library(sp, most_recent_track=None):
    print("Starting to download metadata of songs in library")
    limit = 50
    current_offset = 0
    track_list = []
    while True:
        print("Current track offset: ", current_offset)
        result = sp.current_user_saved_tracks(limit, current_offset)
        if not result["items"]:
            print("No tracks in response. Stopping download loop!")
            break

        if most_recent_track:
            stopped_early = False
            for track in result["items"]:
                if track["track"]["id"] == most_recent_track["track"]["id"]:
                    stopped_early = True
                    break
                track_list.append(track)
            if stopped_early:
                print("No need to download more songs as the rest was downloaded before. Stopping download loop!")
                break
        else:
            track_list.extend(result["items"])

        if not result["next"]:
            print("No more songs in library. Stopping download loop!")
            break

        if (MAX_TRACKS > 0) and (MAX_TRACKS <= len(track_list)):
            print(f"More than {MAX_TRACKS} songs already downloaded. Stopping download loop!")
            track_list = track_list[:MAX_TRACKS]
            break

        sleep(randint(1, 2))
        current_offset += limit
    return track_list


def get_audio_features(sp, tracks):
    print(f"Starting to download audio features of {len(tracks)} tracks")
    all_ids = [track["track"]["id"] for track in tracks]
    audio_features = []
    offset = 100
    for idx in range(0, len(all_ids), offset):
        print("Current audio feature offset: ", idx)
        audio_features.extend(sp.audio_features(all_ids[idx : (idx + offset)]))
        sleep(randint(1, 2))
    return audio_features


def get_artist_id_set_from_tracks(tracks):
    artists_per_track = [track["track"]["artists"] for track in tracks]
    return set([artist["id"] for artists in artists_per_track for artist in artists])


def get_artists_metadata(sp, artist_id_set):
    artist_id_list = list(artist_id_set)

    print(f"Starting to download artist metadata of {len(artist_id_list)} artists")
    metadata = []
    offset = 50
    for idx in range(0, len(artist_id_list), offset):
        print("Current artist metadata download offset: ", idx)
        metadata.extend(sp.artists(artist_id_list[idx : (idx + offset)])["artists"])
        sleep(randint(1, 2))
    return metadata


def main(args):
    """Entry point - downloads Spotify data and saves to SQLite database."""
    print(f"="*60)
    print("MySpotify Library Downloader - Direct to SQLite")
    print(f"="*60)
    print(f"Starting script with the following arguments:")
    print(args)

    # Get database path from args or use default
    db_path = args.get("--db-path") or DEFAULT_DB_PATH
    username = args["<client_username>"]

    print("\nAuthenticating with Spotify (if this is the first time)")
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope="user-library-read",
            username=username,
            redirect_uri=args["<redirect_uri>"],
            client_id=args["<client_id>"],
            client_secret=args["<client_secret>"],
        )
    )

    # Connect to database
    conn = None
    try:
        conn = get_or_create_connection(db_path)

        if args["--regenerate"]:
            print("\n" + "="*60)
            print("MODE: Full regeneration (download ALL tracks)")
            print("="*60)

            track_list = get_user_library(sp)

            print("\nSkipping audio features download (Spotify API deprecated)")
            audio_features = []  # Will be empty in database

            print("\nDownloading metadata of all artists linked to tracks...")
            artists_metadata = get_artists_metadata(sp, get_artist_id_set_from_tracks(track_list))

        else:
            print("\n" + "="*60)
            print("MODE: Incremental download (only new tracks)")
            print("="*60)

            # Query database for most recent track instead of loading JSON
            print("\nChecking database for most recent track...")
            most_recent_track = get_most_recent_track_from_db(conn, username)

            if most_recent_track:
                print(f"  Found most recent track: {most_recent_track['track']['id']} (added {most_recent_track['added_at']})")
            else:
                print("  No existing tracks found. Downloading all tracks...")

            new_tracks = get_user_library(sp, most_recent_track)
            if not new_tracks:
                print("\n✓ No new liked tracks found. Database is up to date!")
                return

            print(f"\nFound {len(new_tracks)} new liked tracks")
            track_list = new_tracks
            audio_features = []  # No audio features (API deprecated)

            # Query existing artists from database
            print("\nChecking database for existing artists...")
            existing_artist_ids = get_existing_artist_ids(conn)
            print(f"  Found {len(existing_artist_ids)} existing artists in database")

            new_artist_ids = get_artist_id_set_from_tracks(new_tracks)
            new_artists_only = new_artist_ids - existing_artist_ids

            if new_artists_only:
                print(f"\nDownloading metadata for {len(new_artists_only)} new artists")
                artists_metadata = get_artists_metadata(sp, new_artists_only)
            else:
                print("\nNo new artists found. Skipping artist metadata download.")
                artists_metadata = []

        # Insert into database (within transaction)
        print("\n" + "="*60)
        print("Saving data to database...")
        print("="*60)

        conn.execute("BEGIN TRANSACTION")

        print(f"\nInserting {len(artists_metadata)} artists (using INSERT OR IGNORE)...")
        inserted_artists = insert_artists(conn, artists_metadata)
        print(f"  Inserted {inserted_artists} new artists (skipped {len(artists_metadata) - inserted_artists} duplicates)")

        print(f"\nInserting tracks from {len(track_list)} library entries (using INSERT OR IGNORE)...")
        inserted_tracks = insert_tracks(conn, track_list)
        print(f"  Inserted {inserted_tracks} new tracks (skipped {len(track_list) - inserted_tracks} duplicates)")

        print("\nInserting track-artist relationships (using INSERT OR IGNORE)...")
        inserted_track_artists = insert_track_artists(conn, track_list)
        print(f"  Inserted {inserted_track_artists} new track-artist relationships")

        if audio_features:
            valid_features = [f for f in audio_features if f is not None]
            print(f"\nInserting {len(valid_features)} audio features (using INSERT OR IGNORE)...")
            inserted_features = insert_audio_features(conn, audio_features)
            print(f"  Inserted {inserted_features} new audio features")
        else:
            print("\nSkipping audio features (none available)")

        print(f"\nInserting {len(track_list)} user_tracks entries for user {username}...")
        inserted_user_tracks = insert_user_tracks(conn, username, track_list)
        print(f"  Inserted {inserted_user_tracks} new user_tracks entries (skipped {len(track_list) - inserted_user_tracks} duplicates)")

        conn.commit()

        print("\n" + "="*60)
        print(f"✓✓✓ Download completed successfully! ✓✓✓")
        print("="*60)
        print(f"✓ Saved {len(track_list)} tracks to database: {db_path}")
        print(f"✓ User: {username}")
        print("="*60)

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n✗ ERROR: Download failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main(docopt(__doc__, version="MySpotify 1.0"))
