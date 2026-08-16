"""Hard-bop musician network page (dash-cytoscape).

Nodes are musicians (size by degree, color by era); edges are shared
releases (width by weight). The page always renders: it reads the
live graph from Postgres and falls back to a committed graph.json so
a logged-out visitor never sees an empty canvas.
"""

import json
import logging
import math
from pathlib import Path

import dash_cytoscape as cyto
from dash import dcc, html

from netviz.db import get_graph
from netviz.ingest import cap_by_degree, prune_isolated

logger = logging.getLogger(__name__)

GRAPH_JSON = Path(__file__).parent.parent / "netviz" / "graph.json"

# Genre bucket -> node color (Spotify-dark friendly palette). Keys match
# netviz.genre.GENRE_BUCKETS; unknown/None renders grey.
_GENRE_COLORS = {
    # Top-level genres of the multi-genre atlas (Discogs dump).
    "Jazz": "#1db954",              # Spotify green
    "Rock": "#e57373",              # red
    "Blues": "#4fc3f7",             # blue
    "Funk / Soul": "#ffb74d",       # orange
    "Other": "#90a4ae",             # blue-grey (fallback)
}
_UNKNOWN_GENRE_COLOR = "#888888"


def _genre_color(genre) -> str:
    if not genre:
        return _UNKNOWN_GENRE_COLOR
    return _GENRE_COLORS.get(genre, _GENRE_COLORS["Other"])


def load_graph() -> dict:
    """Live graph from the DB, or the committed demo if empty/unreachable."""
    try:
        # Focusing/capping is done at build time (netviz.dumps for the
        # atlas, ingest.export_graph for the jazz DB); here just cap by
        # degree as a safety net so a huge DB can't blow up the render.
        graph = cap_by_degree(prune_isolated(get_graph()))
        if graph.get("nodes"):
            return graph
    except Exception as exc:  # DB missing/unreachable -> demo fallback
        logger.warning("get_graph failed, using committed graph.json: %s", exc)
    return json.loads(GRAPH_JSON.read_text())


def filter_graph(
    graph: dict,
    era_range: tuple | list | None = None,
    instruments: list | None = None,
    min_weight: int = 1,
    genres: list | None = None,
) -> dict:
    """Return a subgraph honoring the era / instrument / genre / weight
    filters.

    Nodes with an unknown (None) era are never filtered out by era.
    A genre filter only keeps nodes whose genre is in ``genres``
    (unknown-genre nodes drop when a genre filter is active).
    Edges survive only if their weight clears ``min_weight`` *and* both
    endpoints survived the node filters.
    """
    lo, hi = (era_range or (None, None))
    kept_ids = set()
    nodes = []
    for node in graph.get("nodes", []):
        era = node.get("era")
        if era is not None and lo is not None and era < lo:
            continue
        if era is not None and hi is not None and era > hi:
            continue
        if instruments and node.get("instrument") not in instruments:
            continue
        if genres and node.get("genre") not in genres:
            continue
        nodes.append(node)
        kept_ids.add(node["id"])

    edges = [
        e
        for e in graph.get("edges", [])
        if e.get("weight", 1) >= min_weight
        and e["source"] in kept_ids
        and e["target"] in kept_ids
    ]
    return {"nodes": nodes, "edges": edges}


def to_cytoscape_elements(graph: dict) -> list[dict]:
    """Convert a ``{nodes, edges}`` graph to Cytoscape element dicts."""
    elements: list[dict] = []
    for node in graph.get("nodes", []):
        elements.append(
            {
                "data": {
                    "id": str(node["id"]),
                    "label": node.get("name", ""),
                    "degree": node.get("degree", 0),
                    "era": node.get("era"),
                    "instrument": node.get("instrument"),
                    "genre": node.get("genre"),
                    "style": node.get("style"),
                    "color": _genre_color(node.get("genre")),
                    # sqrt scaling: hubs stay bigger without ballooning
                    # into 250px blobs that swallow their neighbors.
                    "size": round(14 + 7 * math.sqrt(node.get("degree", 0))),
                }
            }
        )
    for edge in graph.get("edges", []):
        elements.append(
            {
                "data": {
                    "source": str(edge["source"]),
                    "target": str(edge["target"]),
                    "weight": edge.get("weight", 1),
                    "samples": ", ".join(edge.get("sample_releases", [])),
                }
            }
        )
    return elements


_STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "background-color": "data(color)",
            "label": "data(label)",
            "width": "data(size)",
            "height": "data(size)",
            "color": "#ffffff",
            "font-size": "11px",
            "text-outline-color": "#121212",
            "text-outline-width": 2,
            # a bg-colored ring separates touching same-color nodes
            "border-color": "#121212",
            "border-width": 2,
            # labels only when zoomed in enough, so it isn't a wall of
            # text at the default fit — hubs + highlights override this.
            "min-zoomed-font-size": 14,
        },
    },
    {
        # always label the well-connected anchors
        "selector": "node[degree >= 12]",
        "style": {
            "font-size": "14px",
            "min-zoomed-font-size": 0,
            "font-weight": "bold",
        },
    },
    {
        "selector": "edge",
        "style": {
            "width": "mapData(weight, 1, 9, 1, 7)",
            "line-color": "#3a3a3a",
            "curve-style": "haystack",
            "opacity": 0.6,
        },
    },
    {
        "selector": "node:selected",
        "style": {
            "border-color": "#ffffff",
            "border-width": 3,
        },
    },
    # --- ego-network focus: dim everything, light up the neighborhood ---
    {
        "selector": ".faded",
        "style": {"opacity": 0.08, "text-opacity": 0},
    },
    {
        "selector": "node.highlight",
        "style": {"opacity": 1, "min-zoomed-font-size": 0},
    },
    {
        "selector": "edge.highlight",
        "style": {"opacity": 0.9, "line-color": "#1db954", "width": 3},
    },
    {
        "selector": "node.ego",
        "style": {
            "border-color": "#1db954",
            "border-width": 5,
            "min-zoomed-font-size": 0,
            "font-size": "16px",
            "font-weight": "bold",
        },
    },
]


def _era_bounds(graph: dict) -> tuple[int, int]:
    eras = [n["era"] for n in graph.get("nodes", []) if n.get("era")]
    if not eras:
        return (1945, 1975)
    return (min(eras), max(eras))


def _instrument_options(graph: dict) -> list[dict]:
    instruments = sorted(
        {
            n["instrument"]
            for n in graph.get("nodes", [])
            if n.get("instrument")
        }
    )
    return [{"label": i.title(), "value": i} for i in instruments]


def _genre_options(graph: dict) -> list[dict]:
    """Genre filter options, ordered by the palette (present genres only)."""
    present = {n["genre"] for n in graph.get("nodes", []) if n.get("genre")}
    return [
        {"label": g, "value": g}
        for g in _GENRE_COLORS
        if g in present
    ]


def _genre_legend(graph: dict) -> html.Div:
    """Color key for the genres actually present, in palette order."""
    present = {n.get("genre") for n in graph.get("nodes", [])}
    return html.Div(
        className="network-legend",
        children=[
            html.Span(
                className="network-legend-item",
                children=[
                    html.Span(
                        className="network-legend-swatch",
                        style={"backgroundColor": color},
                    ),
                    html.Span(genre, className="network-legend-lbl"),
                ],
            )
            for genre, color in _GENRE_COLORS.items()
            if genre in present
        ],
    )


def _max_weight(graph: dict) -> int:
    weights = [e.get("weight", 1) for e in graph.get("edges", [])]
    return max(weights) if weights else 1


def _musician_options(graph: dict) -> list[dict]:
    """Name -> node-id options for the focus dropdown, sorted by name."""
    nodes = sorted(
        graph.get("nodes", []), key=lambda n: n.get("name", "").lower()
    )
    return [{"label": n["name"], "value": str(n["id"])} for n in nodes]


