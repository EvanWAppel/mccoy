"""Create a Spotify playlist from a curated JSON tracklist.

Personal tool. Reads a tracklist file (see tracklists/*.json), resolves
each entry against Spotify search, shows what matched and what didn't,
asks for confirmation, then creates a private playlist on your account
and adds the tracks.

Usage:
    uv run python playlist_cli.py tracklists/smoky_late_night_hard_bop.json

Auth uses the same SPOTIPY_* env vars and scopes as the web app
(auth.py). First run opens a browser once to grant scopes, then caches
a token to .cache so you won't log in again.
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from auth import SCOPE

logger = logging.getLogger(__name__)

# Dedicated app for this CLI (kept separate from the web app's
# SPOTIPY_* credentials so its read-only sandbox app is untouched).
# Set these in .env to use a writable app you own:
#   PLAYLIST_CLIENT_ID, PLAYLIST_CLIENT_SECRET, PLAYLIST_REDIRECT_URI
PLAYLIST_CACHE_PATH = ".cache-playlist"

# Spotify caps add-items at 100 URIs per request.
ADD_ITEMS_CHUNK = 100
# Keep search small; Spotify has returned 400 for large limits on some
# search types (see spotify.py), so stay conservative.
SEARCH_LIMIT = 5


@dataclass
class Track:
    artist: str
    title: str
    album: str | None = None


@dataclass
class Match:
    track: Track
    uri: str
    resolved_artist: str
    resolved_title: str
    resolved_album: str


def build_user_client() -> spotipy.Spotify:
    """A user-authorized client.

    If a dedicated writable app is configured (PLAYLIST_* env vars),
    use it with its own local-server OAuth + token cache: a one-time
    browser consent on first run, cached to .cache-playlist after.

    Otherwise fall back to the web app's stored refresh token
    (auth.py -> db.save_refresh_token). Note that app is a read-only
    sandbox and cannot create playlists.
    """
    if os.environ.get("PLAYLIST_CLIENT_ID"):
        logger.info("Using dedicated PLAYLIST_* app (browser consent once)")
        auth_manager = SpotifyOAuth(
            client_id=os.environ["PLAYLIST_CLIENT_ID"],
            client_secret=os.environ["PLAYLIST_CLIENT_SECRET"],
            redirect_uri=os.environ["PLAYLIST_REDIRECT_URI"],
            scope=SCOPE,
            open_browser=True,
            cache_path=PLAYLIST_CACHE_PATH,
        )
        return spotipy.Spotify(auth_manager=auth_manager)

    logger.info("PLAYLIST_* app not set; using web-app stored token")
    oauth = SpotifyOAuth(scope=SCOPE, open_browser=True)
    try:
        import db

        refresh_token = db.get_refresh_token()
    except Exception as e:  # noqa: BLE001 - DB is optional for the CLI
        logger.warning("Could not read stored refresh token: %s", e)
        refresh_token = None

    if refresh_token:
        logger.info("Using stored user refresh token (no browser login)")
        token = oauth.refresh_access_token(refresh_token)
        return spotipy.Spotify(auth=token["access_token"])

    logger.info("No stored token; falling back to browser login")
    return spotipy.Spotify(auth_manager=oauth)


def load_tracklist(path: str) -> tuple[str, str, list[Track]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    name = data["name"]
    description = data.get("description", "")
    tracks = [
        Track(
            artist=t["artist"],
            title=t["title"],
            album=t.get("album"),
        )
        for t in data["tracks"]
    ]
    return name, description, tracks


def _first_track(response: dict) -> dict | None:
    items = response.get("tracks", {}).get("items", [])
    return items[0] if items else None


def resolve_track(sp: spotipy.Spotify, track: Track) -> Match | None:
    """Search Spotify for a track. Tries an album-constrained query
    first (more precise), then falls back to artist+title."""
    queries = []
    if track.album:
        queries.append(
            f'track:"{track.title}" artist:"{track.artist}" '
            f'album:"{track.album}"'
        )
    queries.append(f'track:"{track.title}" artist:"{track.artist}"')

    for query in queries:
        logger.info("Searching: %s", query)
        response = sp.search(q=query, type="track", limit=SEARCH_LIMIT)
        item = _first_track(response)
        if item is not None:
            artists = ", ".join(a["name"] for a in item.get("artists", []))
            return Match(
                track=track,
                uri=item["uri"],
                resolved_artist=artists,
                resolved_title=item["name"],
                resolved_album=item.get("album", {}).get("name", ""),
            )
    return None


def resolve_all(
    sp: spotipy.Spotify, tracks: list[Track]
) -> tuple[list[Match], list[Track]]:
    matched: list[Match] = []
    missing: list[Track] = []
    for track in tracks:
        match = resolve_track(sp, track)
        if match is None:
            missing.append(track)
        else:
            matched.append(match)
    return matched, missing


def print_report(matched: list[Match], missing: list[Track]) -> None:
    print(f"\nMatched {len(matched)} track(s):")
    for i, m in enumerate(matched, start=1):
        print(
            f"  {i:>2}. {m.resolved_artist} — {m.resolved_title}"
            f"  [{m.resolved_album}]"
        )
    if missing:
        print(f"\nCould NOT find {len(missing)} track(s):")
        for t in missing:
            album = f" [{t.album}]" if t.album else ""
            print(f"   - {t.artist} — {t.title}{album}")


def confirm(prompt: str) -> bool:
    answer = input(f"\n{prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def create_playlist_with_tracks(
    sp: spotipy.Spotify,
    name: str,
    description: str,
    matched: list[Match],
) -> str:
    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,
        description=description,
    )
    playlist_id = playlist["id"]
    uris = [m.uri for m in matched]
    for chunk in _chunks(uris, ADD_ITEMS_CHUNK):
        sp.playlist_add_items(playlist_id, chunk)
        logger.info("Added %d tracks", len(chunk))
    return playlist["external_urls"]["spotify"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tracklist", help="Path to a tracklist JSON file"
    )
    parser.add_argument(
        "--name",
        help="Override the playlist name from the tracklist file",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()

    name, description, tracks = load_tracklist(args.tracklist)
    if args.name:
        name = args.name
    print(f"Playlist: {name}")
    print(f"Tracklist: {len(tracks)} track(s) from {args.tracklist}")

    sp = build_user_client()
    matched, missing = resolve_all(sp, tracks)
    print_report(matched, missing)

    if not matched:
        print("\nNothing resolved — not creating an empty playlist.")
        return 1

    if not args.yes and not confirm(
        f"Create private playlist '{name}' with {len(matched)} track(s)?"
    ):
        print("Aborted. No playlist created.")
        return 0

    url = create_playlist_with_tracks(sp, name, description, matched)
    print(f"\nCreated: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
