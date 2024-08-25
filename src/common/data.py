import json
import os

import pandas as pd


class DataSingleton:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(DataSingleton, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self.df = self.read_data(os.getenv("SPOTIPY_CLIENT_USERNAME"))

    @staticmethod
    def get_decade_from_release_date(release_date):
        year = int(release_date.split("-")[0])
        century = (year // 100) * 100
        decade_in_century = (year % 100) // 10
        return century + (decade_in_century * 10)

    @staticmethod
    def read_data(spotify_client_username):
        print(f"Reading data for spotify_client_username={spotify_client_username}")

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
        merged_df = tracks_df.merge(clean_features_df, on="track.id").merge(
            artists_for_join_df, on="track.first_artist.id"
        )

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

        return merged_df
