# CLAUDE.md

## Key Files

| What | Where |
|---|---|
| Flask app, OAuth routes (`/`, `/auth`) | `src/app.py` |
| Data loading, multi-user merge, SQLite/JSON fallback | `src/common/load_data.py` |
| SQLite schema + insert helpers (shared by scripts) | `src/common/db_helpers.py` |
| Library browser UI, playlist creation | `src/pages/library.py` |
| Stats/charts dashboard | `src/pages/home.py` |
| Sync logic (used by CLI + settings page) | `src/common/sync.py` |
| Settings page with per-user sync button | `src/pages/settings.py` |
| Add/register a user to allowed_users | `bin/add_user.py` |
| Download script (thin CLI wrapper around sync.py) | `bin/download_library.py` |
| One-time legacy JSON → SQLite migration | `bin/migrate_json_to_sqlite.py` |
| DB schema, data flow, auth flow, migration history | `ARCHITECTURE.md` |

## Development Commands

### Environment Setup (once per session)
```bash
sh init_workspace.sh
source .venv/bin/activate
```

### Running the Application
```bash
flask --app src/app.py --debug run
```

### Code Quality
```bash
black .    # 120-char line length (pyproject.toml)
```

### Data Collection
```bash
# Add a user (run once per user)
python bin/add_user.py <display_name> <spotify_user_id>
# e.g.: python bin/add_user.py orlando 1266569549

# Download/update library for a user (requires stored token from /auth)
python bin/download_library.py <spotify_user_id>
python bin/download_library.py <spotify_user_id> --regenerate   # Full refresh
python bin/download_library.py <spotify_user_id> --db-path PATH  # Custom DB

# Migrate legacy JSON files to SQLite (one-time only)
python bin/migrate_json_to_sqlite.py <username> [--db-path PATH] [--verify]
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your Spotify app credentials:
```
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
SPOTIPY_REDIRECT_URI=http://127.0.0.1:5000/auth
```

`SPOTIPY_CLIENT_USERNAME` is no longer used.

## Important Notes & Gotchas

- **Audio Features API is deprecated** (Spotify, Nov 2024). Download script skips audio features. Tracks migrated from old JSON files retain their audio features.
- **Incremental downloads**: script checks the latest `added_at` in the DB and only fetches newer tracks. Use `--regenerate` to force a full refresh.
- **Auth is optional for browsing**: `/` redirects straight to Dash with no login. Spotify OAuth (`/auth`) is only required for playlist creation.
- **Transaction integrity**: all DB writes are wrapped in transactions — an error during download rolls back the entire operation.
- **Rollback to JSON**: `rm ./assets/spotify_data.db` — the app falls back to JSON files automatically.
- **Testing with alternate DB**: use `--db-path`. The Flask app always expects `./assets/spotify_data.db`.
