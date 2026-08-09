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


def discogs_credits_for(release_id, client=None) -> list[dict]:
    """Return ``[{name, role}]`` credits for a Discogs release.

    Combines the main artists and the detailed ``extraartists`` liner
    credits. Returns ``[]`` (logged) if the release can't be fetched.
    """
    client = client or _get_discogs_client()
    try:
        data = client.release(release_id).data
    except Exception as exc:  # unresolved / network / rate-limit
        logger.info("Discogs: could not fetch release %s: %s", release_id, exc)
        return []
    finally:
        time.sleep(DISCOGS_THROTTLE_SECONDS)

    credits = []
    for artist in data.get("artists") or []:
        credits.append(
            {"name": artist.get("name", ""), "role": artist.get("role") or ""}
        )
    for artist in data.get("extraartists") or []:
        credits.append(
            {"name": artist.get("name", ""), "role": artist.get("role") or ""}
        )
    return credits
