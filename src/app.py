import datetime
import os
import sqlite3

import dash
import dash_bootstrap_components as dbc
import spotipy
from dotenv import load_dotenv
from flask import Flask, session, request, redirect
from flask_session import Session

from common.cache import FlaskSessionCacheHandler
from common.db_helpers import get_available_users
from common.spotify import SpotifyClientSingleton

load_dotenv()

DB_PATH = "./assets/spotify_data.db"


def is_user_allowed(conn, spotify_user_id):
    """Check if spotify_user_id exists in allowed_users table."""
    from common.db_helpers import get_allowed_user
    return get_allowed_user(conn, spotify_user_id) is not None


def persist_token(conn, spotify_user_id, token_info):
    """Save OAuth token info to user_tokens table."""
    from common.db_helpers import save_user_token
    expiry = datetime.datetime.utcfromtimestamp(token_info["expires_at"]).isoformat() if token_info.get("expires_at") else None
    save_user_token(
        conn,
        spotify_user_id=spotify_user_id,
        access_token=token_info["access_token"],
        refresh_token=token_info.get("refresh_token"),
        token_expiry=expiry,
    )


# Marker: APP_CREATION_STARTS #
server = Flask(__name__)
server.config["SECRET_KEY"] = os.urandom(64)
server.config["SESSION_TYPE"] = "filesystem"
server.config["SESSION_FILE_DIR"] = "./.flask_session/"
Session(server)

# Query available users from the database at startup
available_users = get_available_users()
default_user_ids = [u["user_id"] for u in available_users]
user_dropdown_options = [{"label": u["display_name"], "value": u["user_id"]} for u in available_users]

app = dash.Dash(
    __name__, server=server, use_pages=True, external_stylesheets=[dbc.themes.LUX], url_base_pathname="/dash/"
)
app.config.suppress_callback_exceptions = True

app.layout = dash.html.Div(
    [
        dash.dcc.Store(id="selected-users-store", data=default_user_ids),
        dash.html.Div(
            id="header-div",
            children=[
                dbc.NavbarSimple(
                    children=[
                        dbc.Nav(
                            [
                                dbc.NavLink(page["name"], href=page["relative_path"])
                                for page in dash.page_registry.values()
                            ],
                        ),
                        dash.html.Div(
                            [
                                dash.html.Span(
                                    "Select Profiles:",
                                    style={"color": "white", "marginRight": "10px", "whiteSpace": "nowrap"},
                                ),
                                dash.dcc.Dropdown(
                                    id="user-selector",
                                    options=user_dropdown_options,
                                    value=default_user_ids,
                                    multi=True,
                                    placeholder="Select users...",
                                    style={"width": "300px", "color": "#333"},
                                ),
                            ],
                            style={
                                "marginLeft": "auto",
                                "display": "flex",
                                "alignItems": "center",
                                "backgroundColor": "rgba(255, 255, 255, 0.15)",
                                "borderRadius": "8px",
                                "padding": "6px 12px",
                            },
                        ),
                    ],
                    brand="MySpotify",
                    color="primary",
                    dark=True,
                ),
            ],
        ),
        dash.page_container,
    ]
)


@app.callback(
    dash.Output("selected-users-store", "data"),
    dash.Input("user-selector", "value"),
)
def update_selected_users(selected_users):
    if not selected_users:
        return default_user_ids
    return selected_users


# Marker: APP_CREATION_ENDS #


@server.route("/")
def index():
    return redirect("/dash")


@server.route("/auth")
def auth():
    cache_handler = FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(
        cache_handler=cache_handler,
        scope="user-library-read playlist-modify-private",
        show_dialog=True,
    )

    if request.args.get("code"):
        auth_manager.get_access_token(request.args.get("code"))
        return redirect("/auth")

    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        auth_url = auth_manager.get_authorize_url()
        return f'<h2><a href="{auth_url}">Sign in</a></h2>'

    # Token is valid — get the Spotify user ID and check allowlist
    sp = spotipy.Spotify(auth_manager=auth_manager)
    spotify_user_id = sp.current_user()["id"]

    conn = sqlite3.connect(DB_PATH)
    try:
        if not is_user_allowed(conn, spotify_user_id):
            session.pop("token_info", None)
            return f"<h2>Access denied: user {spotify_user_id} is not registered.</h2>", 403

        token_info = cache_handler.get_cached_token()
        persist_token(conn, spotify_user_id, token_info)
    finally:
        conn.close()

    # Signed in - Setup Spotify singleton and redirect to dash app
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
