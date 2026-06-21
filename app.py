import logging
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from dash import (
    Dash, html, dcc, Input, Output, State, ALL, ctx, no_update,
    ClientsideFunction,
)
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
    get_playlist_track_uris,
    create_playlist,
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
    card_stack,
    tap_to_start_overlay,
    add_counter_chip,
    create_playlist_form,
    recents_chips,
    no_results_state,
    error_toast,
)
from spotipy import SpotifyException

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
                html.Div(
                    id="rustle-wrap",
                    style={"display": "none"},
                    children=dcc.Loading(
                        type="circle",
                        color="#1db954",
                        children=html.Div(id="rustle-content"),
                    ),
                ),
                dcc.Store(id="rustle-user-id", data=profile.get("user_id", "")),
                dcc.Store(id="rustle-target", data=None),
                dcc.Store(id="rustle-view", data="picker"),
                dcc.Store(id="rustle-playlist-queue", data=[]),
                dcc.Store(id="rustle-playlist-index", data=0),
                dcc.Store(id="rustle-track-queue", data=[]),
                dcc.Store(id="rustle-track-index", data=0),
                dcc.Store(id="rustle-gesture", data=None),
                dcc.Store(id="rustle-audio-unlocked", data=False),
                dcc.Store(id="rustle-audio-sink", data=None),
                dcc.Store(id="rustle-target-uris", data=[]),
                dcc.Store(id="rustle-add-count", data=0),
                dcc.Store(id="rustle-picker-mode", data="list"),
                dcc.Store(id="rustle-recents", data=[]),
                dcc.Store(id="rustle-query", data=""),
                dcc.Store(id="rustle-error", data=None),
                dcc.Store(id="rustle-auth-sink", data=None),
                html.Audio(id="rustle-audio", preload="auto"),
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
    Output("rustle-wrap", "style"),
    Input("mode-tabs", "value"),
)
def toggle_mode(mode):
    if mode == "rustle":
        return {"display": "none"}, {"display": "block"}
    return {"display": "block"}, {"display": "none"}


GESTURE_HINT = (
    "Swipe or drag the card — or use arrow keys. "
    "Up commits, down goes back."
)


def _gesture_area(children):
    # W-01: assets/rustle.js attaches Pointer Events to this region
    return html.Div(
        children,
        **{"data-rustle-card-area": "true"},
    )


def _rustle_search_view(queue, idx, recents=None, query=""):
    children = [search_bar(value=query or "")]
    if not queue:
        if query and query.strip():
            # EE-01: searched but nothing came back
            children.append(no_results_state(recents))
        else:
            # BB-02: idle search bar — offer recent searches
            children.append(
                html.P(
                    "Type a search to flip through playlists.",
                    style={"color": "#b3b3b3", "marginTop": "16px"},
                )
            )
            if recents:
                children.append(recents_chips(recents))
        return html.Div(children)
    idx = max(0, min(idx, len(queue) - 1))
    children.append(
        _gesture_area(
            card_stack([playlist_card(p) for p in queue[idx : idx + 4]])
        )
    )
    children.append(
        html.P(
            f"{idx + 1} of {len(queue)} — {GESTURE_HINT}",
            style={"color": "#b3b3b3", "fontSize": "0.8rem"},
        )
    )
    return html.Div(children)


