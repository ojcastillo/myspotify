import spotipy


class InvalidCachedToken(Exception):
    pass


class SpotifyClientSingleton:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(SpotifyClientSingleton, cls).__new__(cls)
        return cls.instance

    def setup(self, auth_manager, cache_handler):
        self.auth_manager = auth_manager
        self.cache_handler = cache_handler

    def create_playlist(self, name, track_list):
        if not self.auth_manager.validate_token(self.cache_handler.get_cached_token()):
            raise InvalidCachedToken

        sp = spotipy.Spotify(auth_manager=self.auth_manager)
        print(f"Creating playlist with name {name}")
        response = sp.user_playlist_create(
            user=sp.me()["id"],
            name=name,
            public=False,
        )

        playlist_id = response["id"]
        batch_size = 100
        num_tracks = len(track_list)
        print(f"Adding {num_tracks} tracks in batches of {batch_size}")
        for idx in range(0, num_tracks, batch_size):
            print(f"Adding tracks from {idx} to {idx + batch_size}")
            track_batch = track_list[idx : idx + batch_size]
            sp.playlist_add_items(
                playlist_id=playlist_id,
                items=track_batch,
            )
