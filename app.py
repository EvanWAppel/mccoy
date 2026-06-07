import logging
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from dash import Dash, html, dcc, Input, Output
import flask

import db
from auth import get_auth_url, handle_callback, get_sp_from_session
from spotify import get_top_artists, get_user_profile, aggregate_genres
from components.header import render_header
from components.artist_grid import render_grid
from components.genre_chart import render_genre_chart
from components.trends import render_bump_chart, render_area_chart

logger = logging.getLogger(__name__)

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


# --- Layout helpers ---

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


def _next_snapshot_utc() -> str:
    now = datetime.now(timezone.utc)
    next_run = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return next_run.strftime("%B %d, %Y")


app.layout = html.Div(
    id="app-root",
    style={"background": "#121212", "minHeight": "100vh"},
    children=[
        dcc.Location(id="url", refresh=False),
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
    if sp is None:
        return LOGIN_PAGE

    profile = get_user_profile(sp)

    return html.Div([
        render_header(profile),
        html.Div(
            style={"maxWidth": "1100px", "margin": "0 auto", "padding": "24px 16px"},
            children=[
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
                dcc.Tabs(
                    id="content-tabs",
                    value="artists",
                    children=[
                        dcc.Tab(label="Artists", value="artists", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                        dcc.Tab(label="Genres", value="genres", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                        dcc.Tab(label="Trends", value="trends", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
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

    if content_tab == "trends":
        try:
            snapshots = db.get_snapshots("short_term")
        except Exception as e:
            logger.warning("Could not load snapshots from DB: %s", e)
            snapshots = []

        n_slider = dcc.Slider(
            id="n-artists-slider",
            min=5, max=50, step=5, value=10,
            marks={i: str(i) for i in range(5, 51, 5)},
            tooltip={"placement": "bottom"},
        )

        if len(snapshots) < 2:
            next_date = _next_snapshot_utc()
            empty = html.Div(
                style={"padding": "48px 0", "textAlign": "center"},
                children=[
                    html.P(
                        "Snapshots are taken daily. Come back after your first snapshot to see trends.",
                        style={"color": "#b3b3b3", "marginBottom": "8px"},
                    ),
                    html.P(
                        f"Next snapshot: {next_date}",
                        style={"color": "#1db954", "fontWeight": "600"},
                    ),
                ],
            )
            return html.Div([empty])

        return html.Div([
            html.H3("Artist Rank Movement", style={"color": "#fff", "marginBottom": "4px", "fontWeight": "600"}),
            html.P("Short term (4 weeks) — top artists by rank over time", style={"color": "#b3b3b3", "marginBottom": "8px", "fontSize": "0.85rem"}),
            html.Label("Artists shown:", style={"color": "#b3b3b3", "fontSize": "0.8rem"}),
            html.Div(n_slider, style={"marginBottom": "16px"}),
            html.Div(id="bump-chart-container"),
            html.Hr(style={"borderColor": "#333", "margin": "32px 0"}),
            html.H3("Genre Drift", style={"color": "#fff", "marginBottom": "4px", "fontWeight": "600"}),
            html.P("How your genre distribution has shifted over time", style={"color": "#b3b3b3", "marginBottom": "8px", "fontSize": "0.85rem"}),
            render_area_chart(snapshots),
            dcc.Store(id="trends-snapshots", data=[
                {**s, "captured_at": s["captured_at"].isoformat()} for s in snapshots
            ]),
        ])

    artists = get_top_artists(sp, time_range)

    if content_tab == "artists":
        return render_grid(artists)

    genres = aggregate_genres(artists)
    return render_genre_chart(genres)


@app.callback(
    Output("bump-chart-container", "children"),
    Input("n-artists-slider", "value"),
    prevent_initial_call=True,
)
def update_bump_chart(n):
    try:
        snapshots = db.get_snapshots("short_term")
    except Exception:
        snapshots = []
    # Re-parse datetimes if needed (already datetime objects from db)
    return render_bump_chart(snapshots, n=n or 10)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
