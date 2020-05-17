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
import spotipy.util as util

def trim_item(item):
    """Trims unnecessary fields in the track item"""
    track = item['track']
    if 'album' in track:
        to_delete = ['album_type', 'available_markets', 'external_urls', 'href',
                     'images', 'uri']
        for key in to_delete:
            try:
                del track['album'][key]
            except KeyError:
                pass
    to_delete = ['available_markets', 'external_ids', 'external_urls', 'href',
                 'is_local', 'preview_url', 'uri']
    for key in to_delete:
        try:
            del track[key]
        except KeyError:
            pass
    return item

def main(args):
    """Entry point"""
    print('Asking for authorization from user (if this is the first time)')
    token = util.prompt_for_user_token(
        args["<username>"],
        'user-library-read',
        client_id=args["<client_id>"],
        client_secret=args["<client_secret>"],
        redirect_uri=args["<redirect_uri>"],
    )
    assert token is not None, f"Can't get access token for {username}"

    print("Starting to download metadata of songs in library")
    sp = spotipy.Spotify(auth=token)
    limit = 50
    current_offset = 0
    all_tracks = []
    while True:
        print('Current track offset: ', current_offset)
        result = sp.current_user_saved_tracks(limit, current_offset)
        if not result['items']:
            break
        all_tracks.extend([trim_item(item) for item in result['items']])
        if not result['next']:
            print("Concluding download process")
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
