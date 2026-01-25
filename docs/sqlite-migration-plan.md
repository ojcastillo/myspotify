# Migration Plan: JSON to SQLite for MySpotify

## 📋 Implementation Checklist

Use this checklist to track progress. If the session is interrupted, resume from the unchecked items.

### Part 1: Migration Script (`bin/migrate_json_to_sqlite.py`)
- [ ] Create script file with docstring and CLI interface (docopt)
- [ ] Implement `load_json_files(username)` - load 3 JSON files
- [ ] Define SQL schema constants:
  - [ ] CREATE TABLE tracks (with all columns + indexes)
  - [ ] CREATE TABLE audio_features
  - [ ] CREATE TABLE artists
  - [ ] CREATE TABLE track_artists
- [ ] Implement `create_schema(conn)` - execute CREATE TABLE statements
- [ ] Implement `insert_artists(conn, artists_data)` - insert artist records
- [ ] Implement `insert_tracks(conn, library_data)` - insert track/album records
- [ ] Implement `insert_track_artists(conn, library_data)` - insert junction records
- [ ] Implement `insert_audio_features(conn, features_data)` - insert features (handle None)
- [ ] Implement `verify_migration(db_path, ...)` with 6 checks:
  - [ ] Check 1: Record counts
  - [ ] Check 2: Spot-check track data
  - [ ] Check 3: Spot-check artist data
  - [ ] Check 4: Spot-check audio features
  - [ ] Check 5: Foreign key integrity
  - [ ] Check 6: DataFrame equivalence (JSON vs SQLite)
- [ ] Implement `main(username, db_path, verify)` - orchestrate with transaction
- [ ] Add error handling (try/except with rollback)
- [ ] Test migration script on actual data

### Part 2: DataSingleton Update (`src/common/data.py`)
- [ ] Rename `read_data()` → `_read_from_json()` (keep as fallback)
- [ ] Implement `_read_from_sqlite(db_path)`:
  - [ ] Connect to SQLite database
  - [ ] Query tracks table with column aliases
  - [ ] Query audio_features table with column aliases
  - [ ] Query artists table with column aliases
  - [ ] Parse JSON columns back to Python objects
  - [ ] Merge DataFrames (tracks + features + artists)
  - [ ] Compute 10 derived columns (same as current logic)
- [ ] Implement new `read_data(username)` dispatcher:
  - [ ] Check if DB file exists
  - [ ] If yes: call `_read_from_sqlite()`
  - [ ] If no: call `_read_from_json()`
- [ ] Add `import sqlite3` to imports

### Part 3: Testing & Verification
- [ ] Run migration script: `python bin/migrate_json_to_sqlite.py <username> --verify`
- [ ] Verify automated checks pass
- [ ] Manual browser testing:
  - [ ] Start Flask app: `sh bin/run_server.sh <username>`
  - [ ] Test home page (charts, counts)
  - [ ] Test library page (table loads)
  - [ ] Test filtering (3+ different filters)
  - [ ] Test sorting (3+ different columns)
  - [ ] Test row selection
  - [ ] Test playlist creation
- [ ] Check for errors in Flask logs
- [ ] Check for errors in browser console
- [ ] Compare baseline vs SQLite (counts, behavior)

### Part 4: Documentation & Cleanup
- [ ] Update CLAUDE.md with migration instructions
- [ ] Document rollback procedure
- [ ] Test rollback (delete DB, verify fallback to JSON)
- [ ] Optional: Create backup of JSON files

---

## Overview

Migrate MySpotify data storage from JSON files to SQLite database. This is **Phase 1**: create migration script and update reading code. Phase 2 (updating `download_library.py` to write to SQLite) will be done later after browser verification.

## Current State

**Data Flow:**
- Three JSON files in `./assets/`:
  - `user_library_{username}.json` - tracks with nested album/artist data
  - `audio_features_{username}.json` - audio analysis metrics
  - `artists_metadata_{username}.json` - artist info with genres
- `DataSingleton` (src/common/data.py) loads JSON → merges → pandas DataFrame
- Pages (library.py, home.py) consume `DataSingleton().df`

## Database Schema

### Semi-Normalized Design (4 tables)

