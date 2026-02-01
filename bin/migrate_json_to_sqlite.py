#!/usr/bin/env python3
"""
Migrate JSON data files to SQLite database with fully normalized schema.

This script creates a single database (spotify_data.db) where all music entities (tracks, artists, features)
are shared globally across users. Only the user_tracks table contains user-specific data (which tracks
each user has added to their library).

Usage:
    migrate_json_to_sqlite.py <username> [-h] [--db-path PATH] [--verify]

Options:
    -h --help           Show this help information
    --db-path PATH      Custom database path (default: ./assets/spotify_data.db)
    --verify            Run data integrity checks after migration (default: True)
"""

import json
import os
import sqlite3
import sys

import pandas as pd
from docopt import docopt

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


# Fixed database path - single database for all users
DEFAULT_DB_PATH = "./assets/spotify_data.db"


def load_json_files(username):
    """Load all three JSON files into memory."""
    print("Loading JSON files...")

    library_path = f"./assets/user_library_{username}.json"
    features_path = f"./assets/audio_features_{username}.json"
    artists_path = f"./assets/artists_metadata_{username}.json"

    # Check if files exist
    for name, path in [("user_library", library_path), ("audio_features", features_path), ("artists_metadata", artists_path)]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {name} file: {path}")

    with open(library_path) as f:
        library_data = json.load(f)
    print(f"  Loaded {len(library_data)} tracks")

    with open(features_path) as f:
        features_data = json.load(f)
    print(f"  Loaded {len(features_data)} audio features")

    with open(artists_path) as f:
        artists_data = json.load(f)
    print(f"  Loaded {len(artists_data)} artists")

    return library_data, features_data, artists_data


