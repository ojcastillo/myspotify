#!/usr/bin/env python3
"""
Download all the Spotify metadata of songs in the library of the given user. It will first ask the user to authorize the
interaction with its library, after which it requires the redirect URL defined for the app. It will then continue to
download 50 liked songs at a time as that's the limit per API request. Then from the list of liked songs retrieved, it
will proceed to download their audio features (100 at a time) and the metadata of artists (50 at a time).

The first time you run ths script, you should expect it to download ALL of your liked songs metadata. Be prepared to
wait a bit if you have a large library, the script took ~10mins for a ~10K library. The next time the script will just
download new liked songs, unless you pas the "--regenerate" argument intended for the case when past metadata needs to
be updated.

The results are saved the './assets/' folder.

Usage:
    download_library.py <username> <client_id> <client_secret> <redirect_uri> [-h] [--regenerate]

Options:
    -h --help           Show this help information
    --regenerate        Download ALL tracks liked by the user, as opposed to only downloading tracks not downloaded
                        before. Only run this if the metadata collected needs to be re-generated.
"""
import json
from random import randint
from time import sleep

import spotipy
from docopt import docopt
from spotipy.oauth2 import SpotifyOAuth


# Max tracks to download if set to something greater than 0, otherwise downloads everything.
# Intended just for targeted small tests.
MAX_TRACKS = 0


def get_user_library(sp, most_recent_track=None):
    print("Starting to download metadata of songs in library")
    limit = 50
    current_offset = 0
    track_list = []
    while True:
        print("Current track offset: ", current_offset)
        result = sp.current_user_saved_tracks(limit, current_offset)
        if not result["items"]:
            print("No tracks in response. Stopping download loop!")
            break

        if most_recent_track:
            stopped_early = False
            for track in result["items"]:
                if track["track"]["id"] == most_recent_track["track"]["id"]:
                    stopped_early = True
                    break
                track_list.append(track)
            if stopped_early:
                print("No need to download more songs as the rest was downloaded before. Stopping download loop!")
                break
        else:
            track_list.extend(result["items"])

        if not result["next"]:
            print("No more songs in library. Stopping download loop!")
            break

        if (MAX_TRACKS > 0) and (MAX_TRACKS <= len(track_list)):
            print(f"More than {MAX_TRACKS} songs already downloaded. Stopping download loop!")
            track_list = track_list[:MAX_TRACKS]
            break

        sleep(randint(1, 2))
        current_offset += limit
    return track_list


def get_audio_features(sp, tracks):
    print(f"Starting to download audio features of {len(tracks)} tracks")
    all_ids = [track["track"]["id"] for track in tracks]
    audio_features = []
    offset = 100
    for idx in range(0, len(all_ids), offset):
        print("Current audio feature offset: ", idx)
        audio_features.extend(sp.audio_features(all_ids[idx : (idx + offset)]))
        sleep(randint(1, 2))
    return audio_features


def get_artist_id_set_from_tracks(tracks):
    artists_per_track = [track["track"]["artists"] for track in tracks]
    return set([artist["id"] for artists in artists_per_track for artist in artists])


def get_artists_metadata(sp, artist_id_set):
    artist_id_list = list(artist_id_set)

    print(f"Starting to download artist metadata of {len(artist_id_list)} artists")
    metadata = []
    offset = 50
    for idx in range(0, len(artist_id_list), offset):
        print("Current artist metadata download offset: ", idx)
        metadata.extend(sp.artists(artist_id_list[idx : (idx + offset)])["artists"])
        sleep(randint(1, 2))
    return metadata


def load_json_file(file_path):
    try:
        with open(file_path, "r") as json_f:
            return json.load(json_f)
    except FileNotFoundError:
        return None


def main(args):
    """Entry point"""
    print(f"Starting script with the following arguments:")
    print(args)

    print("Asking for authorization from user (if this is the first time)")
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope="user-library-read",
            username=args["<username>"],
            redirect_uri=args["<redirect_uri>"],
            client_id=args["<client_id>"],
            client_secret=args["<client_secret>"],
        )
    )

    user_library_path = f"./assets/user_library_{args['<username>']}.json"
    audio_features_path = f"./assets/audio_features_{args['<username>']}.json"
    artists_metadata_path = f"./assets/artists_metadata_{args['<username>']}.json"
    if args["--regenerate"]:
        print("Downloading ALL liked tracks!")
        track_list = get_user_library(sp)

        print("Downloading audio features of tracks downloaded.")
        audio_features = get_audio_features(sp, track_list)

        print("Downloading metadata of artist linked to tracks downloaded.")
        artists_metadata = get_artists_metadata(sp, get_artist_id_set_from_tracks(track_list))
    else:
        print("Downloading liked tracks not downloaded before.")
        downloaded_tracks = load_json_file(user_library_path)
        most_recent_track = downloaded_tracks[0]

        new_tracks = get_user_library(sp, most_recent_track)
        if not new_tracks:
            print("Found no new liked tracks. Stopping script early!")
            return

        print(f"Found {len(new_tracks)} new liked tracks")
        track_list = new_tracks + downloaded_tracks

        print("Downloading audio features of new tracks downloaded only.")
        new_audio_features = get_audio_features(sp, new_tracks)
        downloaded_features = load_json_file(audio_features_path)
        audio_features = new_audio_features + downloaded_features

        print("Downloading metadata of new artists linked to tracks downloaded.")
        downloaded_artists_metadata = load_json_file(artists_metadata_path)
        downloaded_ids = {artist["id"] for artist in downloaded_artists_metadata}

        new_ids = get_artist_id_set_from_tracks(new_tracks)
        new_artists_only = new_ids - downloaded_ids

        if new_artists_only:
            print(f"Found {len(new_artists_only)} new artists. Proceeding to download their metadata")
            new_artists_metadata = get_artists_metadata(sp, new_artists_only)
            artists_metadata = new_artists_metadata + downloaded_artists_metadata
        else:
            print(f"No new artists found. No metadata to download.")
            artists_metadata = downloaded_artists_metadata

    print(f"Saving {len(track_list)} tracks to {user_library_path}")
    with open(user_library_path, "w") as json_f:
        json.dump(track_list, json_f)

    print(f"Saving {len(audio_features)} features to {audio_features_path}")
    with open(audio_features_path, "w") as json_f:
        json.dump(audio_features, json_f)

    print(f"Saving metadata of {len(artists_metadata)} artists to {artists_metadata_path}")
    with open(artists_metadata_path, "w") as json_f:
        json.dump(artists_metadata, json_f)


if __name__ == "__main__":
    main(docopt(__doc__, version="MySpotify 1.0"))
