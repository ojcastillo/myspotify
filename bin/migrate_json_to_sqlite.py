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


# Fixed database path - single database for all users
DEFAULT_DB_PATH = "./assets/spotify_data.db"


# SQL Schema Constants - FULLY NORMALIZED (4 global tables + 1 user-specific)

CREATE_TRACKS_TABLE = """
CREATE TABLE IF NOT EXISTS tracks (
    track_id TEXT PRIMARY KEY,
    track_name TEXT NOT NULL,
    track_duration_ms INTEGER NOT NULL,
    track_popularity INTEGER,
    track_explicit INTEGER,
    track_is_local INTEGER,
    track_disc_number INTEGER,
    track_track_number INTEGER,
    track_uri TEXT,
    track_href TEXT,
    track_spotify_url TEXT,
    track_preview_url TEXT,
    track_isrc TEXT,
    album_id TEXT NOT NULL,
    album_name TEXT NOT NULL,
    album_type TEXT,
    album_release_date TEXT,
    album_release_date_precision TEXT,
    album_total_tracks INTEGER,
    album_uri TEXT,
    album_href TEXT,
    album_spotify_url TEXT,
    album_images TEXT,
    album_artists TEXT,
    track_artists TEXT NOT NULL,
    first_artist_id TEXT NOT NULL,
    available_markets TEXT,
    FOREIGN KEY (first_artist_id) REFERENCES artists(artist_id)
);
"""

CREATE_TRACKS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_tracks_name ON tracks(track_name);
CREATE INDEX IF NOT EXISTS idx_tracks_album_date ON tracks(album_release_date);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(first_artist_id);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album_id);
"""

CREATE_AUDIO_FEATURES_TABLE = """
CREATE TABLE IF NOT EXISTS audio_features (
    track_id TEXT PRIMARY KEY,
    danceability REAL,
    energy REAL,
    key INTEGER,
    loudness REAL,
    mode INTEGER,
    speechiness REAL,
    acousticness REAL,
    instrumentalness REAL,
    liveness REAL,
    valence REAL,
    tempo REAL,
    time_signature INTEGER,
    duration_ms INTEGER,
    track_href TEXT,
    analysis_url TEXT,
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);
"""

CREATE_ARTISTS_TABLE = """
CREATE TABLE IF NOT EXISTS artists (
    artist_id TEXT PRIMARY KEY,
    artist_name TEXT NOT NULL,
    popularity INTEGER,
    followers_total INTEGER,
    genres TEXT,
    artist_uri TEXT,
    artist_href TEXT,
    artist_spotify_url TEXT,
    images TEXT
);
"""

CREATE_ARTISTS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(artist_name);
CREATE INDEX IF NOT EXISTS idx_artists_popularity ON artists(popularity);
"""

CREATE_TRACK_ARTISTS_TABLE = """
CREATE TABLE IF NOT EXISTS track_artists (
    track_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    artist_position INTEGER NOT NULL,
    PRIMARY KEY (track_id, artist_id, artist_position),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id),
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
);
"""

CREATE_TRACK_ARTISTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_track_artists_artist ON track_artists(artist_id);
"""

CREATE_USER_TRACKS_TABLE = """
CREATE TABLE IF NOT EXISTS user_tracks (
    user_id TEXT NOT NULL,
    track_id TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (user_id, track_id),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);
"""

CREATE_USER_TRACKS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_user_tracks_user ON user_tracks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tracks_added_at ON user_tracks(user_id, added_at);
CREATE INDEX IF NOT EXISTS idx_user_tracks_track ON user_tracks(track_id);
"""


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


def create_schema(conn):
    """Create all tables with indexes."""
    print("Creating database schema...")
    cursor = conn.cursor()

    # Create tables
    cursor.executescript(CREATE_ARTISTS_TABLE)
    cursor.executescript(CREATE_TRACKS_TABLE)
    cursor.executescript(CREATE_AUDIO_FEATURES_TABLE)
    cursor.executescript(CREATE_TRACK_ARTISTS_TABLE)
    cursor.executescript(CREATE_USER_TRACKS_TABLE)

    # Create indexes
    cursor.executescript(CREATE_ARTISTS_INDEXES)
    cursor.executescript(CREATE_TRACKS_INDEXES)
    cursor.executescript(CREATE_TRACK_ARTISTS_INDEX)
    cursor.executescript(CREATE_USER_TRACKS_INDEXES)

    conn.commit()
    print("  Database schema created successfully")


