# Architecture & Database Reference

## Data Flow

```
Spotify API
    ↓
bin/download_library.py  (incremental by default; --regenerate for full refresh)
    ↓
SQLite Database (./assets/spotify_data.db)
    ├── Global tables: tracks, artists, audio_features, track_artists
    └── User-specific: user_tracks (user_id, track_id, added_at)
    ↓
src/common/load_data.py → load_data(user_ids)
    ↓
Pandas DataFrame (merged, deduplicated across users)
    ↓
Flask/Dash UI  →  src/pages/home.py  |  src/pages/library.py
```

## Database Schema (5 tables)

**Global tables** — shared across all users, no `user_id` column:

- **tracks**: track + album metadata (`track_id` PK, denormalized album fields, JSON columns for images/artists)
- **audio_features**: audio analysis metrics (`track_id` FK → tracks; danceability, energy, tempo, etc.)
- **artists**: artist metadata (`artist_id` PK, genres stored as JSON)
- **track_artists**: many-to-many junction (`track_id`, `artist_id`, `artist_position`)

**User-specific table**:

- **user_tracks**: links users to their library (`user_id`, `track_id`, `added_at`)

All global tables use `INSERT OR IGNORE` — when multiple users share a track/artist, only one copy is stored.

## src/common/db_helpers.py — Shared DB Module

Used by both `download_library.py` and `migrate_json_to_sqlite.py`.

- `create_schema(conn)` — creates all 5 tables with indexes
- `insert_artists(conn, artists_data)`
- `insert_tracks(conn, library_data)`
- `insert_track_artists(conn, library_data)`
- `insert_audio_features(conn, features_data)` — handles `None` values (API can return null)
- `insert_user_tracks(conn, username, library_data)`
- `get_available_users()` — queries distinct users with display names
- `USER_DISPLAY_NAMES` — maps user IDs to friendly names

## Authentication Flow (src/app.py)

1. `/` redirects directly to `/dash` — no auth required to browse
2. `/auth` handles Spotify OAuth (sign-in, callback, token validation)
3. Successful `/auth` initializes `SpotifyClientSingleton`, redirects to `/dash`
4. Playlist creation checks for auth and shows a warning with link to `/auth` if missing

## Multi-User Design

Single DB file handles all users. To add a user:
```bash
./bin/download_library.py <new_username> <client_id> <client_secret> <redirect_uri>
# OR for legacy JSON files:
python bin/migrate_json_to_sqlite.py <new_username> --verify
```

Space efficiency: 28% savings observed with two users sharing tracks/artists.

## Migration History

- **Phase 1**: Created `bin/migrate_json_to_sqlite.py`; implemented normalized 5-table schema
- **Phase 2**: Added second user; verified deduplication and data isolation; fixed LEFT JOIN bug in JSON reader
- **Phase 3**: Extracted `src/common/db_helpers.py`; updated download script to write directly to SQLite; eliminated ~300 lines of duplication between scripts

Legacy JSON workflow (`Spotify API → JSON files → migrate script → SQLite`) is still supported as a fallback but is no longer the active path.
