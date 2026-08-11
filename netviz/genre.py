"""Normalize Discogs style tags into a small curated genre bucket set.

Discogs tags releases with free-form ``styles`` (e.g. "Hard Bop",
"Post Bop", "Soul-Jazz", "Free Jazz"). The network viz colors/filters
musicians by a single genre, so we collapse those raw styles into a
handful of buckets and pick a musician's dominant one across all the
releases they're credited on.
"""

from collections import Counter

# Curated buckets (Evan, 2026-08-09): modal + post-bop expansion around
# McCoy Tyner, with the neighboring scenes kept distinct and everything
# else pooled into "Other". "Bebop" added 2026-08-10 — it's the single
# most common Discogs style in the crawl, so pooling it into "Other"
# would swamp that bucket and hide the graph's bebop→hard-bop backbone.
BEBOP = "Bebop"
HARD_BOP = "Hard Bop"
MODAL = "Modal"
POST_BOP = "Post-Bop"
SOUL_JAZZ = "Soul-Jazz"
FREE = "Free/Avant-Garde"
COOL = "Cool"
LATIN = "Latin"
OTHER = "Other"

GENRE_BUCKETS = [
    BEBOP,
    HARD_BOP,
    MODAL,
    POST_BOP,
    SOUL_JAZZ,
    FREE,
    COOL,
    LATIN,
    OTHER,
]

# Raw Discogs style (normalized: lowercased, hyphens/underscores -> space,
# collapsed whitespace) -> bucket. Unlisted styles fall through to OTHER.
_STYLE_TO_BUCKET = {
    "bop": BEBOP,
    "hard bop": HARD_BOP,
    "modal": MODAL,
    "post bop": POST_BOP,
    "contemporary jazz": POST_BOP,
    "soul jazz": SOUL_JAZZ,
    "free jazz": FREE,
    "avant garde jazz": FREE,
    "free improvisation": FREE,
    "cool jazz": COOL,
    "latin jazz": LATIN,
    "afro cuban jazz": LATIN,
    "bossa nova": LATIN,
}


def _norm(style: str) -> str:
    return " ".join(style.lower().replace("-", " ").replace("_", " ").split())


def normalize_style(style: str | None) -> str:
    """Map one raw Discogs style to a bucket (``OTHER`` if unrecognized)."""
    if not style:
        return OTHER
    return _STYLE_TO_BUCKET.get(_norm(style), OTHER)


def dominant_genre(styles: list[str] | None) -> str | None:
    """Pick the most common *specific* bucket across ``styles``.

    ``OTHER`` only wins when no specific bucket appears at all. Returns
    ``None`` when there are no styles to classify (unknown genre).
    """
    if not styles:
        return None
    counts = Counter(normalize_style(s) for s in styles)
    specific = Counter(
        {b: n for b, n in counts.items() if b != OTHER}
    )
    if specific:
        return specific.most_common(1)[0][0]
    return OTHER
