#!/usr/bin/env python3
"""
Download all the Spotify metadata of songs in the library of the given user. It
will first ask the user to authorize the interaction with its library, after
which it requires the redirect URL so it can continue to download 50 songs at a
time until it can't find any more of them or until 10,000 songs are downloaded.
The results are saved into the path './resources/user_library.json'.

Usage:
    download_library.py <username> <client_id> <client_secret> <redirect_uri>

Options:
    -h --help:  Show this help information

"""
import json
from random import randint
import sys
from time import sleep

from docopt import docopt

import spotipy
from spotipy.oauth2 import SpotifyOAuth


def main(args):
    """Entry point"""
    print('Asking for authorization from user (if this is the first time)')
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope="user-library-read",
        username=args["<username>"],
        redirect_uri=args["<redirect_uri>"],
        client_id=args["<client_id>"],
        client_secret=args["<client_secret>"],
    ))

    print("Starting to download metadata of songs in library")
    limit = 50
    current_offset = 0
    all_tracks = []
    while True:
        print('Current track offset: ', current_offset)
        result = sp.current_user_saved_tracks(limit, current_offset)
        if not result['items']:
            break
        all_tracks.extend(result['items'])
        if not result['next']:
            print("No more songs in library, concluding download process")
            break
        sleep(randint(1,2))
        current_offset += limit
        if current_offset > 10000:
            print('More than 10000 songs already, better to stop!')
            break

    path = './resources/user_library.json'
    print(f'Saving {len(all_tracks)} tracks to {path}')
    with open(path, "w") as json_f:
        json.dump(all_tracks, json_f)

if __name__=="__main__":
    main(docopt(__doc__, version='MySpotify 1.0'))
