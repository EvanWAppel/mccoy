"""Ingest CLI: crawl the seed network, then rebuild edges.

Run offline (never at page-render time):

    uv run python -m netviz.ingest

Requires DATABASE_URL (writes nv_* tables) and, for the Discogs half,
DISCOGS_TOKEN. Logs progress and every unresolved name so name-match
misses are visible, never silently dropped.
"""

import logging

from netviz.crawl import crawl
from netviz.edges import rebuild_edges
from netviz.seeds import MIN_EDGE_WEIGHT

logger = logging.getLogger(__name__)


def run_ingest(min_edge_weight: int = MIN_EDGE_WEIGHT) -> dict:
    """Crawl from seeds, rebuild nv_edges, return a summary dict."""
    result = crawl()
    for name in result["unresolved"]:
        logger.warning("unresolved musician name (skipped): %s", name)
    edge_count = rebuild_edges(min_weight=min_edge_weight)
    summary = {
        "crawled": len(result["crawled"]),
        "unresolved": len(result["unresolved"]),
        "edges": edge_count,
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