**1. tracks** - Core track and album data (album denormalized for performance)
- Primary key: `track_id` (TEXT)
- Track fields: name, duration_ms, popularity, explicit, isrc, URIs
- Album fields: id, name, type, release_date, total_tracks, URIs
- JSON columns: album_images, album_artists, track_artists, available_markets
- Foreign key: `first_artist_id` → artists.artist_id
- Indexes: added_at, album_release_date, first_artist_id, album_id

**2. audio_features** - Audio analysis (1:1 with tracks)
- Primary key: `track_id` (FOREIGN KEY → tracks)
- Fields: danceability, energy, key, loudness, mode, speechiness, acousticness, instrumentalness, liveness, valence, tempo, time_signature

**3. artists** - Artist metadata
- Primary key: `artist_id` (TEXT)
- Fields: artist_name, popularity, followers_total
- JSON column: genres
- Indexes: artist_name, popularity

**4. track_artists** - Many-to-many junction table
- Composite key: (track_id, artist_id, artist_position)
- Foreign keys: track_id → tracks, artist_id → artists

**Rationale:**
- Balance normalization (data integrity) vs denormalization (query performance)
- JSON fields for variable-length arrays (artists, genres, images)
- Similar structure to current DataFrame for easier migration
- Optimized for read-heavy workload

## Implementation Steps

### Step 1: Create Migration Script

**File:** `bin/migrate_json_to_sqlite.py`

**Structure:**
```python
#!/usr/bin/env python3
"""
Usage:
    migrate_json_to_sqlite.py <username> [-h] [--db-path PATH] [--verify]
"""

# Functions:
# 1. load_json_files(username) - Load 3 JSON files
# 2. create_schema(conn) - Create 4 tables + indexes
# 3. insert_artists(conn, artists_data) - Insert artists first
# 4. insert_tracks(conn, library_data) - Insert tracks + albums
# 5. insert_track_artists(conn, library_data) - Insert junction records
# 6. insert_audio_features(conn, features_data) - Insert features (skip None)
# 7. verify_migration(db_path, ...) - 6 verification checks
# 8. main(username, db_path, verify) - Orchestrate with transaction
```

**Key Details:**
- Insertion order: artists → tracks → track_artists → audio_features (respect foreign keys)
- Use transaction for atomicity (all-or-nothing)
- Enable `PRAGMA foreign_keys = ON`
- JSON fields: Use `json.dumps()` when inserting, `json.loads()` when reading
- Handle None values in audio_features (Spotify API can return None)
- Default DB path: `./assets/spotify_data_{username}.db`

**Verification Checks:**
1. Record counts (tracks, artists, features)
2. Spot-check sample track data
3. Spot-check sample artist data
4. Spot-check sample audio features
5. Foreign key integrity (no orphaned tracks)
6. DataFrame equivalence (JSON vs SQLite)

### Step 2: Update DataSingleton

**File:** `src/common/data.py`

**Changes:**
1. Rename `read_data()` → `_read_from_json()` (keep current logic as fallback)
2. Add new `_read_from_sqlite(db_path)` method:
   - Connect to SQLite
   - Query tracks with column aliases (e.g., `track_name AS 'track.name'`)
   - Query audio_features with column aliases
   - Query artists with column aliases
   - Parse JSON columns back to Python objects (json.loads)
   - Merge DataFrames: tracks + features + artists
   - Compute 10 derived columns (SAME as current logic)
   - Return merged DataFrame
3. Update `read_data(username)` to:
   - Check if `./assets/spotify_data_{username}.db` exists
   - If yes: call `_read_from_sqlite()`
   - If no: call `_read_from_json()` (fallback)

**Column Mapping (SQLite → DataFrame):**
```python
# Tracks query:
SELECT
    track_id AS 'track.id',
    track_name AS 'track.name',
    track_duration_ms AS 'track.duration_ms',
    track_artists AS 'track.artists',  -- JSON column
    first_artist_id AS 'track.first_artist.id',
    album_name AS 'track.album.name',
    album_release_date AS 'track.album.release_date',
    ...
FROM tracks

# Then: df['track.artists'] = df['track.artists'].apply(json.loads)
```

