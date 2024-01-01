#!/usr/bin/env python3
"""
Download all the Spotify metadata of songs in the library of the given user. It will first ask the user to authorize the
interaction with its library, after which it requires the redirect URL so it can continue to download 50 songs at a time
as that's the limit per API request.

The first time you run ths script, you should expect it to download ALL of your liked songs. Be prepared to wait a bit
if you have a large library, the script took ~10mins for a ~10K library. The next time the script will just download new
liked songs, unless you pas the "--regenerate" argument intended for the case when past metadata needs to be updated.

The results are saved into the path './assets/user_library.json' and './assets/audio_features.json'.

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


def get_user_library(sp, most_recent_track=None, max_items=None):
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


def get_audio_features(sp, all_tracks):
    print(f"Starting to download audio features of {len(all_tracks)} tracks")
    all_ids = [track["track"]["id"] for track in all_tracks]
    # audio_features = sp.audio_features(all_ids[:2])
    audio_features = []
    offset = 100
    for idx in range(0, len(all_ids), offset):
        print("Current audio feature offset: ", idx)
        audio_features.extend(sp.audio_features(all_ids[idx : (idx + offset)]))
        sleep(randint(1, 2))
    return audio_features


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

    user_library_path = "./assets/user_library.json"
    audio_features_path = "./assets/audio_features.json"
    if args["--regenerate"]:
        print("Downloading ALL liked tracks!")
        track_list = get_user_library(sp)

        print("Downloading audio features of tracks downloaded.")
        audio_features = get_audio_features(sp, track_list)
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

    print(f"Saving {len(track_list)} tracks to {user_library_path}")
    with open(user_library_path, "w") as json_f:
        json.dump(track_list, json_f)

    print(f"Saving {len(audio_features)} features to {audio_features_path}")
    with open(audio_features_path, "w") as json_f:
        json.dump(audio_features, json_f)


if __name__ == "__main__":
    main(docopt(__doc__, version="MySpotify 1.0"))
