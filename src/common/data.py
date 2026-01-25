import json
import os
import sqlite3

import pandas as pd


class DataSingleton:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(DataSingleton, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        username = os.getenv("SPOTIPY_CLIENT_USERNAME")
        self.df = self.read_data(username)

    @staticmethod
    def get_decade_from_release_date(release_date):
        year = int(release_date.split("-")[0])
        century = (year // 100) * 100
        decade_in_century = (year % 100) // 10
        return century + (decade_in_century * 10)

    @staticmethod
    def read_data(spotify_client_username):
        """
        Read data from SQLite database or fall back to JSON files.
        """
        print(f"Reading data for spotify_client_username={spotify_client_username}")

        # Fixed database path - single database for all users
        db_path = "./assets/spotify_data.db"

        # Check if SQLite database exists
        if os.path.exists(db_path):
            print(f"Loading data from SQLite database: {db_path}")
            return DataSingleton._read_from_sqlite(db_path, spotify_client_username)
        else:
            # Fallback to JSON for backward compatibility
            print(f"Database {db_path} not found, falling back to JSON files")
            return DataSingleton._read_from_json(spotify_client_username)

    @staticmethod
    def _read_from_sqlite(db_path, username):
        """Read and merge data from SQLite database using JOIN query from user_tracks."""
        conn = sqlite3.connect(db_path)

        try:
            # Single JOIN query from user_tracks to all global tables
            # Filter by user_id on user_tracks table only
            merged_df = pd.read_sql_query("""
                SELECT
                    ut.added_at,
                    t.track_id AS 'track.id',
                    t.track_name AS 'track.name',
                    t.track_duration_ms AS 'track.duration_ms',
                    t.track_popularity AS 'track.popularity',
                    t.track_explicit AS 'track.explicit',
                    t.track_is_local AS 'track.is_local',
                    t.track_disc_number AS 'track.disc_number',
                    t.track_track_number AS 'track.track_number',
                    t.track_uri AS 'track.uri',
                    t.track_href AS 'track.href',
                    t.track_spotify_url AS 'track.external_urls.spotify',
                    t.track_preview_url AS 'track.preview_url',
                    t.track_isrc AS 'track.external_ids.isrc',
                    t.album_id AS 'track.album.id',
                    t.album_name AS 'track.album.name',
                    t.album_type AS 'track.album.album_type',
                    t.album_type AS 'track.album.type',
                    t.album_release_date AS 'track.album.release_date',
                    t.album_release_date_precision AS 'track.album.release_date_precision',
                    t.album_total_tracks AS 'track.album.total_tracks',
                    t.album_uri AS 'track.album.uri',
                    t.album_href AS 'track.album.href',
                    t.album_spotify_url AS 'track.album.external_urls.spotify',
                    t.album_images AS 'track.album.images',
                    t.album_artists AS 'track.album.artists',
                    t.track_artists AS 'track.artists',
                    t.first_artist_id AS 'track.first_artist.id',
                    t.available_markets AS 'track.available_markets',
                    t.available_markets AS 'track.album.available_markets',
                    'track' AS 'track.type',
                    af.danceability AS 'track.danceability',
                    af.energy AS 'track.energy',
                    af.key AS 'track.key',
                    af.loudness AS 'track.loudness',
                    af.mode AS 'track.mode',
                    af.speechiness AS 'track.speechiness',
                    af.acousticness AS 'track.acousticness',
                    af.instrumentalness AS 'track.instrumentalness',
                    af.liveness AS 'track.liveness',
                    af.valence AS 'track.valence',
                    af.tempo AS 'track.tempo',
                    af.time_signature AS 'track.time_signature',
                    af.track_href AS 'track.track_href',
                    af.analysis_url AS 'track.analysis_url',
                    a.artist_name AS 'track.first_artist.name',
                    a.genres AS 'track.first_artist.genres',
                    a.popularity AS 'track.first_artist.popularity',
                    a.followers_total AS 'track.first_artist.followers'
                FROM user_tracks ut
                JOIN tracks t ON ut.track_id = t.track_id
                LEFT JOIN audio_features af ON t.track_id = af.track_id
                LEFT JOIN artists a ON t.first_artist_id = a.artist_id
                WHERE ut.user_id = ?
            """, conn, params=(username,))

            # Parse JSON columns back to Python objects
            merged_df['track.artists'] = merged_df['track.artists'].apply(json.loads)
            merged_df['track.album.artists'] = merged_df['track.album.artists'].apply(json.loads)
            merged_df['track.album.images'] = merged_df['track.album.images'].apply(json.loads)
            merged_df['track.available_markets'] = merged_df['track.available_markets'].apply(json.loads)
            merged_df['track.album.available_markets'] = merged_df['track.album.available_markets'].apply(json.loads)
            merged_df['track.first_artist.genres'] = merged_df['track.first_artist.genres'].apply(json.loads)

            # Compute derived columns (SAME AS BEFORE - no changes needed)
            merged_df["track.artist_names"] = merged_df["track.artists"].apply(
                lambda artists: [a["name"] for a in artists]
            )
            merged_df["track.artist_names_str"] = merged_df["track.artists"].apply(
                lambda artists: ", ".join([a["name"] for a in artists])
            )
            merged_df["track.album.release_year"] = merged_df["track.album.release_date"].apply(
                lambda release_date: int(release_date.split("-")[0])
            )
            merged_df["track.album.release_decade"] = merged_df["track.album.release_date"].apply(
                lambda release_date: DataSingleton.get_decade_from_release_date(release_date)
            )
            merged_df["track.duration_sec"] = merged_df["track.duration_ms"].apply(
                lambda duration_ms: duration_ms / 1000
            )
            merged_df["track.duration_min"] = merged_df["track.duration_sec"].apply(
                lambda duration_sec: float(f"%.2f" % (duration_sec / 60))
            )
            merged_df["track.added_at.year"] = merged_df["added_at"].str.split("-").str.get(0).astype(int)
            merged_df["track.first_artist.genres_str"] = merged_df["track.first_artist.genres"].apply(
                lambda genres: ", ".join(genres)
            )

            print(f"Loaded {len(merged_df)} tracks from database for user {username}")
            return merged_df

        finally:
            conn.close()

    @staticmethod
    def _read_from_json(spotify_client_username):
        """
        Original JSON reading logic - kept for backward compatibility and fallback.
        """
        print(f"Reading data from JSON files for username={spotify_client_username}")

        with open(f"./assets/user_library_{spotify_client_username}.json") as json_f:
            json_data = json.load(json_f)
            tracks_df = pd.json_normalize(json_data)

        with open(f"./assets/audio_features_{spotify_client_username}.json") as json_f:
            json_data = json.load(json_f)
            features_df = pd.json_normalize(json_data)
            clean_features_df = features_df.rename(columns={col: f"track.{col}" for col in features_df.columns}).drop(
                columns=["track.type", "track.uri", "track.duration_ms"]
            )

        with open(f"./assets/artists_metadata_{spotify_client_username}.json") as json_f:
            json_data = json.load(json_f)
            artists_df = pd.json_normalize(json_data)

            artists_for_join_df = artists_df[["id", "name", "genres", "popularity", "followers.total"]].rename(
                columns={
                    "id": "track.first_artist.id",
                    "name": "track.first_artist.name",
                    "genres": "track.first_artist.genres",
                    "popularity": "track.first_artist.popularity",
                    "followers.total": "track.first_artist.followers",
                }
            )

        tracks_df["track.first_artist.id"] = tracks_df["track.artists"].apply(lambda artists: artists[0]["id"])
        merged_df = tracks_df.merge(clean_features_df, on="track.id", how="left").merge(
            artists_for_join_df, on="track.first_artist.id", how="left"
        )

        # Drop duplicates that may occur due to duplicate track IDs in source JSON files
        merged_df = merged_df.drop_duplicates(subset=['track.id'], keep='first')

        merged_df["track.artist_names"] = merged_df["track.artists"].apply(lambda artists: [a["name"] for a in artists])
        merged_df["track.artist_names_str"] = merged_df["track.artists"].apply(
            lambda artists: ", ".join([a["name"] for a in artists])
        )

        merged_df["track.album.release_year"] = merged_df["track.album.release_date"].apply(
            lambda release_date: int(release_date.split("-")[0])
        )
        merged_df["track.album.release_decade"] = merged_df["track.album.release_date"].apply(
            lambda release_date: DataSingleton.get_decade_from_release_date(release_date)
        )
        merged_df["track.duration_sec"] = merged_df["track.duration_ms"].apply(lambda duration_ms: duration_ms / 1000)
        merged_df["track.duration_min"] = merged_df["track.duration_sec"].apply(
            lambda duration_sec: float(f"%.2f" % (duration_sec / 60))
        )

        merged_df["track.added_at.year"] = merged_df["added_at"].str.split("-").str.get(0).astype(int)

        merged_df["track.first_artist.genres_str"] = merged_df["track.first_artist.genres"].apply(
            lambda genres: ", ".join(genres)
        )

        return merged_df

    @staticmethod
    def get_artist_cnt(df):
        return df.explode("track.artist_names")["track.artist_names"].nunique()

    @staticmethod
    def get_first_artist_genre_cnt(df):
        col_name = "track.first_artist.genres"
        return df.explode(col_name)[col_name].nunique()
