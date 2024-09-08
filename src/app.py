import os

import dash
import dash_bootstrap_components as dbc
import spotipy
from flask import Flask, session, request, redirect
from flask_session import Session

from common.cache import FlaskSessionCacheHandler
from common.spotify import SpotifyClientSingleton


# Marker: APP_CREATION_STARTS #
server = Flask(__name__)
server.config["SECRET_KEY"] = os.urandom(64)
server.config["SESSION_TYPE"] = "filesystem"
server.config["SESSION_FILE_DIR"] = "./.flask_session/"
Session(server)

app = dash.Dash(
    __name__, server=server, use_pages=True, external_stylesheets=[dbc.themes.LUX], url_base_pathname="/dash/"
)
app.layout = dash.html.Div(
    [
        dash.html.Div(
            id="header-div",
            children=[
                dbc.NavbarSimple(
                    dbc.Nav(
                        [
                            dbc.NavLink(page["name"], href=page["relative_path"])
                            for page in dash.page_registry.values()
                        ],
                    ),
                    brand="MySpotify",
                    color="primary",
                    dark=True,
                ),
            ],
        ),
        dash.page_container,
    ]
)
# Marker: APP_CREATION_ENDS #


@server.route("/")
def index():
    cache_handler = FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(
        cache_handler=cache_handler,
        scope="user-library-read playlist-modify-private",
        show_dialog=True,
    )

    if request.args.get("code"):
        # Step 2. Being redirected from Spotify auth page
        auth_manager.get_access_token(request.args.get("code"))
        return redirect("/")

    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        # Step 1. Display sign in link when no token
        auth_url = auth_manager.get_authorize_url()
        return f'<h2><a href="{auth_url}">Sign in</a></h2>'

    # Step 4. Signed in - Setup Spotify singleton and redirected to dash app
    spotify_singleton = SpotifyClientSingleton()
    spotify_singleton.setup(auth_manager, cache_handler)
    return redirect("/dash")


@server.route("/sign_out")
def sign_out():
    session.pop("token_info", None)
    return redirect("/")


@server.route("/dash")
def dash_app():
    return app.index()


# Following lines allow application to be run more conveniently with
# `python app.py` (Make sure you're using python3)
# (Also includes directive to leverage pythons threading capacity.)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("SPOTIPY_REDIRECT_URI", 8080).split(":")[-1]))
    server.run(threaded=True, port=port, debug=True)
