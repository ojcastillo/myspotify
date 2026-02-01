"""
Shared database helper functions for SQLite operations.

This module contains schema definitions and insert functions used by both:
- bin/migrate_json_to_sqlite.py (migrates existing JSON files to SQLite)
- bin/download_library.py (downloads data directly to SQLite from Spotify API)

Database Design:
- 4 global tables (tracks, artists, audio_features, track_artists) - shared across all users
- 1 user-specific table (user_tracks) - tracks which user added which track

All inserts use INSERT OR IGNORE for automatic deduplication across users.
"""

import json
import sqlite3


# ============================================================================
# SQL Schema Constants - FULLY NORMALIZED (4 global tables + 1 user-specific)
# ============================================================================

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


# ============================================================================
# Schema Creation Functions
# ============================================================================

def create_schema(conn):
    """
    Create all tables with indexes.

    Creates 5 tables in order:
    1. artists (global, shared across users)
    2. tracks (global, shared across users)
    3. audio_features (global, shared across users)
    4. track_artists (global junction table)
    5. user_tracks (user-specific, only table with user_id)

    Args:
        conn: SQLite database connection

    Returns:
        None
    """
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


# ============================================================================
# Insert Functions (All use INSERT OR IGNORE for deduplication)
# ============================================================================

def insert_artists(conn, artists_data):
    """
    Insert artist metadata using INSERT OR IGNORE for deduplication.

    Args:
        conn: SQLite database connection
        artists_data: List of artist dictionaries from Spotify API

    Returns:
        Number of new artists inserted (excluding duplicates)
    """
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
    return inserted


def insert_tracks(conn, library_data):
    """
    Insert track and album data using INSERT OR IGNORE for deduplication.

    Args:
        conn: SQLite database connection
        library_data: List of track items from Spotify API (includes track.album, track.artists)

    Returns:
        Number of new tracks inserted (excluding duplicates)
    """
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
    return inserted


def insert_track_artists(conn, library_data):
    """
    Insert many-to-many track-artist relationships using INSERT OR IGNORE.

    Args:
        conn: SQLite database connection
        library_data: List of track items from Spotify API

    Returns:
        Number of new relationships inserted
    """
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
    return inserted


def insert_audio_features(conn, features_data):
    """
    Insert audio feature data using INSERT OR IGNORE for deduplication.

    Handles None values from deprecated Spotify Audio Features API.

    Args:
        conn: SQLite database connection
        features_data: List of audio feature dicts from Spotify API (may contain None)

    Returns:
        Number of new features inserted
    """
    # Filter out None values
    valid_features = [f for f in features_data if f is not None]

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
    return inserted


def insert_user_tracks(conn, username, library_data):
    """
    Insert user-specific track library relationships (handles duplicates).

    This is the ONLY user-specific table in the database. It tracks which
    tracks each user has added to their library and when.

    Args:
        conn: SQLite database connection
        username: User ID (from SPOTIPY_CLIENT_USERNAME)
        library_data: List of track items from Spotify API

    Returns:
        Number of new user_tracks entries inserted
    """
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
    return inserted
