"""Rate feature — flip through album covers, preview a song, and tap a
1-10 scale to rate it; then browse rated songs sorted by title, artist,
year, or rating.

Mirrors the Rustle "record-flipping" interaction: album cards are a
gesture-driven crate (assets/rustle.js), drilling up into an album opens
its tracks, and each track carries a tap scale instead of an add gesture.
"""

from dash import dcc, html

# Album cards reuse Rustle's card chrome (cover art + title). Rating
# track cards deliberately use a plain `.rustle-card` (not
# `--track`) so assets/rustle.js doesn't try to stamp "Added" on an
# up-swipe — rating happens through the tap scale, not a gesture.


# Canonical end-of-queue copy, shared with app.py + tests.
RATE_SEARCH_END_MESSAGE = (
    "That's every album for this search. Swipe down to start over."
)
RATE_ALBUM_END_MESSAGE = (
    "You've flipped through every song on this record. "
    "Swipe down to pick another."
)

RATE_SORTS = [
    {"label": "Title", "value": "title"},
    {"label": "Artist", "value": "artist"},
    {"label": "Year", "value": "year"},
    {"label": "Rating", "value": "rating"},
]


def rate_sub_tabs():
    return dcc.Tabs(
        id="rate-tabs",
        value="flip",
        className="rate-tabs",
        children=[
            dcc.Tab(
                label="Rate", value="flip",
                className="rate-tab",
                selected_className="rate-tab--selected",
            ),
            dcc.Tab(
                label="Rated songs", value="rated",
                className="rate-tab",
                selected_className="rate-tab--selected",
            ),
        ],
    )


def rate_search_bar(value=""):
    return html.Div(
        className="rustle-search",
        children=[
            dcc.Input(
                id="rate-search",
                type="search",
                placeholder="Search albums…",
                value=value,
                debounce=True,
                className="rustle-search__input",
            ),
        ],
    )


def _card_art(image_url):
    if image_url:
        return html.Img(src=image_url, className="rustle-card__art")
    return html.Div(
        className="rustle-card__art rustle-card__art--placeholder",
    )


def album_card(album):
    return html.Div(
        className="rustle-card rustle-card--playlist",
        children=[
            _card_art(album.get("image_url")),
            html.Div(album.get("name", ""), className="rustle-card__title"),
        ],
    )


def rating_card(track, current=None):
    subtitle = " · ".join(
        p for p in [track.get("artist"), track.get("year")] if p
    )
    children = [
        _card_art(track.get("image_url")),
        html.Div(track.get("name", ""), className="rustle-card__title"),
    ]
    if subtitle:
        children.append(
            html.Div(subtitle, className="rate-card__subtitle")
        )
    if current:
        children.append(
            html.Div(f"Rated {current}/10", className="rustle-card__badge")
        )
    return html.Div(
        className="rustle-card rate-card",
        children=children,
    )


def rating_scale(current=None):
    # Ten tap targets; the current score (if any) is highlighted.
    buttons = [
        html.Button(
            str(n),
            id={"type": "rate-score", "value": n},
            n_clicks=0,
            className=(
                "rate-scale__btn rate-scale__btn--active"
                if current == n
                else "rate-scale__btn"
            ),
        )
        for n in range(1, 11)
    ]
    return html.Div(
        className="rate-scale",
        children=[
            html.Div("Tap to rate", className="rate-scale__label"),
            html.Div(buttons, className="rate-scale__row"),
        ],
    )


def _sort_header(sort_by):
    return html.Tr(
        className="rate-table__head",
        children=[
            html.Th(
                html.Button(
                    s["label"]
                    + (" ▾" if s["value"] == sort_by else ""),
                    id={"type": "rate-sort", "value": s["value"]},
                    n_clicks=0,
                    className=(
                        "rate-table__sort rate-table__sort--active"
                        if s["value"] == sort_by
                        else "rate-table__sort"
                    ),
                )
            )
            for s in RATE_SORTS
        ],
    )


def ratings_table(ratings, sort_by="rating"):
    if not ratings:
        return html.Div(
            className="rate-empty",
            children=[
                html.P(
                    "No rated songs yet. Flip through some albums and "
                    "tap a score.",
                    className="rate-empty__msg",
                ),
            ],
        )
    rows = [_sort_header(sort_by)]
    for r in ratings:
        rows.append(
            html.Tr(
                className="rate-table__row",
                children=[
                    html.Td(r.get("name", "")),
                    html.Td(r.get("artist", "")),
                    html.Td(r.get("year", "")),
                    html.Td(
                        f"{r.get('rating', '')}/10",
                        className="rate-table__score",
                    ),
                ],
            )
        )
    return html.Table(rows, className="rate-table")
