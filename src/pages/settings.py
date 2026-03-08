import os
import sqlite3
import threading

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback

from common.db_helpers import DEFAULT_DB_PATH

dash.register_page(__name__, path="/settings", name="Settings")

DB_PATH = DEFAULT_DB_PATH

# Track sync status per user in memory (good enough for single-server local use)
_sync_status = {}


def get_users_with_status():
    """Return list of user dicts with sync metadata for the settings table."""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                au.spotify_user_id,
                au.display_name,
                MAX(ut.added_at) AS last_synced,
                CASE WHEN tok.access_token IS NOT NULL THEN 1 ELSE 0 END AS has_token
            FROM allowed_users au
            LEFT JOIN user_tracks ut ON ut.user_id = au.spotify_user_id
            LEFT JOIN user_tokens tok ON tok.spotify_user_id = au.spotify_user_id
            GROUP BY au.spotify_user_id
            ORDER BY au.display_name
        """)
        rows = cursor.fetchall()
        return [
            {
                "spotify_user_id": r[0],
                "display_name": r[1],
                "last_synced": r[2] or "Never",
                "has_token": bool(r[3]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def layout():
    users = get_users_with_status()

    if not users:
        return html.Div([
            html.H2("Settings"),
            html.P("No users registered. Run: python bin/add_user.py <name> <spotify_id>"),
        ], className="p-4")

    rows = []
    for u in users:
        uid = u["spotify_user_id"]
        status = _sync_status.get(uid, "")
        rows.append(
            html.Tr([
                html.Td(u["display_name"]),
                html.Td(uid),
                html.Td(u["last_synced"]),
                html.Td("Authenticated" if u["has_token"] else "No token"),
                html.Td(
                    dbc.Button(
                        "Sync",
                        id={"type": "sync-btn", "index": uid},
                        color="primary",
                        size="sm",
                        disabled=not u["has_token"],
                    )
                ),
                html.Td(html.Span(status, id={"type": "sync-status", "index": uid})),
            ])
        )

    table = dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("Display Name"),
                html.Th("Spotify ID"),
                html.Th("Last Synced"),
                html.Th("Auth Status"),
                html.Th("Action"),
                html.Th("Status"),
            ])),
            html.Tbody(rows),
        ],
        bordered=True,
        hover=True,
        striped=True,
    )

    return html.Div([
        html.H2("Settings", className="mb-4"),
        table,
        dcc.Interval(id="settings-poll", interval=3000, n_intervals=0),
    ], className="p-4")


@callback(
    Output({"type": "sync-status", "index": dash.ALL}, "children"),
    Output({"type": "sync-btn", "index": dash.ALL}, "disabled"),
    Input("settings-poll", "n_intervals"),
    State({"type": "sync-status", "index": dash.ALL}, "id"),
    State({"type": "sync-btn", "index": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def poll_sync_status(n, status_ids, btn_ids):
    statuses = [_sync_status.get(i["index"], "") for i in status_ids]
    disabled = [_sync_status.get(i["index"]) == "Syncing..." for i in btn_ids]
    return statuses, disabled


@callback(
    Output({"type": "sync-btn", "index": dash.MATCH}, "disabled"),
    Input({"type": "sync-btn", "index": dash.MATCH}, "n_clicks"),
    State({"type": "sync-btn", "index": dash.MATCH}, "id"),
    prevent_initial_call=True,
)
def trigger_sync(n_clicks, btn_id):
    if not n_clicks:
        return dash.no_update

    uid = btn_id["index"]
    _sync_status[uid] = "Syncing..."

    def do_sync():
        try:
            from common.sync import run_sync
            run_sync(spotify_user_id=uid, db_path=DB_PATH)
            _sync_status[uid] = "Done"
        except Exception as e:
            _sync_status[uid] = f"Error: {e}"

    threading.Thread(target=do_sync, daemon=True).start()
    return True  # disable button while syncing
