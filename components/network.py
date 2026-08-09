"""Hard-bop musician network page (dash-cytoscape).

Nodes are musicians (size by degree, color by era); edges are shared
releases (width by weight). The page always renders: it reads the
live graph from Postgres and falls back to a committed graph.json so
a logged-out visitor never sees an empty canvas.
"""

import json
import logging
from pathlib import Path

import dash_cytoscape as cyto
from dash import dcc, html

from netviz.db import get_graph

logger = logging.getLogger(__name__)

GRAPH_JSON = Path(__file__).parent.parent / "netviz" / "graph.json"

# Era buckets -> node color (Spotify-dark friendly palette).
_ERA_COLORS = [
    (1955, "#1db954"),   # earliest hard bop -> Spotify green
    (1960, "#4fc3f7"),
    (1965, "#ba68c8"),
    (9999, "#ffb74d"),   # later / post-bop
]


def _era_color(era) -> str:
    if era is None:
        return "#888888"
    for cutoff, color in _ERA_COLORS:
        if era < cutoff:
            return color
    return _ERA_COLORS[-1][1]


def load_graph() -> dict:
    """Live graph from the DB, or the committed demo if empty/unreachable."""
    try:
        graph = get_graph()
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
) -> dict:
    """Return a subgraph honoring the era / instrument / weight filters.

    Nodes with an unknown (None) era are never filtered out by era.
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
                    "color": _era_color(node.get("era")),
                    # scale marker size with connectivity
                    "size": 18 + 6 * node.get("degree", 0),
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
            "font-size": "10px",
            "text-outline-color": "#121212",
            "text-outline-width": 1.5,
            "min-zoomed-font-size": 8,
        },
    },
    {
        "selector": "edge",
        "style": {
            "width": "mapData(weight, 1, 5, 1, 6)",
            "line-color": "#404040",
            "curve-style": "haystack",
            "opacity": 0.7,
        },
    },
    {
        "selector": "node:selected",
        "style": {
            "border-color": "#1db954",
            "border-width": 3,
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


def _max_weight(graph: dict) -> int:
    weights = [e.get("weight", 1) for e in graph.get("edges", [])]
    return max(weights) if weights else 1


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
            html.H2("Hard Bop Session Network", className="network-title"),
            html.P(
                "Every node is a musician; every edge means they played "
                "on the same record. Node size grows with how many "
                "collaborators a player has; color marks the era they "
                "came up in. Built offline from MusicBrainz + Discogs, "
                "cached to Postgres. Click a node to see their sessions.",
                className="network-blurb",
            ),
            html.P(
                f"{n_nodes} musicians · {n_edges} shared-session links",
                className="network-stats",
            ),
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
