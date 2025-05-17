# MySpotify

This repo allows running a Flask/Dash app which can be used to create playlists based on liked songs.

## Initial Setup

### Set up virtual environment

You can use the command below to set up the environment. Make sure you're using Python 3.8+

```bash
. init_workspace.sh
```

## Command Line Utilities

### Download all of your library metadata

You can use the following script tp download all the Spotify metadata of songs in the library of a given user:
```bash
./bin/download_library.py <client_username> <client_id> <client_secret> <redirect_uri> [-h] [--regenerate]
```

Check the help message of the script to learn more about how to run. 

#### Requirements

- Spotify client credentials: a client ID and a client secret.  Follow the official guide
[here](https://developer.spotify.com/documentation/general/guides/authorization/app-settings)
to learn how to generate them. In the process you should also get a redirect URI allowed.
- Spotify username. This [article](https://www.androidauthority.com/how-to-find-spotify-username-3071901/)
should help you find it.

## Flask Server

### Quickstart

1. Set up required environment variables:
    ```sh
    export SPOTIPY_CLIENT_ID="<client_id>"
    export SPOTIPY_CLIENT_SECRET="<client_secret>"
    export SPOTIPY_REDIRECT_URI="<redirect_uri>"
    export SPOTIPY_CLIENT_USERNAME="<client_username>"
    ```
2. Start Flask server with `flask --app src/app.py --debug run`

## Jupyter Notebooks

Run `jupyter notebook` and once the server is up, you can now open **notebooks/analysis_example.ipynb**

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE) file for details
