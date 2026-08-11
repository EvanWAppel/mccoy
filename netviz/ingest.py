"""Ingest CLI: crawl the seed network, then rebuild edges.

Run offline (never at page-render time):

    uv run python -m netviz.ingest

Requires DATABASE_URL (writes nv_* tables) and, for the Discogs half,
DISCOGS_TOKEN. Logs progress and every unresolved name so name-match
misses are visible, never silently dropped.
"""

import json
import logging
from pathlib import Path

from netviz import db
from netviz.crawl import crawl
from netviz.edges import rebuild_edges
from netviz.genre import GENRE_BUCKETS, OTHER
from netviz.seeds import (
    GRAPH_MIN_YEAR,
    GRAPH_NODE_LIMIT,
    MIN_EDGE_WEIGHT,
)

logger = logging.getLogger(__name__)

GRAPH_JSON = Path(__file__).parent / "graph.json"

# Rendered genres: every bucket except the catch-all "Other" (swing,
# big band, vocal, soundtrack, non-jazz sideman dates).
CORE_GENRES = frozenset(GENRE_BUCKETS) - {OTHER}


def focus_graph(
    graph: dict,
    min_year: int = GRAPH_MIN_YEAR,
    genres: frozenset = CORE_GENRES,
) -> dict:
    """Keep musicians in a core genre and active from ``min_year`` on.

    Drops the pre-hard-bop swing/big-band cliques and non-core "Other"
    sidemen so the rendered graph stays centered on McCoy Tyner's
    hard-bop / modal / post-bop world. Isolated nodes are pruned.
    """
    kept = {
        n["id"]
        for n in graph.get("nodes", [])
        if n.get("genre") in genres and (n.get("era") or 0) >= min_year
    }
    nodes = [n for n in graph.get("nodes", []) if n["id"] in kept]
    edges = [
        e
        for e in graph.get("edges", [])
        if e["source"] in kept and e["target"] in kept
    ]
    return prune_isolated({"nodes": nodes, "edges": edges})


def prune_isolated(graph: dict) -> dict:
    """Drop nodes with no surviving edges (noise after edge pruning)."""
    connected = set()
    for edge in graph["edges"]:
        connected.add(edge["source"])
        connected.add(edge["target"])
    nodes = [n for n in graph["nodes"] if n["id"] in connected]
    return {"nodes": nodes, "edges": graph["edges"]}


def cap_by_degree(graph: dict, limit: int = GRAPH_NODE_LIMIT) -> dict:
    """Keep the ``limit`` highest-degree nodes and edges among them.

    Degree is the number of incident edges. Ties break on lower id for
    determinism. A no-op when the graph already fits under ``limit``.
    """
    nodes = graph.get("nodes", [])
    if len(nodes) <= limit:
        return graph
    degree: dict = {}
    for edge in graph.get("edges", []):
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1
    ranked = sorted(
        nodes, key=lambda n: (-degree.get(n["id"], 0), n["id"])
    )
    kept_ids = {n["id"] for n in ranked[:limit]}
    kept_nodes = [n for n in nodes if n["id"] in kept_ids]
    kept_edges = [
        e
        for e in graph.get("edges", [])
        if e["source"] in kept_ids and e["target"] in kept_ids
    ]
    return prune_isolated({"nodes": kept_nodes, "edges": kept_edges})


def export_graph(path: Path = GRAPH_JSON) -> int:
    """Write the connected-core DB graph to graph.json; return node count.

    Isolated nodes are pruned so the demo is a readable network rather
    than a dust cloud. Only overwrites when the crawl produced a
    connected graph, so a failed/empty run never blanks the fallback.
    """
    graph = cap_by_degree(focus_graph(prune_isolated(db.get_graph())))
    if not graph["nodes"]:
        logger.warning("graph has no connected nodes; leaving %s untouched",
                       path.name)
        return 0
    path.write_text(json.dumps(graph, indent=2))
    logger.info(
        "wrote %s (%d nodes, %d edges)",
        path.name,
        len(graph["nodes"]),
        len(graph["edges"]),
    )
    return len(graph["nodes"])


def run_ingest(
    min_edge_weight: int = MIN_EDGE_WEIGHT,
    export: bool = True,
) -> dict:
    """Crawl seeds, rebuild edges, backfill eras + genres, export JSON."""
    result = crawl()
    for name in result["unresolved"]:
        logger.warning("unresolved musician name (skipped): %s", name)
    db.backfill_active_years()
    db.backfill_primary_genre()
    edge_count = rebuild_edges(min_weight=min_edge_weight)
    exported = export_graph() if export else 0
    summary = {
        "crawled": len(result["crawled"]),
        "unresolved": len(result["unresolved"]),
        "edges": edge_count,
        "exported_nodes": exported,
    }
    logger.info("ingest complete: %s", summary)
    return summary


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_ingest()


if __name__ == "__main__":
    main()
