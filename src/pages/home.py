import dash
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots

from common.data import DataSingleton


dash.register_page(__name__, path="/")


def get_counts_div(df):
    return dash.html.Div(
        id="counts-div",
        children=[
            dash.dcc.Markdown(
                children=f"""
                ## General Stats
                - **Number of tracks**: {df.shape[0]}
                - **Number of unique artists**: {DataSingleton.get_artist_cnt(df)}
                - **Number of unique genres from first artists**: {DataSingleton.get_first_artist_genre_cnt(df)}
            """
            ),
        ],
    )


def get_library_plots_div(df):
    clean_df = df[df["track.album.release_decade"] > 0]
    year_df = clean_df.groupby("track.album.release_year").size().reset_index(name="count")
    decade_df = clean_df.groupby("track.album.release_decade").size().reset_index(name="count")
    added_df = clean_df.groupby("track.added_at.year").size().reset_index(name="count")

    sorted_artists = (
        clean_df.explode("track.artist_names")["track.artist_names"].value_counts().sort_values(ascending=False)
    )
    top25_artists = sorted_artists.head(25)

    sorted_genres = (
        clean_df.explode("track.first_artist.genres")["track.first_artist.genres"]
        .value_counts()
        .sort_values(ascending=False)
    )
    top25_genres = sorted_genres.head(25)

    return dash.html.Div(
        id="library-plots-div",
        children=[
            dash.dcc.Markdown(children="## Exploring Library"),
            dash.dcc.Graph(
                figure=px.bar(
                    year_df,
                    title="Counts of tracks per album release year",
                    x="track.album.release_year",
                    y="count",
                    text_auto=True,
                ),
            ),
            dash.dcc.Graph(
                figure=px.bar(
                    decade_df,
                    title="Counts of tracks per album release decade",
                    x="track.album.release_decade",
                    y="count",
                    text_auto=True,
                ),
            ),
            dash.dcc.Graph(
                figure=px.bar(
                    added_df,
                    title="Counts of tracks by year when they were saved",
                    x="track.added_at.year",
                    y="count",
                    text_auto=True,
                ),
            ),
            dash.dcc.Graph(
                figure=px.bar(
                    top25_artists,
                    title="Top 25 artists by saved track counts",
                    y=top25_artists.values,
                    x=top25_artists.index,
                    text_auto=True,
                ),
            ),
            dash.dcc.Graph(
                figure=px.bar(
                    top25_genres,
                    title="Top 25 genres by number of tracks (extracted from first artist of track)",
                    y=top25_genres.values,
                    x=top25_genres.index,
                    text_auto=True,
                ),
            ),
            dash.dcc.Graph(id="histogram-subplots"),
        ],
    )


@dash.callback(
    dash.Output("histogram-subplots", "figure"),
    [dash.Input("histogram-subplots", "id")],  # Dummy input to trigger callback
)
def update_histograms(_):
    data = DataSingleton()

    # Create subplots: 1 row x 3 columns
    fig = make_subplots(
        rows=4,
        cols=2,
        column_widths=[0.5, 0.5],
        subplot_titles=(
            "Duration (min)",
            "Danceability",
            "Energy",
            "Loudness",
            "Acousticness",
            "Instrumentalness",
            "Liveness",
            "Valence",
        ),
    )

    # Add histograms to each subplot
    fig.add_trace(
        go.Histogram(x=data.df["track.duration_min"].values, xbins=dict(size=1), name="Duration", texttemplate="%{x}"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Histogram(x=data.df["track.danceability"].values, name="Danceability", texttemplate="%{x}"), row=1, col=2
    )
    fig.add_trace(go.Histogram(x=data.df["track.energy"].values, name="Energy", texttemplate="%{x}"), row=2, col=1)
    fig.add_trace(go.Histogram(x=data.df["track.loudness"].values, name="Loudness", texttemplate="%{x}"), row=2, col=2)
    fig.add_trace(
        go.Histogram(x=data.df["track.acousticness"].values, name="Acousticness", texttemplate="%{x}"), row=3, col=1
    )
    fig.add_trace(
        go.Histogram(x=data.df["track.instrumentalness"].values, name="Instrumentalness", texttemplate="%{x}"),
        row=3,
        col=2,
    )
    fig.add_trace(go.Histogram(x=data.df["track.liveness"].values, name="Liveness", texttemplate="%{x}"), row=4, col=1)
    fig.add_trace(go.Histogram(x=data.df["track.valence"].values, name="Valence", texttemplate="%{x}"), row=4, col=2)

    # Update layout to set title and better presentation
    fig.update_layout(
        title_text="Histograms of audio features",
        height=1600,
        showlegend=False,
    )

    return fig


def layout():
    data = DataSingleton()
    return dash.html.Div(
        [
            get_counts_div(data.df),
            get_library_plots_div(data.df),
        ]
    )
