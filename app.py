import os
from dotenv import load_dotenv

load_dotenv()

import dash
from dash import Dash, html, dcc, Input, Output, State, callback
import flask

from auth import get_auth_url, handle_callback, get_sp_from_session
from spotify import get_top_artists, get_user_profile, aggregate_genres
from components.header import render_header
from components.artist_grid import render_grid
from components.genre_chart import render_genre_chart

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="mccoy",
)
server = app.server
server.secret_key = os.environ["FLASK_SECRET_KEY"]

# --- Flask routes for OAuth ---

@server.route("/login")
def login():
    return flask.redirect(get_auth_url())


@server.route("/callback")
def callback_route():
    code = flask.request.args.get("code")
    if not code:
        return flask.redirect("/")
    token = handle_callback(code)
    flask.session["token"] = token
    return flask.redirect("/")


@server.route("/logout")
def logout():
    flask.session.clear()
    return flask.redirect("/login")


# --- Dash layout ---

TIME_WINDOWS = [
    {"label": "4 Weeks", "value": "short_term"},
    {"label": "6 Months", "value": "medium_term"},
    {"label": "All Time", "value": "long_term"},
]

LOGIN_PAGE = html.Div(
    style={
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
        "justifyContent": "center",
        "height": "100vh",
        "background": "#121212",
    },
    children=[
        html.H1("mccoy", style={"color": "#ffffff", "fontSize": "3rem", "marginBottom": "8px"}),
        html.P(
            "Your Spotify listening habits, visualized.",
            style={"color": "#b3b3b3", "marginBottom": "40px"},
        ),
        html.A(
            "Connect with Spotify",
            href="/login",
            style={
                "background": "#1db954",
                "color": "#000000",
                "padding": "14px 32px",
                "borderRadius": "50px",
                "textDecoration": "none",
                "fontWeight": "700",
                "fontSize": "1rem",
                "letterSpacing": "0.05em",
            },
        ),
    ],
)

app.layout = html.Div(
    id="app-root",
    style={"background": "#121212", "minHeight": "100vh"},
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="artist-data"),
        html.Div(id="page-content"),
    ],
)


# --- Callbacks ---

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def render_page(pathname):
    token = flask.session.get("token")
    if not token:
        return LOGIN_PAGE

    sp = get_sp_from_session(flask.session)
    profile = get_user_profile(sp)

    return html.Div([
        render_header(profile),
        html.Div(
            style={"maxWidth": "1100px", "margin": "0 auto", "padding": "24px 16px"},
            children=[
                # Time window tabs
                dcc.Tabs(
                    id="time-window-tabs",
                    value="short_term",
                    children=[
                        dcc.Tab(label=w["label"], value=w["value"])
                        for w in TIME_WINDOWS
                    ],
                    colors={
                        "border": "#333",
                        "primary": "#1db954",
                        "background": "#121212",
                    },
                ),
                # Content tabs
                dcc.Tabs(
                    id="content-tabs",
                    value="artists",
                    children=[
                        dcc.Tab(label="Artists", value="artists"),
                        dcc.Tab(label="Genres", value="genres"),
                    ],
                    colors={
                        "border": "#333",
                        "primary": "#1db954",
                        "background": "#121212",
                    },
                    style={"marginTop": "8px"},
                ),
                dcc.Loading(
                    id="loading",
                    type="circle",
                    color="#1db954",
                    children=html.Div(id="tab-content", style={"marginTop": "16px"}),
                ),
            ],
        ),
    ])


@app.callback(
    Output("tab-content", "children"),
    Input("time-window-tabs", "value"),
    Input("content-tabs", "value"),
    prevent_initial_call=False,
)
def update_content(time_range, content_tab):
    sp = get_sp_from_session(flask.session)
    if sp is None:
        return html.P("Not authenticated.", style={"color": "#b3b3b3"})

    artists = get_top_artists(sp, time_range)

    if content_tab == "artists":
        return render_grid(artists)

    genres = aggregate_genres(artists)
    return render_genre_chart(genres)


if __name__ == "__main__":
    app.run(debug=True, port=8050)
