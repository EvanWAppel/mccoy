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
from netviz.seeds import MIN_EDGE_WEIGHT

logger = logging.getLogger(__name__)

GRAPH_JSON = Path(__file__).parent / "graph.json"


def prune_isolated(graph: dict) -> dict:
    """Drop nodes with no surviving edges (noise after edge pruning)."""
    connected = set()
    for edge in graph["edges"]:
        connected.add(edge["source"])
        connected.add(edge["target"])
    nodes = [n for n in graph["nodes"] if n["id"] in connected]
    return {"nodes": nodes, "edges": graph["edges"]}


def export_graph(path: Path = GRAPH_JSON) -> int:
    """Write the connected-core DB graph to graph.json; return node count.

    Isolated nodes are pruned so the demo is a readable network rather
    than a dust cloud. Only overwrites when the crawl produced a
    connected graph, so a failed/empty run never blanks the fallback.
    """
    graph = prune_isolated(db.get_graph())
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
    """Crawl from seeds, rebuild edges, backfill eras, export graph.json."""
    result = crawl()
    for name in result["unresolved"]:
        logger.warning("unresolved musician name (skipped): %s", name)
    db.backfill_active_years()
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