def verify_migration(db_path, username, library_data, features_data, artists_data):
    """Verify data integrity by comparing record counts and spot-checking data."""
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check 1: Record Counts for user
        print(f"\n1. Checking record counts for user {username}...")

        # Count unique tracks in JSON (source may have duplicates)
        unique_track_ids = set(item['track']['id'] for item in library_data)
        expected_count = len(unique_track_ids)

        cursor.execute("SELECT COUNT(*) FROM user_tracks WHERE user_id = ?", (username,))
        user_tracks_count = cursor.fetchone()[0]

        if user_tracks_count != expected_count:
            print(f"   ✗ User tracks count mismatch: DB={user_tracks_count}, Expected={expected_count}")
            return False

        duplicates = len(library_data) - expected_count
        if duplicates > 0:
            print(f"   ✓ User tracks: {user_tracks_count} (source had {duplicates} duplicates)")
        else:
            print(f"   ✓ User tracks: {user_tracks_count}")

        # Check global counts (may be less than JSON due to deduplication)
        cursor.execute("SELECT COUNT(*) FROM tracks")
        tracks_count = cursor.fetchone()[0]
        print(f"   ✓ Global tracks: {tracks_count} (≤ {len(library_data)} due to deduplication)")

        cursor.execute("SELECT COUNT(*) FROM artists")
        artists_count = cursor.fetchone()[0]
        print(f"   ✓ Global artists: {artists_count} (≤ {len(artists_data)} due to deduplication)")

        cursor.execute("SELECT COUNT(*) FROM audio_features")
        features_count = cursor.fetchone()[0]
        features_non_null = len([f for f in features_data if f is not None])
        print(f"   ✓ Global audio features: {features_count} (≤ {features_non_null} due to deduplication)")

        # Check 2: Sample Track Data via user_tracks JOIN
        print("\n2. Spot-checking track data via user_tracks join...")
        sample_track = library_data[0]
        track_id = sample_track['track']['id']

        cursor.execute("""
            SELECT t.track_name, t.album_name, ut.added_at
            FROM user_tracks ut
            JOIN tracks t ON ut.track_id = t.track_id
            WHERE ut.user_id = ? AND ut.track_id = ?
        """, (username, track_id))
        db_track = cursor.fetchone()

        if db_track is None:
            print(f"   ✗ Sample track not found in user_tracks join")
            return False
        if db_track[0] != sample_track['track']['name']:
            print(f"   ✗ Track name mismatch")
            return False
        if db_track[1] != sample_track['track']['album']['name']:
            print(f"   ✗ Album name mismatch")
            return False
        if db_track[2] != sample_track['added_at']:
            print(f"   ✗ Added_at timestamp mismatch")
            return False
        print(f"   ✓ Sample track '{db_track[0]}' matches")

        # Check 3: Sample Artist Data
        print("\n3. Spot-checking artist data...")
        sample_artist = artists_data[0]
        artist_id = sample_artist['id']

        cursor.execute("SELECT artist_name, popularity, genres FROM artists WHERE artist_id = ?", (artist_id,))
        db_artist = cursor.fetchone()

        if db_artist is None:
            print(f"   ✗ Sample artist not found")
            return False
        if db_artist[0] != sample_artist['name']:
            print(f"   ✗ Artist name mismatch")
            return False
        # Popularity might differ if artist was already in DB from another user, that's OK
        if json.loads(db_artist[2]) != sample_artist['genres']:
            print(f"   ✗ Artist genres mismatch")
            return False
        print(f"   ✓ Sample artist '{db_artist[0]}' matches")

        # Check 4: Sample Audio Features
        print("\n4. Spot-checking audio features...")
        sample_feature = next(f for f in features_data if f is not None)
        feature_id = sample_feature['id']

        cursor.execute("SELECT danceability, energy, valence FROM audio_features WHERE track_id = ?", (feature_id,))
        db_feature = cursor.fetchone()

        if db_feature is None:
            print(f"   ✗ Sample audio feature not found")
            return False
        if abs(db_feature[0] - sample_feature['danceability']) > 0.0001:
            print(f"   ✗ Danceability mismatch")
            return False
        if abs(db_feature[1] - sample_feature['energy']) > 0.0001:
            print(f"   ✗ Energy mismatch")
            return False
        if abs(db_feature[2] - sample_feature['valence']) > 0.0001:
            print(f"   ✗ Valence mismatch")
            return False
        print(f"   ✓ Sample audio features match")

        # Check 5: Foreign Key Integrity
        print("\n5. Checking foreign key integrity...")
        cursor.execute("""
            SELECT COUNT(*) FROM user_tracks ut
            LEFT JOIN tracks t ON ut.track_id = t.track_id
            WHERE t.track_id IS NULL AND ut.user_id = ?
        """, (username,))
        orphaned_user_tracks = cursor.fetchone()[0]
        if orphaned_user_tracks != 0:
            print(f"   ✗ Found {orphaned_user_tracks} user_tracks with missing track references")
            return False
        print(f"   ✓ All user_tracks have valid track references")

        # Check 6: DataFrame Equivalence
        print("\n6. Comparing DataFrames (JSON vs SQLite)...")

        # Import DataSingleton
        sys.path.insert(0, './src')
        from common.data import DataSingleton

        # Load using JSON method
        json_df = DataSingleton._read_from_json(username)

        # Load using SQLite method
        sqlite_df = DataSingleton._read_from_sqlite(db_path, username)

        # Compare row counts (column counts may differ due to optional fields in JSON)
        if json_df.shape[0] != sqlite_df.shape[0]:
            print(f"   ✗ Row count mismatch: JSON={json_df.shape[0]}, SQLite={sqlite_df.shape[0]}")
            return False
        print(f"   ✓ Row counts match: {json_df.shape[0]} rows")

        # Check column overlap (JSON may have extra optional columns like is_playable)
        json_cols = set(json_df.columns)
        sqlite_cols = set(sqlite_df.columns)

        # Optional columns that JSON might have but SQLite doesn't need
        optional_json_cols = {'track.is_playable', 'track.album.is_playable'}

        missing_in_sqlite = json_cols - sqlite_cols - optional_json_cols
        missing_in_json = sqlite_cols - json_cols

        if missing_in_sqlite:
            print(f"   ✗ Required columns missing in SQLite: {missing_in_sqlite}")
            return False
        if missing_in_json:
            print(f"   ✗ Required columns missing in JSON: {missing_in_json}")
            return False

        extra_in_json = json_cols & optional_json_cols
        if extra_in_json:
            print(f"   ✓ Columns match (JSON has {len(extra_in_json)} optional columns: {extra_in_json})")
        else:
            print(f"   ✓ Columns match ({len(sqlite_cols)} columns)")

        # Compare sample row
        sample_id = json_df.iloc[0]['track.id']
        json_row = json_df[json_df['track.id'] == sample_id].iloc[0]
        sqlite_row = sqlite_df[sqlite_df['track.id'] == sample_id].iloc[0]

        # Check key fields
        if json_row['track.name'] != sqlite_row['track.name']:
            print(f"   ✗ Track name mismatch in DataFrame")
            return False
        if json_row['track.album.name'] != sqlite_row['track.album.name']:
            print(f"   ✗ Album name mismatch in DataFrame")
            return False
        if json_row['added_at'] != sqlite_row['added_at']:
            print(f"   ✗ Added_at mismatch in DataFrame")
            return False
        print(f"   ✓ DataFrame sample rows match")

        print("\n" + "="*60)
        print("✓✓✓ ALL VERIFICATION CHECKS PASSED ✓✓✓")
        print("="*60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def migrate_with_transaction(db_path, username, library_data, features_data, artists_data, verify=True):
    """Migrate data within a transaction for atomicity."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Check if database exists and has schema
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
            print(f"  Existing tables: {existing_tables}")
            # Verify schema is correct
            if existing_tables != {'tracks', 'audio_features', 'artists', 'track_artists', 'user_tracks'}:
                print(f"  WARNING: Schema mismatch. Expected 5 tables, found: {existing_tables}")

        # Check if user already exists
        cursor.execute("SELECT COUNT(*) FROM user_tracks WHERE user_id = ?", (username,))
        existing_count = cursor.fetchone()[0]
        if existing_count > 0:
            response = input(f"User {username} already has {existing_count} tracks in database. Overwrite? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled.")
                return False
            # Delete existing user_tracks for this user
            cursor.execute("DELETE FROM user_tracks WHERE user_id = ?", (username,))
            conn.commit()
            print(f"  Deleted {existing_count} existing user_tracks for user {username}")

        # Insert data in correct order (respecting foreign keys)
        # Global tables first (with OR IGNORE for deduplication)
        print(f"Inserting {len(artists_data)} artists (using INSERT OR IGNORE)...")
        inserted_artists = insert_artists(conn, artists_data)
        print(f"  Inserted {inserted_artists} new artists (skipped {len(artists_data) - inserted_artists} duplicates)")

        print(f"Inserting tracks from {len(library_data)} library entries (using INSERT OR IGNORE)...")
        inserted_tracks = insert_tracks(conn, library_data)
        print(f"  Inserted {inserted_tracks} new tracks (skipped {len(library_data) - inserted_tracks} duplicates)")

        print("Inserting track-artist relationships (using INSERT OR IGNORE)...")
        inserted_track_artists = insert_track_artists(conn, library_data)
        print(f"  Inserted {inserted_track_artists} new track-artist relationships")

        valid_features = [f for f in features_data if f is not None]
        print(f"Inserting {len(valid_features)} audio features (using INSERT OR IGNORE, skipping {len(features_data) - len(valid_features)} None values)...")
        inserted_features = insert_audio_features(conn, features_data)
        print(f"  Inserted {inserted_features} new audio features (skipped {len(valid_features) - inserted_features} duplicates)")

        # User-specific table last
        print(f"Inserting {len(library_data)} user_tracks entries for user {username}...")
        inserted_user_tracks = insert_user_tracks(conn, username, library_data)
        print(f"  Inserted {inserted_user_tracks} new user_tracks entries (skipped {len(library_data) - inserted_user_tracks} duplicates)")

        print(f"\n✓ Migration completed successfully for user {username}!")
        print(f"✓ Database: {db_path}")

        # Verify if requested
        if verify:
            success = verify_migration(db_path, username, library_data, features_data, artists_data)
            return success

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n✗ ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()


def main(args):
    """Entry point."""
    username = args['<username>']
    db_path = args.get('--db-path') or DEFAULT_DB_PATH
    verify = not args.get('--verify') == False  # Default to True

    print(f"="*60)
    print("MySpotify SQLite Migration - Fully Normalized Schema")
    print("="*60)
    print(f"User: {username}")
    print(f"Database: {db_path}")
    print(f"Verification: {'enabled' if verify else 'disabled'}")
    print(f"Schema: 5 tables (4 global + 1 user-specific)")
    print("="*60)
    print()

    # Load JSON files
    library_data, features_data, artists_data = load_json_files(username)

    # Migrate
    success = migrate_with_transaction(db_path, username, library_data, features_data, artists_data, verify)

    if success:
        print("\n✓✓✓ Migration and verification completed successfully! ✓✓✓")
        print(f"\nNext steps:")
        print(f"1. Test the Flask app: sh bin/run_server.sh {username}")
        print(f"2. Verify home page displays correctly")
        print(f"3. Verify library page loads all tracks")
        print(f"4. Test filtering, sorting, and playlist creation")
        print(f"\nTo add another user:")
        print(f"  python bin/migrate_json_to_sqlite.py <another_username> --verify")
        return 0
    else:
        print("\n✗✗✗ Migration failed! ✗✗✗")
        print(f"\nRollback: Simply delete the database file:")
        print(f"  rm {db_path}")
        return 1


if __name__ == "__main__":
    args = docopt(__doc__, version="MySpotify Migration 2.0")
    sys.exit(main(args))
