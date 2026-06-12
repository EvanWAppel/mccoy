from dash import html, dcc


def mode_switcher():
    return dcc.Tabs(
        id="mode-tabs",
        value="stats",
        children=[
            dcc.Tab(label="Stats", value="stats"),
            dcc.Tab(label="Rustle", value="rustle"),
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
            disabled=True,
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


def search_bar():
    return html.Div(
        className="rustle-search",
        children=[
            dcc.Input(
                id="rustle-search",
                type="search",
                placeholder="Search playlists…",
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


def playlist_card(playlist):
    return html.Div(
        className="rustle-card rustle-card--playlist",
        children=[
            html.Img(
                src=playlist.get("image_url"),
                className="rustle-card__art",
            ),
            html.Div(
                playlist["name"],
                className="rustle-card__title",
            ),
        ],
    )


def track_card(track, already_added: bool = False):
    children = [
        html.Img(
            src=track.get("album_image_url"),
            className="rustle-card__art",
        ),
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
    return html.Div(f"+{n} added", className="rustle-counter-chip")
