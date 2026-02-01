# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup (Only once per session)
- Set up virtual environment: `sh init_workspace.sh`
- Activate virtual environment: `source .venv/bin/activate`

### Running the Application
- To spin up the Flask server, rely on `sh bin/run_server.sh orlando` command if the script `bin/run_server.sh` is available. Otherwise, fall back to `flask --app src/app.py --debug run`, but that will require environment variable defined in advance.
- Alternative: `python src/app.py` (runs on port from SPOTIPY_REDIRECT_URI or 8080)
- Jupyter notebooks: `jupyter notebook` then open `notebooks/analysis_example.ipynb`

### Code Quality
- Format code: `black` (configured for 120 character line length in pyproject.toml)

### Data Collection & Migration
- **Download Spotify library** (writes directly to SQLite):
  ```bash
  ./bin/download_library.py <client_username> <client_id> <client_secret> <redirect_uri> [--regenerate] [--db-path PATH]
  ```
  - Default database: `./assets/spotify_data.db`
  - `--regenerate`: Download ALL tracks (full refresh)
  - `--db-path PATH`: Custom database location for testing
  - Incremental downloads: Run without `--regenerate` to download only new liked songs
  - Data saved directly to SQLite database (no JSON intermediate files)

- **Migrate legacy JSON to SQLite** (one-time migration for old data):
  ```bash
  python bin/migrate_json_to_sqlite.py <username> [--db-path PATH] [--verify]
  ```
  - Only needed if you have existing JSON files from before Phase 3
  - Creates/updates SQLite database at `./assets/spotify_data.db`
  - Automatically verified by default with `--verify` flag
  - JSON files are preserved as backup

## Architecture Overview

### Core Application Structure
- **Flask + Dash hybrid**: Flask handles OAuth authentication, Dash provides the interactive UI
- **Singleton pattern**: Both SpotifyClientSingleton and DataSingleton use singleton pattern for shared state
- **Session-based auth**: Uses Flask sessions with filesystem storage for Spotify OAuth tokens

### Key Components

#### Authentication Flow (src/app.py)
1. Root route `/` handles Spotify OAuth (sign in, callback, token validation)
2. Successful auth redirects to `/dash` for the main application
3. SpotifyClientSingleton is initialized with auth manager and cache handler

#### Data Layer (src/common/)
- **DataSingleton**: Loads and processes user library, audio features, and artist metadata
  - **Primary source**: SQLite database (`./assets/spotify_data.db`) if available
  - **Fallback**: JSON files in `./assets/` directory (for backward compatibility)
  - Automatically detects and uses appropriate data source
- **db_helpers**: Shared database module for SQLite operations
  - Schema creation SQL constants
  - Insert functions with automatic deduplication (INSERT OR IGNORE)
  - Used by both download_library.py and migrate_json_to_sqlite.py
  - Eliminates code duplication across scripts
- **SpotifyClientSingleton**: Manages Spotify API client and playlist creation
- **cache.py**: Custom Flask session cache handler for Spotify tokens

#### UI Layer (src/pages/)
- **library.py**: Main interactive table for browsing/filtering tracks and creating playlists
- **home.py**: Dashboard/home page
- Uses Dash DataTable with filtering, sorting, and multi-select capabilities

### Data Flow

**Current Workflow (Phase 3+):**
1. Download script fetches data from Spotify API → writes directly to SQLite database
2. DataSingleton loads data from SQLite and merges into pandas DataFrame
3. Library page displays interactive table for playlist creation
4. SpotifyClientSingleton creates playlists via Spotify API

**Legacy Workflow (before Phase 3):**
1. Download script → JSON files → Migration script → SQLite database
2. Still supported for backward compatibility with existing JSON files

**Database Pipeline:**
```
Spotify API
    ↓
download_library.py (with --db-path)
    ↓
SQLite Database (./assets/spotify_data.db)
    ├── Global tables: tracks, artists, audio_features, track_artists
    └── User-specific: user_tracks (links users to their tracks)
    ↓
DataSingleton._read_from_sqlite()
    ↓
Pandas DataFrame (merged data for specific user)
    ↓
Flask/Dash UI (library.py, home.py)
```

### Database Schema (SQLite) - Fully Normalized
When using SQLite storage, data is organized in 5 tables (4 global + 1 user-specific):

**Global Tables** (shared across all users for deduplication):
- **tracks**: Track and album metadata - NO user_id
- **audio_features**: Audio analysis metrics (danceability, energy, etc.) - NO user_id
- **artists**: Artist metadata with genres and popularity - NO user_id
- **track_artists**: Junction table for many-to-many track-artist relationships - NO user_id

