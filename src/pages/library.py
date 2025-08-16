import dash
import dash_bootstrap_components as dbc

from common.data import DataSingleton
from common.spotify import SpotifyClientSingleton

dash.register_page(__name__)


TABLE_COLUMNS = [
    {"name": "Date Added", "id": "added_at"},
    {"name": "Track", "id": "track.name"},
    {"name": "Album", "id": "track.album.name"},
    {"name": "First Artist", "id": "track.first_artist.name"},
    {"name": "Genres", "id": "track.first_artist.genres_str"},
    {"name": "Release Year", "id": "track.album.release_year"},
    {"name": "Release Decade", "id": "track.album.release_decade"},
    {"name": "Duration (in mins)", "id": "track.duration_min"},
    {"name": "Danceability", "id": "track.danceability"},
    {"name": "Energy", "id": "track.energy"},
    {"name": "Valence", "id": "track.valence"},
]


def get_data_table(df):
    df["id"] = df["track.id"]
    data_columns = ["id"] + [col["id"] for col in TABLE_COLUMNS]
    return dash.html.Div(
        children=[
            dbc.Alert(
                "Created playlist successfully!",
                id="playlist-create-success",
                dismissable=True,
                fade=False,
                is_open=False,
            ),
            dbc.Alert(
                "Failed to create playlist",
                id="playlist-create-failure",
                dismissable=True,
                fade=False,
                is_open=False,
                color="danger",
            ),
            dash.dcc.Markdown("##### Create a playlist from selected rows:"),
            dbc.Button("Select All", id="select-all-button", className="me-1"),
            dbc.Button("Deselect All", id="deselect-all-button", className="me-1"),
            dash.dcc.Input(
                id="playlist-name-input",
                type="text",
                placeholder="Name of playlist",
            ),
            dbc.Button("Create Playlist", id="create-playlist-button", className="me-1"),
            dash.html.Br(),
            dash.html.Div(
                [
                    dash.html.Span("Selected rows: 0", id="display-selected-count", style={"margin-right": "10px"}),
                    dash.html.Span("|", style={"margin-right": "10px"}),
                    dash.html.Span(f"Filtered rows: {df.shape[0]}", id="display-filtered-count"),
                ]
            ),
            # dash.html.Div("Selected rows: 0", id="display-selected-count", className="me-1"),
            # dash.html.Div(f"Filtered rows: {df.shape[0]}", id="display-filtered-count", className="me-1"),
            dash.dcc.RadioItems(
                [
                    {"label": "Read filter_query", "value": "read"},
                    {"label": "Write to filter_query", "value": "write"},
                ],
                "read",
                id="filter-query-radio",
            ),
            dash.html.Br(),
            dash.dcc.Input(id="filter-query-input", placeholder="Enter filter query..."),
            dash.html.Div(id="filter-query-output"),
            dash.html.Br(),
            dash.html.Hr(),
            dash.dcc.Markdown("##### Select columns to display (filters on them would still work):"),
            dash.dcc.Checklist(
                id="column-selector",
                labelStyle={"display": "inline-flex", "align-items": "start", "padding": "5px"},
                options=[
                    {
                        "label": dash.dcc.Markdown(f'{col["name"]} (`{col["id"]})`'),
                        # "label": col["name"],
                        "value": col["id"],
                    }
                    for col in TABLE_COLUMNS
                ],
                value=[
                    "added_at",
                    "track.name",
                    "track.album.name",
                    "track.first_artist.name",
                    "track.first_artist.genres_str",
                    "track.album.release_year",
                ],
            ),
            dash.dash_table.DataTable(
                id="library-table",
                data=df[data_columns].to_dict("records"),
                columns=TABLE_COLUMNS,
                sort_action="native",
                filter_action="native",
                row_selectable="multi",
                selected_rows=[],
                style_header={"border": "1px solid pink", "position": "sticky", "top": 0},
                style_data={"border": "1px solid blue"},
                style_cell_conditional=[
                    {
                        "if": {"column_id": "track.first_artist.genres_str"},
                        "whiteSpace": "nowrap",
                        "overflow": "auto",
                        "maxWidth": "400px",
                    }
                ]
                + [
                    {
                        "if": {"column_id": c},
                        "whiteSpace": "normal",
                        "overflow": "auto",
                        "maxWidth": "300px",
                    }
                    for c in ["track.name", "track.album.name", "track.first_artist.name"]
                ],
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Create playlist?")),
                    dbc.ModalBody("Are you sure?"),
                    dbc.ModalFooter(
                        [
                            dbc.Button(
                                "Create",
                                id="modal-playlist-create-button",
                                className="me-1",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "Cancel",
                                id="modal-playlist-cancel-button",
                                className="me-1",
                                color="secondary",
                            ),
                        ]
                    ),
                ],
                id="modal-create-playlist",
                is_open=False,
            ),
        ],
    )


