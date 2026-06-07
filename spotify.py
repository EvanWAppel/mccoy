import logging
from collections import Counter

import spotipy

logger = logging.getLogger(__name__)


def get_top_artists(sp, time_range: str, limit: int = 10) -> list[dict]:
    try:
        response = sp.current_user_top_artists(limit=limit, time_range=time_range)
    except spotipy.SpotifyException as e:
        logger.error("Spotify API error in get_top_artists: %s", e)
        return []
    artists = []
    for rank, item in enumerate(response["items"], start=1):
        images = item.get("images", [])
        artists.append({
            "name": item["name"],
            "artist_id": item.get("id", ""),
            "image_url": images[0]["url"] if images else None,  # H-02
            "rank": rank,
            "genres": item.get("genres", []),  # H-03: empty list handled safely
        })
    return artists


def get_user_profile(sp) -> dict:
    try:
        data = sp.current_user()
    except spotipy.SpotifyException as e:
        logger.error("Spotify API error in get_user_profile: %s", e)
        return {"user_id": "", "display_name": "", "avatar_url": None}
    images = data.get("images", [])
    return {
        "user_id": data.get("id", ""),
        "display_name": data.get("display_name", ""),
        "avatar_url": images[0]["url"] if images else None,
    }


def aggregate_genres(artists: list[dict]) -> list[dict]:
    counter: Counter = Counter()
    for artist in artists:
        for genre in artist.get("genres", []):  # H-03: empty genres skipped
            counter[genre] += 1
    return [
        {"genre": genre, "count": count}
        for genre, count in counter.most_common(20)
    ]


def search_playlists(
    sp, query: str, limit: int = 20, offset: int = 0
) -> list[dict]:
    response = sp.search(q=query, type="playlist", limit=limit, offset=offset)
    out = []
    for item in response["playlists"]["items"]:
        if item is None:
            continue
        images = item.get("images") or []
        out.append({
            "id": item["id"],
            "name": item["name"],
            "image_url": images[0]["url"] if images else None,
        })
    return out


def _iter_pages(sp, first_page):
    page = first_page
    while page is not None:
        yield page
        page = sp.next(page) if page.get("next") else None


def get_playlist_tracks(sp, playlist_id: str) -> list[dict]:
    first = sp.playlist_items(playlist_id)
    out = []
    for page in _iter_pages(sp, first):
        for entry in page["items"]:
            track = entry.get("track")
            if track is None or track.get("uri") is None:
                continue
            album = track.get("album") or {}
            album_images = album.get("images") or []
            out.append({
                "name": track["name"],
                "uri": track["uri"],
                "album_id": album.get("id"),
                "album_name": album.get("name"),
                "album_image_url": (
                    album_images[0]["url"] if album_images else None
                ),
                "preview_url": track.get("preview_url"),
            })
    return out


def get_album_tracks(sp, album_id: str) -> list[dict]:
    album = sp.album(album_id)
    images = album.get("images") or []
    image_url = images[0]["url"] if images else None
    out = []
    for item in album["tracks"]["items"]:
        out.append({
            "name": item["name"],
            "uri": item["uri"],
            "track_number": item["track_number"],
            "duration_ms": item["duration_ms"],
            "image_url": image_url,
            "preview_url": item.get("preview_url"),
        })
    return out


def get_user_playlists(sp) -> list[dict]:
    first = sp.current_user_playlists()
    out = []
    for page in _iter_pages(sp, first):
        for p in page["items"]:
            if p is None:
                continue
            out.append({"id": p["id"], "name": p["name"]})
    return out


def create_playlist(sp, user_id: str, name: str) -> str:
    response = sp.user_playlist_create(user=user_id, name=name, public=False)
    return response["id"]


def add_track_to_playlist(sp, playlist_id: str, track_uri: str) -> None:
    sp.playlist_add_items(playlist_id, [track_uri])


def get_playlist_track_uris(sp, playlist_id: str) -> set[str]:
    first = sp.playlist_items(playlist_id)
    uris: set[str] = set()
    for page in _iter_pages(sp, first):
        for entry in page["items"]:
            track = entry.get("track")
            if track is None:
                continue
            uri = track.get("uri")
            if uri is None:
                continue
            uris.add(uri)
    return uris


def get_user_product(sp) -> str:
    return sp.current_user().get("product", "open")