def network_page(graph: dict) -> html.Div:
    """Full /network view: intro, filters, layout toggle, canvas, panel."""
    elements = to_cytoscape_elements(graph)
    n_nodes = len(graph.get("nodes", []))
    n_edges = len(graph.get("edges", []))
    era_lo, era_hi = _era_bounds(graph)
    max_weight = _max_weight(graph)

    return html.Div(
        className="network-page",
        children=[
            dcc.Store(id="network-graph-data", data=graph),
            dcc.Store(id="network-fit-dummy"),
            dcc.Store(id="network-focus-dummy"),
            html.H2("Musical Network", className="network-title"),
            html.P(
                "Every node is a musician; every edge means they played "
                "on the same record. Node size grows with how many "
                "collaborators a player has; color marks their dominant "
                "genre across the 1955–1975 golden era — jazz, "
                "rock, blues, and funk/soul — where session players "
                "wove the scenes together. Built offline from Discogs "
                "release credits. Click a node to see their sessions.",
                className="network-blurb",
            ),
            html.P(
                f"{n_nodes} musicians · {n_edges} shared-session links",
                className="network-stats",
            ),
            _genre_legend(graph),
            html.Div(
                className="network-filters",
                children=[
                    html.Div(
                        className="network-filter",
                        children=[
                            html.Label("Era", className="network-filter-lbl"),
                            dcc.RangeSlider(
                                id="network-era",
                                min=era_lo,
                                max=era_hi,
                                value=[era_lo, era_hi],
                                step=1,
                                marks={
                                    era_lo: str(era_lo),
                                    era_hi: str(era_hi),
                                },
                                tooltip={"placement": "bottom"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="network-filter",
                        children=[
                            html.Label(
                                "Instrument",
                                className="network-filter-lbl",
                            ),
                            dcc.Dropdown(
                                id="network-instrument",
                                options=_instrument_options(graph),
                                value=[],
                                multi=True,
                                placeholder="All instruments",
                                className="network-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="network-filter",
                        children=[
                            html.Label(
                                "Genre",
                                className="network-filter-lbl",
                            ),
                            dcc.Dropdown(
                                id="network-genre",
                                options=_genre_options(graph),
                                value=[],
                                multi=True,
                                placeholder="All genres",
                                className="network-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="network-filter",
                        children=[
                            html.Label(
                                "Min shared sessions",
                                className="network-filter-lbl",
                            ),
                            dcc.Slider(
                                id="network-min-weight",
                                min=1,
                                max=max_weight,
                                value=1,
                                step=1,
                                marks={
                                    1: "1",
                                    max_weight: str(max_weight),
                                },
                                tooltip={"placement": "bottom"},
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="network-controls-row",
                children=[
                    dcc.RadioItems(
                        id="network-layout",
                        options=[
                            {"label": "Force-directed", "value": "cose"},
                            {"label": "Concentric", "value": "concentric"},
                        ],
                        value="cose",
                        inline=True,
                        className="network-layout-toggle",
                    ),
                    html.Div(
                        className="network-focus",
                        children=[
                            dcc.Dropdown(
                                id="network-focus",
                                options=_musician_options(graph),
                                value=None,
                                placeholder=(
                                    "Focus on a musician's network…"
                                ),
                                className="network-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="network-canvas-wrap",
                children=[
                    cyto.Cytoscape(
                        id="network-graph",
                        elements=elements,
                        layout={"name": "cose", "animate": False},
                        stylesheet=_STYLESHEET,
                        style={"width": "100%", "height": "600px"},
                    ),
                    html.Div(
                        id="network-side-panel",
                        className="network-side-panel",
                        children=html.P(
                            "Click a musician to see details.",
                            className="network-side-hint",
                        ),
                    ),
                ],
            ),
        ],
    )
