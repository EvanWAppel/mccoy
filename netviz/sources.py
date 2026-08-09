"""External source clients for the music network crawl.

Two sources, both fetched offline by the ingest job (never at page
render): MusicBrainz for canonical identity + structured performer
relations, Discogs for richer liner-note credits. Name resolution
misses are logged, never silently dropped.
"""

import logging
import os
import time

import discogs_client
import musicbrainzngs

logger = logging.getLogger(__name__)

# Polite, self-identifying MusicBrainz UA + built-in ~1 req/sec limiter.
musicbrainzngs.set_useragent("mccoy", "0.1", "appelew@gmail.com")
musicbrainzngs.set_rate_limit(limit_or_interval=1.0, new_requests=1)

# Discogs allows ~60 req/min for authenticated clients.
DISCOGS_THROTTLE_SECONDS = 1.0

_discogs_singleton = None


def _get_discogs_client():
    """Lazily build a Discogs client from DISCOGS_TOKEN."""
    global _discogs_singleton
    if _discogs_singleton is None:
        token = os.environ.get("DISCOGS_TOKEN")
        _discogs_singleton = discogs_client.Client(
            "mccoy/0.1", user_token=token
        )
    return _discogs_singleton


def _year_from_date(date: str | None) -> int | None:
    """Pull a 4-digit year out of a MusicBrainz date string."""
    if not date:
        return None
    head = date[:4]
    return int(head) if head.isdigit() else None


def mb_releases_for(name: str) -> list[dict]:
    """Resolve a musician by name and return their releases (normalized).

    Returns ``[{mbid, title, year, label}]``; ``[]`` (logged) if the
    name can't be resolved.
    """
    result = musicbrainzngs.search_artists(artist=name, limit=1)
    artists = result.get("artist-list", [])
    if not artists:
        logger.info("MusicBrainz: unresolved artist name %r", name)
        return []

    artist_mbid = artists[0]["id"]
    time.sleep(0)  # yield to the built-in rate limiter between calls
    browsed = musicbrainzngs.browse_releases(
        artist=artist_mbid, includes=["labels"], limit=100
    )
    releases = []
    for rel in browsed.get("release-list", []):
        label_info = rel.get("label-info-list") or []
        label = None
        if label_info:
            label = (label_info[0].get("label") or {}).get("name")
        releases.append(
            {
                "mbid": rel["id"],
                "title": rel.get("title", ""),
                "year": _year_from_date(rel.get("date")),
                "label": label,
            }
        )
    return releases


def mb_personnel_for(release_mbid: str) -> list[dict]:
    """Return the performers credited on a release (normalized).

    Returns ``[{mbid, name, instrument}]`` from the release's
    artist-relation list.
    """
    result = musicbrainzngs.get_release_by_id(
        release_mbid, includes=["artist-rels"]
    )
    release = result.get("release", {})
    personnel = []
    for rel in release.get("artist-relation-list", []):
        artist = rel.get("artist")
        if not artist:
            continue
        attrs = rel.get("attribute-list") or []
        instrument = attrs[0] if attrs else rel.get("type")
        personnel.append(
            {
                "mbid": artist["id"],
                "name": artist.get("name", ""),
                "instrument": instrument,
            }
        )
    return personnel


# Discogs credit roles that are not performing musicians — dropped so
# the network is players, not cover designers / engineers / labels.
_NON_PERFORMER_ROLES = {
    "recorded by",
    "engineer",
    "mixed by",
    "mastered by",
    "remastered by",
    "lacquer cut by",
    "design",
    "artwork",
    "artwork by",
    "photography",
    "photography by",
    "liner notes",
    "notes",
    "producer",
    "executive-producer",
    "executive producer",
    "co-producer",
    "reissue producer",
    "supervised by",
    "coordinator",
    "management",
    "other",
}


def _clean_role(role: str) -> str:
    """First listed instrument from a Discogs role string."""
    return role.split(",")[0].strip() if role else ""


def _is_performer(role: str) -> bool:
    return _clean_role(role).lower() not in _NON_PERFORMER_ROLES


def discogs_releases_for(name: str, client=None, limit: int = 40) -> list[dict]:
    """Resolve an artist by name; return up to ``limit`` of their releases.

    Returns ``[{discogs_id, title, year, label}]`` (releases only, not
    masters); ``[]`` (logged) if the name can't be resolved.
    """
    client = client or _get_discogs_client()
    results = client.search(name, type="artist")
    try:
        artist = results[0]
    except (IndexError, KeyError):
        logger.info("Discogs: unresolved artist name %r", name)
        return []

    releases = []
    for item in artist.releases:
        data = item.data
        if data.get("type") != "release":
            continue  # skip masters; we want a concrete release + credits
        releases.append(
            {
                "discogs_id": str(data["id"]),
                "title": data.get("title", ""),
                "year": data.get("year") or None,
                "label": data.get("label"),
            }
        )
        if len(releases) >= limit:
            break
    return releases


def discogs_personnel_for(release_id, client=None) -> list[dict]:
    """Return the performing musicians on a Discogs release.

    Returns ``[{discogs_id, name, instrument}]`` from the main artists
    plus the ``extraartists`` liner credits, filtered to performers.
    ``[]`` (logged) if the release can't be fetched.
    """
    client = client or _get_discogs_client()
    try:
        data = client.release(release_id).data
    except Exception as exc:  # unresolved / network / rate-limit
        logger.info("Discogs: could not fetch release %s: %s", release_id, exc)
        return []
    finally:
        time.sleep(DISCOGS_THROTTLE_SECONDS)

    personnel = []
    seen = set()
    for artist in (data.get("artists") or []) + (
        data.get("extraartists") or []
    ):
        role = artist.get("role") or ""
        if not _is_performer(role):
            continue
        discogs_id = str(artist.get("id"))
        if discogs_id in seen:
            continue
        seen.add(discogs_id)
        personnel.append(
            {
                "discogs_id": discogs_id,
                "name": artist.get("name", ""),
                "instrument": _clean_role(role) or None,
            }
        )
    return personnel
