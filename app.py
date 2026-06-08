import logging
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from dash import Dash, html, dcc, Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate
import flask

import db
from auth import get_auth_url, handle_callback, get_sp_from_session
from spotify import (
    get_top_artists,
    get_user_profile,
    get_user_playlists,
    search_playlists,
    get_playlist_tracks,
    add_track_to_playlist,
)
from components.header import render_header
from components.artist_grid import render_grid
from components.trends import render_bump_chart
from components.rustle import (
    mode_switcher,
    target_picker,
    search_bar,
    playlist_card,
    track_card,
    end_of_queue_card,
)

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
                mode_switcher(),
                html.Div(
                    id="stats-content",
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
                html.Div(id="rustle-content", style={"display": "none"}),
                dcc.Store(id="rustle-user-id", data=profile.get("user_id", "")),
                dcc.Store(id="rustle-target", data=None),
                dcc.Store(id="rustle-view", data="picker"),
                dcc.Store(id="rustle-playlist-queue", data=[]),
                dcc.Store(id="rustle-playlist-index", data=0),
                dcc.Store(id="rustle-track-queue", data=[]),
                dcc.Store(id="rustle-track-index", data=0),
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
        ])

    artists = get_top_artists(sp, time_range)
    return render_grid(artists)


@app.callback(
    Output("bump-chart-container", "children"),
    Input("n-artists-slider", "value"),
    prevent_initial_call=False,
)
def update_bump_chart(n):
    try:
        snapshots = db.get_snapshots("short_term")
    except Exception:
        snapshots = []
    # Re-parse datetimes if needed (already datetime objects from db)
    return render_bump_chart(snapshots, n=n or 10)


# --- Rustle callbacks ---


@app.callback(
    Output("stats-content", "style"),
    Output("rustle-content", "style"),
    Input("mode-tabs", "value"),
)
def toggle_mode(mode):
    if mode == "rustle":
        return {"display": "none"}, {"display": "block"}
    return {"display": "block"}, {"display": "none"}


def _rustle_search_view(queue, idx):
    children = [search_bar()]
    if not queue:
        children.append(
            html.P(
                "Type a search to flip through playlists.",
                style={"color": "#b3b3b3", "marginTop": "16px"},
            )
        )
        return html.Div(children)
    idx = max(0, min(idx, len(queue) - 1))
    children.append(playlist_card(queue[idx]))
    children.append(
        html.Div(
            style={"marginTop": "12px", "display": "flex", "gap": "8px"},
            children=[
                html.Button("← Prev", id="rustle-pl-prev", n_clicks=0),
                html.Button("Enter →", id="rustle-pl-enter", n_clicks=0),
                html.Button("Next", id="rustle-pl-next", n_clicks=0),
            ],
        )
    )
    children.append(
        html.P(
            f"{idx + 1} of {len(queue)}",
            style={"color": "#b3b3b3", "fontSize": "0.8rem"},
        )
    )
    return html.Div(children)


def _rustle_track_view(queue, idx):
    if not queue:
        return html.Div([
            end_of_queue_card(
                "This playlist has no playable tracks. "
                "Press Back to pick another."
            ),
            html.Button("↩ Back", id="rustle-tr-back", n_clicks=0),
        ])
    if idx >= len(queue):
        return html.Div([
            end_of_queue_card(
                "You've flipped through every track in this playlist."
            ),
            html.Button("↩ Back", id="rustle-tr-back", n_clicks=0),
        ])
    children = [track_card(queue[idx])]
    children.append(
        html.Div(
            style={"marginTop": "12px", "display": "flex", "gap": "8px"},
            children=[
                html.Button("← Prev", id="rustle-tr-prev", n_clicks=0),
                html.Button("+ Add", id="rustle-tr-add", n_clicks=0),
                html.Button("Next", id="rustle-tr-next", n_clicks=0),
                html.Button("↩ Back", id="rustle-tr-back", n_clicks=0),
            ],
        )
    )
    children.append(
        html.P(
            f"{idx + 1} of {len(queue)}",
            style={"color": "#b3b3b3", "fontSize": "0.8rem"},
        )
    )
    return html.Div(children)


@app.callback(
    Output("rustle-content", "children"),
    Input("mode-tabs", "value"),
    Input("rustle-view", "data"),
    Input("rustle-target", "data"),
    Input("rustle-playlist-queue", "data"),
    Input("rustle-playlist-index", "data"),
    Input("rustle-track-queue", "data"),
    Input("rustle-track-index", "data"),
)
def render_rustle_content(
    mode, view, target, pl_queue, pl_idx, tr_queue, tr_idx
):
    if mode != "rustle":
        return None
    sp = get_sp_from_session(flask.session)
    if sp is None:
        return html.P("Not authenticated.", style={"color": "#b3b3b3"})
    if not target:
        try:
            playlists = get_user_playlists(sp)
        except Exception as e:
            logger.warning("Could not load user playlists: %s", e)
            playlists = []
        logger.info("Rustle target picker: %d playlists", len(playlists))
        return target_picker(playlists)
    if view == "track":
        return _rustle_track_view(tr_queue, tr_idx)
    return _rustle_search_view(pl_queue, pl_idx)


