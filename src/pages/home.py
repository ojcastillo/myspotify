import dash
import plotly.express as px

from common.data import DataSingleton


dash.register_page(__name__, path="/")


def get_counts_div(df):
    return dash.html.Div(
        id="counts-div",
        children=[
            dash.dcc.Markdown(
                children=f"""
                ## General Stats
                - **Total amount of tracks**: {df.shape[0]}
            """
            ),
        ],
    )


def get_library_plots_div(df):
    clean_df = df[df["track.album.release_decade"] > 0]
    decade_df = clean_df.groupby("track.album.release_decade").size().reset_index(name="count")

    sorted_artists = clean_df.explode("track.artists")["track.artists"].value_counts().sort_values(ascending=False)
    top25_artists = sorted_artists.head(25)

    return dash.html.Div(
        id="library-plots-div",
        children=[
            dash.dcc.Markdown(children="## Exploring Library"),
            dash.dcc.Graph(
                figure=px.bar(
                    decade_df,
                    title="Counts of tracks per decade",
                    x="track.album.release_decade",
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
        ],
    )


def layout():
    data = DataSingleton()
    return dash.html.Div(
        [
            get_counts_div(data.df),
            get_library_plots_div(data.df),
        ]
    )