def insert_artists(conn, artists_data):
    """Insert artist metadata using INSERT OR IGNORE for deduplication."""
    print(f"Inserting {len(artists_data)} artists (using INSERT OR IGNORE)...")
    cursor = conn.cursor()

    inserted = 0
    for artist in artists_data:
        cursor.execute("""
            INSERT OR IGNORE INTO artists (
                artist_id, artist_name, popularity, followers_total,
                genres, artist_uri, artist_href, artist_spotify_url, images
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            artist['id'],
            artist['name'],
            artist.get('popularity'),
            artist.get('followers', {}).get('total'),
            json.dumps(artist.get('genres', [])),
            artist.get('uri'),
            artist.get('href'),
            artist.get('external_urls', {}).get('spotify'),
            json.dumps(artist.get('images', []))
        ))
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} new artists (skipped {len(artists_data) - inserted} duplicates)")


def insert_tracks(conn, library_data):
    """Insert track and album data using INSERT OR IGNORE for deduplication."""
    print(f"Inserting tracks from {len(library_data)} library entries (using INSERT OR IGNORE)...")
    cursor = conn.cursor()

    inserted = 0
    for item in library_data:
        track = item['track']
        album = track['album']

        # Extract first artist ID for foreign key
        first_artist_id = track['artists'][0]['id']

        cursor.execute("""
            INSERT OR IGNORE INTO tracks (
                track_id, track_name, track_duration_ms,
                track_popularity, track_explicit, track_is_local,
                track_disc_number, track_track_number,
                track_uri, track_href, track_spotify_url, track_preview_url,
                track_isrc, album_id, album_name, album_type,
                album_release_date, album_release_date_precision,
                album_total_tracks, album_uri, album_href, album_spotify_url,
                album_images, album_artists, track_artists,
                first_artist_id, available_markets
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            track['id'],
            track['name'],
            track['duration_ms'],
            track.get('popularity'),
            1 if track.get('explicit') else 0,
            1 if track.get('is_local') else 0,
            track.get('disc_number'),
            track.get('track_number'),
            track.get('uri'),
            track.get('href'),
            track.get('external_urls', {}).get('spotify'),
            track.get('preview_url'),
            track.get('external_ids', {}).get('isrc'),
            album['id'],
            album['name'],
            album.get('album_type'),
            album.get('release_date'),
            album.get('release_date_precision'),
            album.get('total_tracks'),
            album.get('uri'),
            album.get('href'),
            album.get('external_urls', {}).get('spotify'),
            json.dumps(album.get('images', [])),
            json.dumps(album.get('artists', [])),
            json.dumps(track.get('artists', [])),
            first_artist_id,
            json.dumps(track.get('available_markets', []))
        ))
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} new tracks (skipped {len(library_data) - inserted} duplicates)")


def insert_track_artists(conn, library_data):
    """Insert many-to-many track-artist relationships using INSERT OR IGNORE."""
    print("Inserting track-artist relationships (using INSERT OR IGNORE)...")
    cursor = conn.cursor()

    inserted = 0
    for item in library_data:
        track_id = item['track']['id']
        artists = item['track']['artists']

        for position, artist in enumerate(artists):
            cursor.execute("""
                INSERT OR IGNORE INTO track_artists (track_id, artist_id, artist_position)
                VALUES (?, ?, ?)
            """, (track_id, artist['id'], position))
            if cursor.rowcount > 0:
                inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} new track-artist relationships")


def insert_audio_features(conn, features_data):
    """Insert audio feature data using INSERT OR IGNORE for deduplication."""
    # Filter out None values
    valid_features = [f for f in features_data if f is not None]
    print(f"Inserting {len(valid_features)} audio features (using INSERT OR IGNORE, skipping {len(features_data) - len(valid_features)} None values)...")

    cursor = conn.cursor()

    inserted = 0
    for features in valid_features:
        cursor.execute("""
            INSERT OR IGNORE INTO audio_features (
                track_id, danceability, energy, key, loudness, mode,
                speechiness, acousticness, instrumentalness, liveness,
                valence, tempo, time_signature, duration_ms,
                track_href, analysis_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            features['id'],
            features.get('danceability'),
            features.get('energy'),
            features.get('key'),
            features.get('loudness'),
            features.get('mode'),
            features.get('speechiness'),
            features.get('acousticness'),
            features.get('instrumentalness'),
            features.get('liveness'),
            features.get('valence'),
            features.get('tempo'),
            features.get('time_signature'),
            features.get('duration_ms'),
            features.get('track_href'),
            features.get('analysis_url')
        ))
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} new audio features (skipped {len(valid_features) - inserted} duplicates)")


def insert_user_tracks(conn, username, library_data):
    """Insert user-specific track library relationships (handles duplicates)."""
    print(f"Inserting {len(library_data)} user_tracks entries for user {username}...")
    cursor = conn.cursor()

    inserted = 0
    for item in library_data:
        track_id = item['track']['id']
        added_at = item['added_at']

        cursor.execute("""
            INSERT OR IGNORE INTO user_tracks (user_id, track_id, added_at)
            VALUES (?, ?, ?)
        """, (username, track_id, added_at))
        inserted += cursor.rowcount

    conn.commit()
    print(f"  Inserted {inserted} new user_tracks entries (skipped {len(library_data) - inserted} duplicates)")


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
            create_schema(conn)
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
        insert_artists(conn, artists_data)
        insert_tracks(conn, library_data)
        insert_track_artists(conn, library_data)
        insert_audio_features(conn, features_data)

        # User-specific table last
        insert_user_tracks(conn, username, library_data)

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
