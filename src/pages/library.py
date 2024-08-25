import dash
import dash_bootstrap_components as dbc

from common.data import DataSingleton
from common.spotify import SpotifyClientSingleton

dash.register_page(__name__)


def get_data_table(df):
    df["id"] = df["track.id"]
    columns = {
        "id": "Track ID",
        "added_at": "Date Added",
        "track.name": "Track",
        "track.album.name": "Album",
        "track.first_artist.name": "First Artist",
        "track.first_artist.genres": "Genres",
        "track.album.release_year": "Release Year",
        "track.album.release_decade": "Release Decade",
        "track.duration_min": "Duration (in mins)",
        "track.danceability": "Danceability",
        "track.energy": "Energy",
        "track.valence": "Valence",
    }
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
            dbc.Button("Select All", id="select-all-button", className="me-1"),
            dbc.Button("Deselect All", id="deselect-all-button", className="me-1"),
            dash.dcc.Input(
                id="playlist-name-input",
                type="text",
                placeholder="Name of playlist",
            ),
            dbc.Button("Create Playlist", id="create-playlist-button", className="me-1"),
            dash.html.Div("Selected rows: 0", id="display-selected-count", className="me-1"),
            dash.html.Div(f"Filtered rows: {df.shape[0]}", id="display-filtered-count", className="me-1"),
            dash.dcc.RadioItems(
                [{"label": "Read filter_query", "value": "read"}, {"label": "Write to filter_query", "value": "write"}],
                "read",
                id="filter-query-radio",
            ),
            dash.html.Br(),
            dash.dcc.Input(id="filter-query-input", placeholder="Enter filter query..."),
            dash.html.Div(id="filter-query-output"),
            dash.html.Hr(),
            dash.dash_table.DataTable(
                id="library-table",
                data=df[columns.keys()].to_dict("records"),
                columns=[{"name": name, "id": col_id} for col_id, name in columns.items() if col_id != "id"],
                sort_action="native",
                filter_action="native",
                row_selectable="multi",
                selected_rows=[],
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
