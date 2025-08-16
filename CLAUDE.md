# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- Set up virtual environment: `. init_workspace.sh`
- Activate virtual environment: `source .venv/bin/activate`

### Running the Application
- Start Flask server: `flask --app src/app.py --debug run`
- Alternative: `python src/app.py` (runs on port from SPOTIPY_REDIRECT_URI or 8080)
- Jupyter notebooks: `jupyter notebook` then open `notebooks/analysis_example.ipynb`

### Code Quality
- Format code: `black` (configured for 120 character line length in pyproject.toml)

### Data Collection
- Download Spotify library: `./bin/download_library.py <client_username> <client_id> <client_secret> <redirect_uri> [--regenerate]`

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
- **DataSingleton**: Loads and processes user library, audio features, and artist metadata from JSON files
- **SpotifyClientSingleton**: Manages Spotify API client and playlist creation
- **cache.py**: Custom Flask session cache handler for Spotify tokens

#### UI Layer (src/pages/)
- **library.py**: Main interactive table for browsing/filtering tracks and creating playlists
- **home.py**: Dashboard/home page
- Uses Dash DataTable with filtering, sorting, and multi-select capabilities

### Data Flow
1. External script downloads Spotify data → JSON files in `./assets/`
2. DataSingleton merges library, audio features, and artist metadata into pandas DataFrame
3. Library page displays interactive table for playlist creation
4. SpotifyClientSingleton creates playlists via Spotify API

### Environment Variables Required
```
SPOTIPY_CLIENT_ID
SPOTIPY_CLIENT_SECRET  
SPOTIPY_REDIRECT_URI
SPOTIPY_CLIENT_USERNAME
```

### File Naming Conventions
- Data files: `{data_type}_{username}.json` (e.g., `user_library_1137012579.json`)
- Session storage: `./.flask_session/` directory
- Assets stored in `./assets/` directory