def _rustle_track_view(queue, idx, audio_unlocked=False, target_uris=None):
    added = set(target_uris or [])
    if not queue:
        return _gesture_area([
            end_of_queue_card(
                "This playlist has no playable tracks. "
                "Swipe down to pick another."
            ),
        ])
    if idx >= len(queue):
        return _gesture_area([
            end_of_queue_card(
                "You've flipped through every track in this playlist. "
                "Swipe down to try another."
            ),
        ])
    area = [
        card_stack([
            track_card(t, already_added=t["uri"] in added)
            for t in queue[idx : idx + 4]
        ])
    ]
    if not audio_unlocked:
        area.append(tap_to_start_overlay())
    children = [_gesture_area(area)]
    children.append(
        html.P(
            f"{idx + 1} of {len(queue)} — {GESTURE_HINT}",
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
    Input("rustle-audio-unlocked", "data"),
    Input("rustle-target-uris", "data"),
    Input("rustle-add-count", "data"),
    Input("rustle-picker-mode", "data"),
    Input("rustle-recents", "data"),
    Input("rustle-query", "data"),
    Input("rustle-error", "data"),
)
def render_rustle_content(
    mode, view, target, pl_queue, pl_idx, tr_queue, tr_idx,
    audio_unlocked, target_uris, add_count, picker_mode,
    recents, query, error,
):
    if mode != "rustle":
        return None
    sp = get_sp_from_session(flask.session)
    if sp is None:
        return html.P("Not authenticated.", style={"color": "#b3b3b3"})
    if not target:
        if picker_mode == "create":
            return create_playlist_form()
        try:
            playlists = get_user_playlists(sp)
        except Exception as e:
            logger.warning("Could not load user playlists: %s", e)
            playlists = []
        logger.info("Rustle target picker: %d playlists", len(playlists))
        return target_picker(playlists)
    if view == "track":
        body = _rustle_track_view(
            tr_queue, tr_idx, audio_unlocked, target_uris
        )
    else:
        body = _rustle_search_view(pl_queue, pl_idx, recents, query)
    # Z-06 / Z-07: session add counter, fixed top-right
    overlays = [add_counter_chip(add_count or 0)]
    if error:
        # EE-05 / EE-06: non-blocking toast (auth errors redirect
        # clientside, so don't double-render them here)
        if error.get("kind") != "auth":
            overlays.append(
                error_toast(error.get("msg", ""), error.get("kind"))
            )
    return html.Div([body, *overlays])


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
    Output("rustle-query", "data", allow_duplicate=True),
    Output("rustle-recents", "data", allow_duplicate=True),
    Output("rustle-error", "data", allow_duplicate=True),
    Input("rustle-search", "value"),
    State("rustle-user-id", "data"),
    prevent_initial_call=True,
)
def run_search(query, user_id):
    if not query or not query.strip():
        return [], 0, "", no_update, None
    q = query.strip()
    sp = get_sp_from_session(flask.session)
    if sp is None:
        raise PreventUpdate
    error = None
    try:
        results = search_playlists(sp, q)
    except Exception as e:
        kind = _classify_error(e)
        logger.warning("search_playlists failed (%s): %s", kind, e)
        results = []
        error = _error_payload(kind)
    # BB-03: persist the query and refresh the recents list
    new_recents = no_update
    if user_id:
        try:
            db.save_recent_search(user_id, q)
            new_recents = db.get_recent_searches(user_id)
        except Exception as e:
            logger.warning("save_recent_search failed: %s", e)
    return results, 0, q, new_recents, error


# BB-04: load recent searches when entering Rustle mode
@app.callback(
    Output("rustle-recents", "data", allow_duplicate=True),
    Input("mode-tabs", "value"),
    State("rustle-user-id", "data"),
    prevent_initial_call=True,
)
def load_recents(mode, user_id):
    if mode != "rustle" or not user_id:
        raise PreventUpdate
    try:
        return db.get_recent_searches(user_id)
    except Exception as e:
        logger.warning("get_recent_searches failed: %s", e)
        raise PreventUpdate


