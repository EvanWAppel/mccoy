from dash import html, dcc


def mode_switcher():
    return dcc.Tabs(
        id="mode-tabs",
        value="stats",
        className="mode-tabs",
        children=[
            dcc.Tab(
                label="Stats",
                value="stats",
                className="mode-tab",
                selected_className="mode-tab--selected",
            ),
            dcc.Tab(
                label="Rustle",
                value="rustle",
                className="mode-tab",
                selected_className="mode-tab--selected",
            ),
        ],
    )


def target_picker(playlists):
    items = [
        html.Button(
            p["name"],
            id={"type": "rustle-target-pick", "playlist_id": p["id"]},
            n_clicks=0,
            className="rustle-picker__btn",
        )
        for p in playlists
    ]
    items.append(
        html.Button(
            "Create new…",
            id="rustle-target-create-new",
            n_clicks=0,
            className="rustle-picker__btn rustle-picker__btn--create",
        )
    )
    return html.Div(
        className="rustle-picker",
        children=[
            html.H3("Rustle into…", className="rustle-picker__title"),
            html.Div(items, className="rustle-picker__list"),
        ],
    )


def create_playlist_form():
    # CC-02: replaces the picker list while naming a new playlist
    return html.Div(
        className="rustle-picker",
        children=[
            html.H3(
                "Name your new playlist",
                className="rustle-picker__title",
            ),
            dcc.Input(
                id="rustle-new-name",
                type="text",
                placeholder="Playlist name…",
                debounce=False,
                className="rustle-search__input",
            ),
            html.Div(
                className="rustle-picker__actions",
                children=[
                    html.Button(
                        "Create",
                        id="rustle-create-btn",
                        n_clicks=0,
                        className=(
                            "rustle-picker__btn "
                            "rustle-picker__btn--confirm"
                        ),
                    ),
                    html.Button(
                        "Cancel",
                        id="rustle-create-cancel",
                        n_clicks=0,
                        className="rustle-picker__btn",
                    ),
                ],
            ),
        ],
    )


def search_bar(value=""):
    return html.Div(
        className="rustle-search",
        children=[
            dcc.Input(
                id="rustle-search",
                type="search",
                placeholder="Search playlists…",
                value=value,
                debounce=True,
                className="rustle-search__input",
            ),
        ],
    )


def recents_chips(queries):
    if not queries:
        return html.Div(className="rustle-recents rustle-recents--empty")
    chips = [
        html.Button(
            q,
            id={"type": "rustle-recent-chip", "query": q},
            n_clicks=0,
            className="rustle-recents__chip",
        )
        for q in queries[:5]
    ]
    chips.append(
        html.Button(
            "Clear",
            id="rustle-recents-clear",
            n_clicks=0,
            className="rustle-recents__clear",
        )
    )
    return html.Div(chips, className="rustle-recents")


# AA-05 / DD-02 / DD-03: canonical end-of-queue copy, kept here so
# app.py and the tests share one source of truth.
ALBUM_END_MESSAGE = "End of the record. Swipe down to keep digging."
SEARCH_END_MESSAGE = (
    "That's everything for this search. Swipe down to start over."
)
TRACK_END_MESSAGE = (
    "You've flipped through every track in this playlist. "
    "Swipe down to try another."
)


def _card_art(image_url, drill=False):
    # EE-03: grey placeholder square when art is missing.
    # AA-01: drill=True marks the art so assets/rustle.js can detect a
    # tap on it and emit the "tap-art" album-drill gesture.
    extra = {"data-rustle-art": "true"} if drill else {}
    if image_url:
        return html.Img(
            src=image_url, className="rustle-card__art", **extra
        )
    return html.Div(
        className="rustle-card__art rustle-card__art--placeholder",
        **extra,
    )


def playlist_card(playlist):
    return html.Div(
        className="rustle-card rustle-card--playlist",
        children=[
            _card_art(playlist.get("image_url")),
            html.Div(
                playlist["name"],
                className="rustle-card__title",
            ),
        ],
    )


def track_card(track, already_added: bool = False):
    children = [
        # AA-01: track art is tap-drillable into its parent album
        _card_art(track.get("album_image_url"), drill=True),
        html.Div(track["name"], className="rustle-card__title"),
    ]
    if already_added:
        children.append(
            html.Div("Already added", className="rustle-card__badge")
        )
    if not track.get("preview_url"):
        children.append(
            html.Div(
                "No preview available",
                className="rustle-card__no-preview",
            )
        )
    return html.Div(
        className="rustle-card rustle-card--track",
        children=children,
    )


def card_stack(cards):
    # V-02: top card front and centered, up to three more peeking
    # behind it. Depth styling lives on .rustle-stack__card--{i}.
    slots = [
        html.Div(
            card,
            className=f"rustle-stack__card rustle-stack__card--{i}",
        )
        for i, card in enumerate(cards[:4])
    ]
    return html.Div(slots, className="rustle-stack")


def no_results_state(recents=None):
    # EE-01: zero search results, with recents below to recover
    children = [
        html.P(
            "No playlists found. Try a different search.",
            className="rustle-no-results",
        )
    ]
    if recents:
        children.append(recents_chips(recents))
    return html.Div(children, className="rustle-empty")


def error_toast(message: str, kind: str = "error"):
    # EE-05 / EE-06: non-blocking error / offline notice
    return html.Div(
        message,
        className=f"rustle-toast rustle-toast--{kind}",
    )


def end_of_queue_card(message: str):
    return html.Div(
        className="rustle-end-of-queue",
        children=[
            html.P(message, className="rustle-end-of-queue__msg"),
        ],
    )


def tap_to_start_overlay():
    # X-05: one-time overlay whose tap primes the <audio> element
    # inside a user gesture (iOS audio unlock).
    return html.Div(
        html.Button(
            "Tap to start",
            id="rustle-audio-unlock",
            n_clicks=0,
            className="rustle-unlock__btn",
        ),
        className="rustle-unlock",
    )


def added_stamp_overlay():
    return html.Div("Added", className="added-stamp")


def add_counter_chip(n: int):
    # Z-09: hidden until the first add of the session
    if not n or n <= 0:
        return html.Div(
            className="rustle-counter-chip rustle-counter-chip--hidden"
        )
    return html.Div(f"+{n} added", className="rustle-counter-chip")
