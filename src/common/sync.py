"""
Core library sync logic for MySpotify.

Called by both bin/download_library.py (CLI) and the settings page (in-app sync).
"""
import json
import os
import sqlite3
from random import randint
from time import sleep

import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth

from common.db_helpers import (
    create_schema,
    insert_artists,
    insert_tracks,
    insert_track_artists,
    insert_user_tracks,
    get_user_token,
)


def _build_spotify_client(token_info):
    """Build a Spotify client from stored token info dict, with token refresh support."""
    cache_handler = MemoryCacheHandler(token_info=token_info)
    auth_manager = SpotifyOAuth(scope="user-library-read", cache_handler=cache_handler, open_browser=False)
    return spotipy.Spotify(auth_manager=auth_manager)


def _get_most_recent_track(conn, user_id):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ut.track_id, ut.added_at, t.track_artists
        FROM user_tracks ut
        JOIN tracks t ON ut.track_id = t.track_id
        WHERE ut.user_id = ?
        ORDER BY ut.added_at DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    if row:
        return {"track": {"id": row[0], "artists": json.loads(row[2])}, "added_at": row[1]}
    return None


def _get_existing_artist_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT artist_id FROM artists")
    return {row[0] for row in cursor.fetchall()}


def _fetch_library(sp, most_recent_track=None, max_tracks=0):
    limit = 50
    offset = 0
    tracks = []
    while True:
        result = sp.current_user_saved_tracks(limit, offset)
        if not result["items"]:
            break
        if most_recent_track:
            stopped = False
            for item in result["items"]:
                if item["track"]["id"] == most_recent_track["track"]["id"]:
                    stopped = True
                    break
                tracks.append(item)
            if stopped:
                break
        else:
            tracks.extend(result["items"])
        if not result["next"]:
            break
        if max_tracks > 0 and len(tracks) >= max_tracks:
            tracks = tracks[:max_tracks]
            break
        sleep(randint(1, 2))
        offset += limit
    return tracks


def _fetch_artists(sp, artist_ids):
    ids = list(artist_ids)
    metadata = []
    for i in range(0, len(ids), 50):
        metadata.extend(sp.artists(ids[i : i + 50])["artists"])
        sleep(randint(1, 2))
    return metadata


def run_sync(spotify_user_id, db_path="./assets/spotify_data.db", regenerate=False):
    """
    Sync the Spotify library for a given user using their stored token.

    Args:
        spotify_user_id: Spotify user ID (must exist in user_tokens)
        db_path: Path to SQLite DB
        regenerate: If True, re-download all tracks (full refresh)

    Raises:
        ValueError: If no token is stored for the user
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)

    try:
        token = get_user_token(conn, spotify_user_id)
        if token is None:
            raise ValueError(f"No stored token for user {spotify_user_id}")

        token_info = {
            "access_token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "expires_at": 0,  # force refresh on next call
            "token_type": "Bearer",
            "scope": "user-library-read",
        }
        sp = _build_spotify_client(token_info)

        if regenerate:
            track_list = _fetch_library(sp)
            artist_ids = {a["id"] for item in track_list for a in item["track"]["artists"]}
            artists = _fetch_artists(sp, artist_ids)
        else:
            most_recent = _get_most_recent_track(conn, spotify_user_id)
            track_list = _fetch_library(sp, most_recent)
            if not track_list:
                return  # already up to date
            new_artist_ids = {a["id"] for item in track_list for a in item["track"]["artists"]}
            existing_ids = _get_existing_artist_ids(conn)
            artists = _fetch_artists(sp, new_artist_ids - existing_ids)

        conn.execute("BEGIN TRANSACTION")
        insert_artists(conn, artists)
        insert_tracks(conn, track_list)
        insert_track_artists(conn, track_list)
        insert_user_tracks(conn, spotify_user_id, track_list)
        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
