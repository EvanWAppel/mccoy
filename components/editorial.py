"""The listening journal's shared editorial chrome."""

from collections import Counter
from typing import TypedDict

from dash import html

AriaHidden = TypedDict("AriaHidden", {"aria-hidden": str})


def wordmark():
    return html.A(
        [html.Span("m", className="brand-mark"), "mccoy"],
        href="/",
        className="wordmark",
        title="McCoy home",
    )


def listening_intro():
    return html.Section(
        className="listening-intro",
        children=[
            html.Div([
                html.P(
                    "A PERSONAL LISTENING JOURNAL",
                    className="eyebrow",
                ),
                html.H1(["Good music.", html.Br(), html.Em("On repeat.")]),
                html.P(
                    "The artists you come back to. The records you "
                    "haven’t found yet. A closer look at a life in music.",
                    className="intro-description",
                ),
                html.A(
                    ["Explore the collection", html.Span("↘")],
                    href="#collection",
                    className="intro-link",
                ),
            ]),
            html.Div(
                className="record-sleeve",
                **AriaHidden({"aria-hidden": "true"}),
                children=[
                    html.Div(
                        "McCOY / SELECTED ROTATION", className="sleeve-top"
                    ),
                    html.Div(
                        className="vinyl",
                        children=html.Div(
                            [html.Span("m"), html.Small("SIDE A · 33⅓ RPM")],
                            className="vinyl-label",
                        ),
                    ),
                    html.Div(
                        [html.Span("KEEP LISTENING."), html.Span("VOL. 01")],
                        className="sleeve-bottom",
                    ),
                ],
            ),
        ],
    )


def collection_heading():
    return html.Div(
        id="collection",
        className="collection-heading",
        children=[
            html.Div([
                html.P("01 / THE LISTENING ROOM", className="eyebrow"),
                html.H2("In rotation"),
            ]),
            html.P("Familiar favorites. New obsessions."),
        ],
    )


def listening_summary(artists):
    genres = Counter(
        genre for artist in artists for genre in artist.get("genres", [])
    )
    leading = genres.most_common(1)[0][0] if genres else "Unclassified"
    metrics = [
        (f"{len(artists):02d}", "Artists in rotation"),
        (f"{len(genres):02d}", "Genres in the mix"),
        (leading, "Leading the sound"),
    ]
    return html.Div(
        className="listening-summary",
        children=[
            html.Div([html.Strong(value), html.Span(label)])
            for value, label in metrics
        ],
    )


def journal_footer():
    return html.Footer(
        className="journal-footer",
        children=[
            html.Span("mccoy / A life in music."),
            html.Span("Built by Evan Appel · Powered by Spotify"),
        ],
    )