**Derived Columns (preserve exactly):**
- `track.artist_names` - list of all artist names
- `track.artist_names_str` - comma-separated artist names
- `track.album.release_year` - extracted from release_date
- `track.album.release_decade` - computed using get_decade_from_release_date()
- `track.duration_sec` - milliseconds / 1000
- `track.duration_min` - formatted to 2 decimals
- `track.added_at.year` - extracted from added_at
- `track.first_artist.genres_str` - comma-separated genres

**Key Principle:** Pages (library.py, home.py) require ZERO modifications. DataFrame structure must be identical.

### Step 3: Testing & Verification

**Automated Verification:**
```bash
python bin/migrate_json_to_sqlite.py <username> --verify
```

**Manual Browser Testing:**
1. Run migration script
2. Start Flask app: `sh bin/run_server.sh <username>`
3. Verify home page:
   - Charts render correctly
   - Track/artist/genre counts match baseline
4. Verify library page:
   - Table loads with all tracks
   - Filtering works (test 3+ filters)
   - Sorting works (test 3+ columns)
   - Row selection works
5. Test playlist creation:
   - Select tracks
   - Create playlist
   - Verify in Spotify

**Data Integrity Checks:**
- Record counts match JSON files
- Sample data spot-checks pass
- Foreign key integrity verified
- DataFrame shapes identical (JSON vs SQLite)
- No console errors in Flask or browser

## Rollback Plan

**Immediate Rollback:**
```bash
# Simply delete the database - DataSingleton falls back to JSON
rm ./assets/spotify_data_{username}.db
sh bin/run_server.sh <username>
```

**Key Safety Feature:** JSON files are NEVER deleted. They serve as permanent backup and fallback.

## Files to Create/Modify

### Create:
- `bin/migrate_json_to_sqlite.py` (~500 lines)
  - Schema creation SQL
  - Data insertion functions
  - Verification functions
  - CLI interface

### Modify:
- `src/common/data.py` (89 → ~250 lines)
  - Add `_read_from_sqlite()` method
  - Rename `read_data()` → `_read_from_json()`
  - Add new dispatcher `read_data()`

### No Changes Needed:
- `src/pages/library.py` - Uses `DataSingleton().df` (unchanged interface)
- `src/pages/home.py` - Uses `DataSingleton().df` (unchanged interface)
- `src/app.py` - No data loading logic
- `bin/download_library.py` - Will update in Phase 2 (later)
- `notebooks/analysis_example.ipynb` - Can continue using JSON files

## Success Criteria

✅ Migration script completes without errors
✅ All 6 verification checks pass
✅ Flask app starts successfully
✅ Home page displays correctly (charts, counts)
✅ Library page shows all tracks
✅ Filtering works as before
✅ Sorting works as before
✅ Playlist creation works
✅ No errors in Flask logs or browser console
✅ Rollback tested and works

## Critical Implementation Details

**SQL Schema (tracks table):**
```sql
CREATE TABLE tracks (
    track_id TEXT PRIMARY KEY,
    added_at TEXT NOT NULL,
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

CREATE INDEX idx_tracks_added_at ON tracks(added_at);
CREATE INDEX idx_tracks_album_release_date ON tracks(album_release_date);
CREATE INDEX idx_tracks_first_artist_id ON tracks(first_artist_id);
CREATE INDEX idx_tracks_album_id ON tracks(album_id);
```

**Error Handling:**
- Wrap migration in try/except with conn.rollback()
- Check file existence before loading JSON
- Validate record counts after insertion
- Handle None values in audio_features gracefully

**Data Types:**
- IDs: TEXT (Spotify uses alphanumeric)
- Dates: TEXT (ISO 8601 format)
- Booleans: INTEGER (0 or 1, SQLite has no boolean type)
- Floats: REAL (audio features)
- Arrays: TEXT (JSON serialized)

## Next Steps (Phase 2 - Later)

After successful browser verification:
1. Update `bin/download_library.py` to write to SQLite
2. Use INSERT OR REPLACE for incremental updates
3. Optionally archive JSON files as backup
4. Update CLAUDE.md documentation

## Notes

- Database file: `./assets/spotify_data_{username}.db`
- Username from: `SPOTIPY_CLIENT_USERNAME` environment variable
- Estimated script runtime: ~30 seconds for 10K tracks
- Database size: ~10-15MB for 10K tracks (vs ~20MB JSON)
- Query performance: Expected faster load times vs JSON parsing
