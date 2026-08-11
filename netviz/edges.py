"""Build musician<->musician edges from raw co-credits.

An edge links two musicians credited on the same release; its weight
is the number of releases they share. Edges are precomputed here and
persisted to nv_edges so the /network page reads a ready-made graph.
"""

import logging
from collections import defaultdict
from itertools import combinations

from netviz import db

logger = logging.getLogger(__name__)

# A few sample titles per edge is plenty for a tooltip.
MAX_SAMPLE_RELEASES = 3


def build_edges(credits: list[dict], min_weight: int = 1) -> list[dict]:
    """Collapse per-release co-credits into weighted musician edges.

    ``credits`` is a list of ``{musician_id, release_id,
    release_title}``. Returns ``[{musician_a, musician_b, weight,
    sample_releases}]`` with edges weaker than ``min_weight`` pruned.
    """
    musicians_by_release: dict[int, set[int]] = defaultdict(set)
    title_by_release: dict[int, str | None] = {}
    for credit in credits:
        rid = credit["release_id"]
        musicians_by_release[rid].add(credit["musician_id"])
        title_by_release[rid] = credit.get("release_title")

    weight: dict[tuple[int, int], int] = defaultdict(int)
    samples: dict[tuple[int, int], list[str]] = defaultdict(list)
    for rid, musician_ids in musicians_by_release.items():
        title = title_by_release.get(rid)
        for a, b in combinations(sorted(musician_ids), 2):
            weight[(a, b)] += 1
            if title and len(samples[(a, b)]) < MAX_SAMPLE_RELEASES:
                samples[(a, b)].append(title)

    edges = [
        {
            "musician_a": a,
            "musician_b": b,
            "weight": w,
            "sample_releases": samples[(a, b)],
        }
        for (a, b), w in weight.items()
        if w >= min_weight
    ]
    logger.info(
        "built %d edges from %d releases (min_weight=%d)",
        len(edges),
        len(musicians_by_release),
        min_weight,
    )
    return edges


def _fetch_credits() -> list[dict]:
    """Read every co-credit from nv_credits joined to release titles."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.musician_id, c.release_id, r.title
                FROM nv_credits c
                JOIN nv_releases r ON r.id = c.release_id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"musician_id": m, "release_id": r, "release_title": t}
        for m, r, t in rows
    ]


def rebuild_edges(min_weight: int = 1) -> int:
    """Rebuild nv_edges from the current nv_credits; return edge count."""
    edges = build_edges(_fetch_credits(), min_weight=min_weight)
    db.replace_edges(edges)
    return len(edges)