@app.callback(
    Output("rustle-target", "data"),
    Output("rustle-view", "data", allow_duplicate=True),
    Input(
        {"type": "rustle-target-pick", "playlist_id": ALL},
        "n_clicks",
    ),
    prevent_initial_call=True,
)
def select_target(n_clicks_list):
    if not n_clicks_list or not any(n_clicks_list):
        raise PreventUpdate
    trigger = ctx.triggered_id
    if not trigger or "playlist_id" not in trigger:
        raise PreventUpdate
    return trigger["playlist_id"], "search"


@app.callback(
    Output("rustle-playlist-queue", "data"),
    Output("rustle-playlist-index", "data", allow_duplicate=True),
    Input("rustle-search", "value"),
    prevent_initial_call=True,
)
def run_search(query):
    if not query or not query.strip():
        return [], 0
    sp = get_sp_from_session(flask.session)
    if sp is None:
        raise PreventUpdate
    try:
        results = search_playlists(sp, query.strip(), limit=20)
    except Exception as e:
        logger.warning("search_playlists failed: %s", e)
        results = []
    return results, 0


@app.callback(
    Output("rustle-playlist-index", "data", allow_duplicate=True),
    Input("rustle-pl-prev", "n_clicks"),
    Input("rustle-pl-next", "n_clicks"),
    State("rustle-playlist-index", "data"),
    State("rustle-playlist-queue", "data"),
    prevent_initial_call=True,
)
def nav_playlist(prev_n, next_n, idx, queue):
    if not queue:
        raise PreventUpdate
    trigger = ctx.triggered_id
    if trigger == "rustle-pl-prev":
        return max(0, idx - 1)
    if trigger == "rustle-pl-next":
        return min(len(queue) - 1, idx + 1)
    raise PreventUpdate


@app.callback(
    Output("rustle-track-queue", "data"),
    Output("rustle-track-index", "data", allow_duplicate=True),
    Output("rustle-view", "data", allow_duplicate=True),
    Input("rustle-pl-enter", "n_clicks"),
    State("rustle-playlist-queue", "data"),
    State("rustle-playlist-index", "data"),
    prevent_initial_call=True,
)
def enter_playlist(n_clicks, queue, idx):
    if not n_clicks or not queue:
        raise PreventUpdate
    playlist = queue[idx]
    sp = get_sp_from_session(flask.session)
    if sp is None:
        raise PreventUpdate
    try:
        tracks = get_playlist_tracks(sp, playlist["id"])
    except Exception as e:
        logger.warning("get_playlist_tracks failed: %s", e)
        tracks = []
    return tracks, 0, "track"


@app.callback(
    Output("rustle-track-index", "data", allow_duplicate=True),
    Input("rustle-tr-prev", "n_clicks"),
    Input("rustle-tr-next", "n_clicks"),
    State("rustle-track-index", "data"),
    State("rustle-track-queue", "data"),
    prevent_initial_call=True,
)
def nav_track(prev_n, next_n, idx, queue):
    if not queue:
        raise PreventUpdate
    trigger = ctx.triggered_id
    if trigger == "rustle-tr-prev":
        return max(0, idx - 1)
    if trigger == "rustle-tr-next":
        return min(len(queue), idx + 1)
    raise PreventUpdate


@app.callback(
    Output("rustle-track-index", "data", allow_duplicate=True),
    Input("rustle-tr-add", "n_clicks"),
    State("rustle-track-queue", "data"),
    State("rustle-track-index", "data"),
    State("rustle-target", "data"),
    prevent_initial_call=True,
)
def add_track(n_clicks, queue, idx, target):
    if not n_clicks or not queue or not target:
        raise PreventUpdate
    if idx >= len(queue):
        raise PreventUpdate
    track = queue[idx]
    sp = get_sp_from_session(flask.session)
    if sp is None:
        raise PreventUpdate
    try:
        add_track_to_playlist(sp, target, track["uri"])
        logger.info("Added %s to %s", track["uri"], target)
    except Exception as e:
        logger.warning("add_track_to_playlist failed: %s", e)
    # Advance to next track
    return min(len(queue), idx + 1)


@app.callback(
    Output("rustle-view", "data", allow_duplicate=True),
    Input("rustle-tr-back", "n_clicks"),
    prevent_initial_call=True,
)
def back_to_search(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return "search"


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
