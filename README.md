# MySpotify

A family of scripts I created to analyze my personal Spotify library.

## Initial Setup

### Installing Dependencies

You can find all the Python dependencies in the `requirements.txt` file. It is recommended to use a `conda` managed environment.

Running the following command will set up a `conda` environment automatically, assuming `conda` is installed ([instructions](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)).

```bash
. init_workspace.sh
```

## Command Line Utilities

### Download all of your library metadata

Download all the Spotify metadata of songs in the library of the given user. It will first ask the user to authorize the interaction with its library, after which it requires the redirect URL so it can continue to download 50 songs at a time until it can't find any more of them or until 10,000 songs are downloaded. The results are saved into the path './resources/user_library.json'.

```bash
./bin/download_library.py <username> <client_id> <client_secret> <redirect_uri>
```

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE) file for details
