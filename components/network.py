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


def network_page(graph: dict) -> html.Div:
    """Full /network view: intro, layout toggle, graph canvas, side panel."""
    elements = to_cytoscape_elements(graph)
    n_nodes = len(graph.get("nodes", []))
    n_edges = len(graph.get("edges", []))

    return html.Div(
        className="network-page",
        children=[
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
