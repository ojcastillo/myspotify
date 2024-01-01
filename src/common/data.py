import json

import pandas as pd


class DataSingleton:

    def __new__(cls):
        if not hasattr(cls, 'instance'):
          cls.instance = super(DataSingleton, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self.df = self.read_data()

    @staticmethod
    def get_decade_from_release_date(release_date):
        year = int(release_date.split('-')[0])
        century = (year // 100) * 100
        decade_in_century = ((year % 100) // 10)
        return century + (decade_in_century * 10)

    @staticmethod
    def read_data():
        with open('./assets/user_library.json') as json_f:
            json_data = json.load(json_f)
            tracks_df = pd.json_normalize(json_data)

        with open('./assets/audio_features.json') as json_f:
            json_data = json.load(json_f)
            features_df = pd.json_normalize(json_data)
            clean_features_df = (
                features_df
                    .rename(columns={col: f"track.{col}" for col in features_df.columns})
                    .drop(columns=["track.type", "track.uri", "track.duration_ms"])
            )

        merged_df = tracks_df.merge(clean_features_df, on="track.id")

        merged_df['track.artists'] = merged_df['track.album.artists'].apply(
            lambda artists: [a['name'] for a in artists]
        )
        merged_df['track.first_artist'] = merged_df['track.artists'].apply(
            lambda artists: artists[0]
        )
        merged_df['track.album.release_year'] = merged_df['track.album.release_date'].apply(
            lambda release_date: int(release_date.split('-')[0])
        )
        merged_df['track.album.release_decade'] = merged_df['track.album.release_date'].apply(
            lambda release_date: DataSingleton.get_decade_from_release_date(release_date)
        )
        merged_df['track.duration_sec'] = merged_df['track.duration_ms'].apply(
            lambda duration_ms: duration_ms / 1000
        )
        merged_df['track.duration_min'] = merged_df['track.duration_sec'].apply(
            lambda duration_sec: float(f"%.2f" % (duration_sec / 60))
        )

        return merged_df