**User-Specific Table** (only table with user_id):
- **user_tracks**: Links users to their library tracks (user_id, track_id, added_at)

**Design Benefits:**
- Zero data duplication: tracks/artists/features shared across users
- Maximum space efficiency (28% space savings with multi-user deduplication)
- Single JOIN query: user_tracks → tracks → audio_features → artists
- Only user_tracks contains user-specific data

### Shared Database Module (src/common/db_helpers.py)

The database module provides reusable functions for both download and migration scripts:

**Schema Management:**
- `create_schema(conn)` - Creates all 5 tables with indexes

**Insert Functions** (all use INSERT OR IGNORE for deduplication):
- `insert_artists(conn, artists_data)` - Insert artist metadata
- `insert_tracks(conn, library_data)` - Insert track and album data
- `insert_track_artists(conn, library_data)` - Insert track-artist relationships
- `insert_audio_features(conn, features_data)` - Insert audio features (handles None)
- `insert_user_tracks(conn, username, library_data)` - Insert user-specific library data

**Benefits:**
- Single source of truth for database operations
- Eliminates code duplication between scripts
- Consistent INSERT OR IGNORE deduplication strategy
- Easier to maintain and update schema

### Environment Variables Required
```
SPOTIPY_CLIENT_ID
SPOTIPY_CLIENT_SECRET  
SPOTIPY_REDIRECT_URI
SPOTIPY_CLIENT_USERNAME
```

### File Naming Conventions
- **SQLite database**: `./assets/spotify_data.db` (single file for ALL users, not per-user)
- **Legacy JSON files**: `{data_type}_{username}.json` (e.g., `user_library_1137012579.json`)
  - Only created by old versions of download_library.py (before Phase 3)
  - Still supported as fallback data source
  - Can be migrated to SQLite using migrate_json_to_sqlite.py
- Session storage: `./.flask_session/` directory
- Assets stored in `./assets/` directory

### Multi-User Support
The SQLite database supports multiple users in a single file:
- Each user's tracks are stored in the `user_tracks` table with their `user_id`
- All music entities (tracks, artists, features) are shared globally
- Automatic deduplication: shared tracks/artists across users save space

**To add another user:**
```bash
# Download data for new user (writes directly to database)
./bin/download_library.py <new_username> <client_id> <client_secret> <redirect_uri>

# OR migrate existing JSON files for new user
python bin/migrate_json_to_sqlite.py <new_username> --verify
```

Both methods use `INSERT OR IGNORE` to automatically skip duplicate tracks/artists/features.

### Rollback to JSON
If you need to revert to JSON-based storage:
```bash
rm ./assets/spotify_data.db
```
The application will automatically fall back to reading JSON files (if they exist).

---

## Migration History & Notes

### Phase 1: Migration Script (Completed)
- Created `bin/migrate_json_to_sqlite.py` to convert existing JSON files to SQLite
- Implemented fully normalized schema (5 tables: 4 global + 1 user-specific)
- Added comprehensive verification with 6 automated checks

### Phase 2: Multi-User Testing (Completed)
- Added second user to test deduplication and data isolation
- Verified 28% space savings with shared tracks/artists
- Fixed JSON reading bugs (LEFT JOIN instead of inner merge)
- Confirmed zero data leakage between users

### Phase 3: Direct SQLite Downloads (Completed)
- Extracted shared database module (`src/common/db_helpers.py`)
- Updated download script to write directly to SQLite (no JSON intermediate)
- Refactored migration script to use shared module
- Eliminated 300+ lines of code duplication

### Key Workflow Changes

**Old Workflow:**
```
Spotify API → download_library.py → JSON files → migrate_json_to_sqlite.py → SQLite
```

**New Workflow:**
```
Spotify API → download_library.py → SQLite (direct write)
```

**Migration script is now only for:**
- Converting legacy JSON files to SQLite
- One-time migration of historical data
- Verification and testing purposes

### Important Notes

- **Audio Features API Deprecated**: Spotify deprecated the Audio Features API in November 2024. The download script skips audio features entirely. Existing tracks migrated from old JSON files will retain their audio features.

- **Incremental Downloads**: The download script queries the database for the most recent track (by `added_at` timestamp). It only downloads tracks newer than this. Use `--regenerate` to force a full refresh.

- **Database Path Override**: Use `--db-path` for testing with alternative databases. The default path (`./assets/spotify_data.db`) is what the Flask application expects.

- **Transaction Integrity**: All database writes are wrapped in transactions. If an error occurs during download, the entire operation is rolled back, leaving the database in a consistent state.

- **Deduplication**: All global tables use `INSERT OR IGNORE`. When multiple users share tracks/artists, only one copy is stored. The `user_tracks` table tracks which users have which tracks.