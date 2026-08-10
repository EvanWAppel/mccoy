"""Snowball crawl from seed musicians into the nv_* tables.

Starting from a curated seed list, fetch each musician's releases and
the personnel on each release, upsert everything, and expand outward
to newly discovered players. Bounded by config constants so the crawl
terminates; idempotent so re-running extends the cache without
duplicating rows.
"""

import logging
from collections import Counter

from netviz import db, sources
from netviz.seeds import (
    MAX_HOPS,
    NODE_CAP,
    PER_MUSICIAN_RELEASE_CAP,
    SEED_MUSICIANS,
)

logger = logging.getLogger(__name__)


def crawl(
    seeds: list[str] | None = None,
    node_cap: int = NODE_CAP,
    max_hops: int = MAX_HOPS,
    release_cap: int = PER_MUSICIAN_RELEASE_CAP,
) -> dict:
    """Run the bounded snowball crawl; return crawl stats.

    Returns ``{"crawled": [names], "unresolved": [names]}``.
    """
    seeds = list(SEED_MUSICIANS if seeds is None else seeds)
    crawled: set[str] = set()
    unresolved: list[str] = []
    frontier = seeds

    for hop in range(max_hops + 1):
        # candidate name -> how many admitted releases it links to
        discovered: Counter[str] = Counter()
        for name in frontier:
            if name in crawled:
                continue
            if len(crawled) >= node_cap:
                break

            try:
                releases = sources.discogs_releases_for(
                    name, limit=release_cap
                )
            except Exception as exc:  # never let one musician kill the run
                logger.warning("crawl: skipping %r after error: %s", name, exc)
                unresolved.append(name)
                continue
            if not releases:
                unresolved.append(name)
                continue

            crawled.add(name)
            for rel in releases:
                try:
                    release_id = db.upsert_release_by_discogs(
                        discogs_id=rel["discogs_id"],
                        title=rel["title"],
                        year=rel.get("year"),
                        label=rel.get("label"),
                    )
                    fetched = sources.discogs_personnel_for(rel["discogs_id"])
                    db.set_release_styles(release_id, fetched["styles"])
                except Exception as exc:  # skip a bad release, keep crawling
                    logger.warning(
                        "crawl: skipping release %s: %s",
                        rel.get("discogs_id"), exc,
                    )
                    continue
                for person in fetched["personnel"]:
                    musician_id = db.upsert_musician_by_discogs(
                        discogs_id=person["discogs_id"],
                        name=person["name"],
                        primary_instrument=person.get("instrument"),
                    )
                    db.add_credit(
                        musician_id, release_id, person.get("instrument")
                    )
                    other = person["name"]
                    if other not in crawled:
                        discovered[other] += 1

        logger.info(
            "hop %d: %d crawled, %d candidates discovered",
            hop,
            len(crawled),
            len(discovered),
        )
        if len(crawled) >= node_cap:
            break
        # BFS priority: most-connected discovered musicians first.
        frontier = [name for name, _ in discovered.most_common()]

    logger.info(
        "crawl complete: %d musicians crawled, %d unresolved",
        len(crawled),
        len(unresolved),
    )
    return {"crawled": sorted(crawled), "unresolved": unresolved}