# BB-05: clicking a recent chip refills the search box, refiring search
@app.callback(
    Output("rustle-search", "value"),
    Input({"type": "rustle-recent-chip", "query": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def click_recent_chip(n_list):
    if not n_list or not any(n_list):
        raise PreventUpdate
    trigger = ctx.triggered_id
    if not trigger or "query" not in trigger:
        raise PreventUpdate
    return trigger["query"]


# BB-06: clear all recent searches for this user
@app.callback(
    Output("rustle-recents", "data", allow_duplicate=True),
    Input("rustle-recents-clear", "n_clicks"),
    State("rustle-user-id", "data"),
    prevent_initial_call=True,
)
def clear_recents(n_clicks, user_id):
    if not n_clicks:
        raise PreventUpdate
    if user_id:
        try:
            db.clear_recent_searches(user_id)
        except Exception as e:
            logger.warning("clear_recent_searches failed: %s", e)
    return []


# W-06 / W-07: one dispatcher replaces the Group U temp buttons.
# Search view: L/R = index ±1, Up = enter playlist, Down = clear
# search. Track view: L/R = index ±1, Up = add track, Down = back
# to the playlist queue.


# EE-04/05/06: classify Spotify-side failures into toast/redirect kinds
ERROR_MESSAGES = {
    "auth": "Session expired. Reconnecting…",
    "missing": "That playlist no longer exists. Pick another.",
    "offline": "Offline — retrying…",
    "error": "Something went wrong. Try again.",
}


def _is_network_error(e) -> bool:
    name = type(e).__name__
    return "Connection" in name or "Timeout" in name


def _classify_error(e) -> str:
    if isinstance(e, SpotifyException):
        status = getattr(e, "http_status", None)
        if status == 401:
            return "auth"
        if status == 404:
            return "missing"
        return "error"
    if _is_network_error(e):
        return "offline"
    return "error"


def _error_payload(kind: str) -> dict:
    return {"kind": kind, "msg": ERROR_MESSAGES.get(kind, ERROR_MESSAGES["error"])}


def _enter_playlist(sp, queue, idx):
    playlist = queue[idx]
    try:
        tracks = get_playlist_tracks(sp, playlist["id"])
        return {"tracks": tracks, "error": None}
    except Exception as e:
        kind = _classify_error(e)
        logger.warning("get_playlist_tracks failed (%s): %s", kind, e)
        return {"tracks": [], "error": _error_payload(kind)}


def _fetch_target_uris(sp, target):
    # Z-01: dedupe set against the target playlist
    try:
        return sorted(get_playlist_track_uris(sp, target))
    except Exception as e:
        logger.warning("get_playlist_track_uris failed: %s", e)
        return []


def _add_current_track(sp, queue, idx, target) -> str:
    if idx >= len(queue) or not target:
        return "error"
    track = queue[idx]
    try:
        add_track_to_playlist(sp, target, track["uri"])
        logger.info("Added %s to %s", track["uri"], target)
        return "ok"
    except Exception as e:
        kind = _classify_error(e)
        logger.warning("add_track_to_playlist failed (%s): %s", kind, e)
        return kind


@app.callback(
    Output("rustle-playlist-queue", "data", allow_duplicate=True),
    Output("rustle-playlist-index", "data", allow_duplicate=True),
    Output("rustle-track-queue", "data"),
    Output("rustle-track-index", "data", allow_duplicate=True),
    Output("rustle-view", "data", allow_duplicate=True),
    Output("rustle-target-uris", "data"),
    Output("rustle-add-count", "data"),
    Output("rustle-target", "data", allow_duplicate=True),
    Output("rustle-error", "data", allow_duplicate=True),
    Output("rustle-query", "data", allow_duplicate=True),
    Input("rustle-gesture", "data"),
    State("rustle-view", "data"),
    State("rustle-target", "data"),
    State("rustle-playlist-queue", "data"),
    State("rustle-playlist-index", "data"),
    State("rustle-track-queue", "data"),
    State("rustle-track-index", "data"),
    State("rustle-target-uris", "data"),
    State("rustle-add-count", "data"),
    prevent_initial_call=True,
)
def handle_gesture(
    gesture, view, target, pl_queue, pl_idx, tr_queue, tr_idx,
    target_uris, add_count,
):
    if not gesture or not gesture.get("direction"):
        raise PreventUpdate
    direction = gesture["direction"]
    sp = get_sp_from_session(flask.session)
    if sp is None:
        raise PreventUpdate

    out = {
        "pl_queue": no_update, "pl_idx": no_update,
        "tr_queue": no_update, "tr_idx": no_update,
        "view": no_update, "uris": no_update, "count": no_update,
        "target": no_update, "error": no_update, "query": no_update,
    }

    def ret():
        return (
            out["pl_queue"], out["pl_idx"], out["tr_queue"],
            out["tr_idx"], out["view"], out["uris"], out["count"],
            out["target"], out["error"], out["query"],
        )

    if view == "track":
        if direction == "left":
            out["tr_idx"] = max(0, tr_idx - 1)
            return ret()
        if direction == "right":
            if not tr_queue:
                raise PreventUpdate
            # len(queue) is the end-of-queue card position
            out["tr_idx"] = min(len(tr_queue), tr_idx + 1)
            return ret()
        if direction == "up":
            if not tr_queue or tr_idx >= len(tr_queue):
                raise PreventUpdate
            uri = tr_queue[tr_idx]["uri"]
            if uri in set(target_uris or []):
                # Z-03: already in the target — no-op (the shake
                # animation happens clientside)
                raise PreventUpdate
            status = _add_current_track(sp, tr_queue, tr_idx, target)
            if status == "ok":
                # Z-07 / Z-08: bump the counter and grow the dedupe
                # set so later cards see this add
                out["uris"] = (target_uris or []) + [uri]
                out["count"] = (add_count or 0) + 1
                out["tr_idx"] = min(len(tr_queue), tr_idx + 1)
                out["error"] = None  # clear any prior toast
            elif status == "missing":
                # EE-05: target was deleted in Spotify mid-session
                out["target"] = None
                out["view"] = "search"
                out["error"] = _error_payload("missing")
            else:
                # auth / offline / generic — surface, keep the card
                out["error"] = _error_payload(status)
            return ret()
        if direction == "down":
            out["view"] = "search"
            return ret()
        raise PreventUpdate

    # search (playlist queue) view
    if direction == "left":
        out["pl_idx"] = max(0, pl_idx - 1)
        return ret()
    if direction == "right":
        if not pl_queue:
            raise PreventUpdate
        out["pl_idx"] = min(len(pl_queue) - 1, pl_idx + 1)
        return ret()
    if direction == "up":
        if not pl_queue:
            raise PreventUpdate
        result = _enter_playlist(sp, pl_queue, pl_idx)
        if result["error"]:
            out["error"] = result["error"]
            return ret()
        out["tr_queue"] = result["tracks"]
        out["tr_idx"] = 0
        out["view"] = "track"
        out["uris"] = _fetch_target_uris(sp, target)
        out["error"] = None  # clear any prior toast
        return ret()
    if direction == "down":
        # W-07: clear the search results, back to recents
        out["pl_queue"] = []
        out["pl_idx"] = 0
        out["query"] = ""
        return ret()
    raise PreventUpdate
    raise PreventUpdate


# CC-02: toggle the picker between list and create-input modes
@app.callback(
    Output("rustle-picker-mode", "data", allow_duplicate=True),
    Input("rustle-target-create-new", "n_clicks"),
    Input("rustle-create-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_picker_mode(create_n, cancel_n):
    trigger = ctx.triggered_id
    if trigger == "rustle-target-create-new" and create_n:
        return "create"
    if trigger == "rustle-create-cancel" and cancel_n:
        return "list"
    raise PreventUpdate


# CC-03: create the playlist and make it the Rustle target
@app.callback(
    Output("rustle-target", "data", allow_duplicate=True),
    Output("rustle-view", "data", allow_duplicate=True),
    Output("rustle-picker-mode", "data", allow_duplicate=True),
    Input("rustle-create-btn", "n_clicks"),
    State("rustle-new-name", "value"),
    State("rustle-user-id", "data"),
    prevent_initial_call=True,
)
def create_new_target(n_clicks, name, user_id):
    if not n_clicks or not name or not name.strip():
        raise PreventUpdate
    sp = get_sp_from_session(flask.session)
    if sp is None:
        raise PreventUpdate
    try:
        playlist_id = create_playlist(sp, user_id, name.strip())
        logger.info("Created playlist %r (%s)", name.strip(), playlist_id)
    except Exception as e:
        logger.warning("create_playlist failed: %s", e)
        raise PreventUpdate
    return playlist_id, "search", "list"


# X-02..X-04: play/fade the preview clientside on card change
app.clientside_callback(
    ClientsideFunction(namespace="rustle", function_name="playPreview"),
    Output("rustle-audio-sink", "data"),
    Input("rustle-track-index", "data"),
    Input("rustle-track-queue", "data"),
    Input("rustle-view", "data"),
    Input("rustle-audio-unlocked", "data"),
)

# X-05 / X-06: prime the audio element inside the tap gesture
app.clientside_callback(
    ClientsideFunction(namespace="rustle", function_name="unlockAudio"),
    Output("rustle-audio-unlocked", "data"),
    Input("rustle-audio-unlock", "n_clicks"),
    prevent_initial_call=True,
)

# EE-04: a 401 from any Rustle-side call → full re-auth at /login
app.clientside_callback(
    """
    function(error) {
        if (error && error.kind === 'auth') {
            window.location.href = '/login';
            return 'redirecting';
        }
        return '';
    }
    """,
    Output("rustle-auth-sink", "data"),
    Input("rustle-error", "data"),
    prevent_initial_call=True,
)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
