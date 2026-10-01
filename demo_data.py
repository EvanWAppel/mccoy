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


def demo_patterns(today=None) -> dict:
    """Synthetic Listening Patterns (public view is demo-only).

    Evenings and weekend late mornings are busiest; 30 listening days
    over the last 32 (two quiet days), ending today.
    """
    from zoneinfo import ZoneInfo

    from components.patterns import LISTENING_TZ

    # Same local "today" the chart windows on, not the server's date
    # (Railway is UTC), so the newest demo bar is never filtered out.
    today = today or datetime.now(ZoneInfo(LISTENING_TZ)).date()
    hour_of_week = []
    for dow in range(1, 8):
        weekend = dow >= 6
        for hour in range(24):
            if 1 <= hour <= 6:
                continue
            base = 1
            if 18 <= hour <= 23:
                base = 6
            elif weekend and 10 <= hour <= 13:
                base = 5
            elif not weekend and 9 <= hour <= 17:
                base = 3
            plays = base + (dow * 7 + hour * 3) % 4
            hour_of_week.append({
                "iso_dow": dow, "hour": hour, "plays": plays,
                "minutes": round(plays * 3.9, 2),
            })
    quiet = {5, 17}
    daily = []
    for back in range(31, -1, -1):
        if back in quiet:
            continue
        plays = 12 + (back * 11) % 23
        daily.append({
            "listen_date": today - timedelta(days=back),
            "plays": plays,
            "minutes": round(plays * 3.9, 2),
        })
    streaks = [
        {"artist_name": name, "streak_days": days,
         "streak_start": today - timedelta(days=days - 1 + lag),
         "streak_end": today - timedelta(days=lag)}
        for (name, _), days, lag in zip(
            _ARTISTS[:5], (6, 4, 3, 3, 2), (0, 1, 0, 9, 2)
        )
    ]
    return {"hour_of_week": hour_of_week, "daily": daily,
            "streaks": streaks}