@dash.callback(
    dash.Output("library-table", "columns"),
    dash.Input("column-selector", "value"),
)
def update_columns(selected_columns):
    return [col for col in TABLE_COLUMNS if col["id"] in selected_columns]


@dash.callback(
    dash.Output("filter-query-input", "style"),
    dash.Output("filter-query-output", "style"),
    dash.Input("filter-query-radio", "value"),
)
def query_input_output(val):
    input_style = {"width": "100%"}
    output_style = {}
    if val == "read":
        input_style.update(display="none")
        output_style.update(display="inline-block")
    else:
        input_style.update(display="inline-block")
        output_style.update(display="none")
    return input_style, output_style


@dash.callback(dash.Output("filter-query-output", "children"), dash.Input("library-table", "filter_query"))
def read_query(query):
    if query is None:
        return "No filter query"
    return dash.dcc.Markdown('`filter_query = "{}"`'.format(query))


@dash.callback(dash.Output("library-table", "filter_query"), dash.Input("filter-query-input", "value"))
def write_query(query):
    if query is None:
        return ""
    return query


@dash.callback(
    dash.Output("display-selected-count", "children"),
    dash.Input("library-table", "selected_rows"),
)
def print_selected_rows(selected_rows):
    return f"Selected rows: {len(selected_rows)}"


@dash.callback(
    dash.Output("display-filtered-count", "children"),
    dash.Input("library-table", "derived_virtual_indices"),
)
def print_filtered_rows(derived_virtual_indices):
    cnt = 0 if derived_virtual_indices is None else len(derived_virtual_indices)
    return f"Filtered rows: {cnt}"


@dash.callback(
    dash.Output("library-table", "selected_rows"),
    dash.Input("select-all-button", "n_clicks"),
    dash.Input("deselect-all-button", "n_clicks"),
    dash.State("library-table", "derived_virtual_indices"),
)
def selection(_ignored_1, _ignored_2, derived_virtual_indices):
    ctx = dash.callback_context.triggered[0]
    ctx_caller = ctx["prop_id"]

    if derived_virtual_indices is None:
        raise dash.exceptions.PreventUpdate

    if ctx_caller == "select-all-button.n_clicks":
        print("len(filtered_indices)=", len(derived_virtual_indices))
        return derived_virtual_indices
    if ctx_caller == "deselect-all-button.n_clicks":
        return []
    raise dash.exceptions.PreventUpdate


@dash.callback(
    dash.Output("modal-create-playlist", "is_open"),
    dash.Input("create-playlist-button", "n_clicks"),
    dash.Input("modal-playlist-create-button", "n_clicks"),
    dash.Input("modal-playlist-cancel-button", "n_clicks"),
    dash.State("modal-create-playlist", "is_open"),
)
def show_create_playlist_modal(show_n_clicks, create_n_clicks, cancel_n_clicks, modal_is_open):
    # Nothing was clicked, so persist current state of modal
    if (not show_n_clicks) and (not create_n_clicks) and (not cancel_n_clicks):
        return modal_is_open
    # If something was clicked, switch modal visibility
    return not modal_is_open


@dash.callback(
    dash.Output("playlist-create-success", "is_open"),
    dash.Output("playlist-create-failure", "is_open"),
    dash.Input("modal-playlist-create-button", "n_clicks"),
    dash.State("playlist-create-success", "is_open"),
    dash.State("playlist-create-failure", "is_open"),
    dash.State("playlist-name-input", "value"),
    dash.State("library-table", "data"),
    dash.State("library-table", "selected_rows"),
)
def create_playlist(create_n_clicks, success_alert_is_open, failure_alert_is_open, playlist_name, data, selected_rows):
    if not selected_rows or not playlist_name:
        raise dash.exceptions.PreventUpdate

    # Nothing was clicked, so persist current state of modal/alert
    if not create_n_clicks:
        return success_alert_is_open, failure_alert_is_open

    track_list = [data[row]["id"] for row in selected_rows]
    spotify_singleton = SpotifyClientSingleton()
    try:
        spotify_singleton.create_playlist(playlist_name, track_list)
    except Exception as e:
        print(e)
        return False, True

    return True, False


def layout():
    data = DataSingleton()
    return dash.html.Div([get_data_table(data.df)])
