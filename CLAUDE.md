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
- Download Spotify library: `./bin/download_library.py <client_username> <client_id> <client_secret> <redirect_uri> [--regenerate]`
- Migrate JSON to SQLite: `python bin/migrate_json_to_sqlite.py <username> [--verify]` (run once after downloading data)
  - Creates SQLite database at `./assets/spotify_data_{username}.db`
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
  - **Primary source**: SQLite database (`./assets/spotify_data_{username}.db`) if available
  - **Fallback**: JSON files in `./assets/` directory (for backward compatibility)
  - Automatically detects and uses appropriate data source
- **SpotifyClientSingleton**: Manages Spotify API client and playlist creation
- **cache.py**: Custom Flask session cache handler for Spotify tokens

#### UI Layer (src/pages/)
- **library.py**: Main interactive table for browsing/filtering tracks and creating playlists
- **home.py**: Dashboard/home page
- Uses Dash DataTable with filtering, sorting, and multi-select capabilities

### Data Flow
1. External script downloads Spotify data → JSON files in `./assets/`
2. (Optional) Migration script converts JSON → SQLite database in `./assets/`
3. DataSingleton loads data from SQLite (or falls back to JSON) and merges into pandas DataFrame
4. Library page displays interactive table for playlist creation
5. SpotifyClientSingleton creates playlists via Spotify API

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
- Maximum space efficiency
- Single JOIN query: user_tracks → tracks → audio_features → artists
- Only user_tracks contains user-specific data

### Environment Variables Required
```
SPOTIPY_CLIENT_ID
SPOTIPY_CLIENT_SECRET  
SPOTIPY_REDIRECT_URI
SPOTIPY_CLIENT_USERNAME
```

### File Naming Conventions
- JSON data files: `{data_type}_{username}.json` (e.g., `user_library_1137012579.json`)
- **SQLite database**: `spotify_data.db` (single file for ALL users, not per-user)
- Session storage: `./.flask_session/` directory
- Assets stored in `./assets/` directory

### Multi-User Support
The SQLite database supports multiple users in a single file:
- Each user's tracks are stored in the `user_tracks` table with their `user_id`
- All music entities (tracks, artists, features) are shared globally
- To add another user: `python bin/migrate_json_to_sqlite.py <new_username> --verify`

### Rollback to JSON
If you need to revert to JSON-based storage:
```bash
rm ./assets/spotify_data.db
```
The application will automatically fall back to reading JSON files.