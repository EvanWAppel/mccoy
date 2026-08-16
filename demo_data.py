"""Deterministic demo data for the public (no-login) view.

Backs the recruiter-facing dashboard as a *fallback* so it renders a
populated demo when the owner's real snapshots are unavailable (e.g. a
fresh deploy before the weekly cron has run). This data is never written
to the database; it only feeds the public callbacks when the DB is empty.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Curated, recognizable artists with genres. List order is the baseline
# rank; weekly snapshots permute it so the trends bump chart shows motion.
_ARTISTS: list[tuple[str, list[str]]] = [
    ("Radiohead", ["art rock", "alternative rock"]),
    ("Fleetwood Mac", ["classic rock", "soft rock"]),
    ("Kendrick Lamar", ["hip hop", "conscious hip hop"]),
    ("Bon Iver", ["indie folk", "chamber pop"]),
    ("Daft Punk", ["french house", "electronic"]),
    ("Miles Davis", ["jazz", "cool jazz"]),
    ("Tame Impala", ["neo-psychedelic", "indietronica"]),
    ("The Beatles", ["classic rock", "psychedelic rock"]),
    ("Herbie Hancock", ["jazz fusion", "post-bop"]),
    ("Vulfpeck", ["funk", "indie funk"]),
]

_WEEKS = 5  # number of short_term snapshots for the trends chart


def _rank_order(week: int) -> list[int]:
    """A gentle, deterministic permutation of indices for one week."""
    order = list(range(len(_ARTISTS)))
    for i in range(week % 2, len(order) - 1, 3):
        order[i], order[i + 1] = order[i + 1], order[i]
    return order


def _artist(rank: int, base_index: int, seed: int) -> dict:
    name, genres = _ARTISTS[base_index]
    return {
        "rank": rank,
        "name": name,
        "artist_id": f"demo-{seed}-{base_index}",
        "image_url": None,
        "genres": list(genres),
    }


def demo_snapshots(time_range: str = "short_term") -> list[dict]:
    """Return ``_WEEKS`` deterministic snapshots ending at 'now'."""
    now = datetime.now(timezone.utc)
    snaps: list[dict] = []
    for week in range(_WEEKS):
        when = now - timedelta(weeks=_WEEKS - 1 - week)
        order = _rank_order(week)
        artists = [
            _artist(rank, base_index, seed=week)
            for rank, base_index in enumerate(order, start=1)
        ]
        snaps.append(
            {
                "snapshot_id": -(week + 1),  # negative => not a real row
                "captured_at": when,
                "time_range": time_range,
                "artists": artists,
            }
        )
    logger.debug("served %d demo snapshots (%s)", len(snaps), time_range)
    return snaps


def demo_latest_snapshot(time_range: str = "short_term") -> dict:
    """The most recent demo snapshot for the stats grid."""
    return demo_snapshots(time_range)[-1]
