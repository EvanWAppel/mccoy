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

TAB_STYLE = {
    "backgroundColor": "#121212",
    "color": "#b3b3b3",
    "border": "none",
    "borderBottom": "2px solid transparent",
    "padding": "10px 20px",
    "fontWeight": "600",
    "fontSize": "0.875rem",
    "letterSpacing": "0.04em",
    "textTransform": "uppercase",
}

TAB_SELECTED_STYLE = {
    **TAB_STYLE,
    "color": "#ffffff",
    "borderBottom": "2px solid #1db954",
    "backgroundColor": "#121212",
}

LOGIN_PAGE = html.Div(
    className="login-page",
    children=[
        html.H1("mccoy", className="login-page__title"),
        html.P("Your Spotify listening habits, visualized.", className="login-page__subtitle"),
        html.A("Connect with Spotify", href="/login", className="login-page__btn"),
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
                        dcc.Tab(
                            label=w["label"],
                            value=w["value"],
                            style=TAB_STYLE,
                            selected_style=TAB_SELECTED_STYLE,
                        )
                        for w in TIME_WINDOWS
                    ],
                ),
                # Content tabs
                dcc.Tabs(
                    id="content-tabs",
                    value="artists",
                    children=[
                        dcc.Tab(label="Artists", value="artists", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                        dcc.Tab(label="Genres", value="genres", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    ],
                    style={"marginTop": "4px"},
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
    app.run(debug=True, host="127.0.0.1", port=8050)
