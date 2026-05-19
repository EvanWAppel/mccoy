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
        return {"display_name": "", "avatar_url": None}
    images = data.get("images", [])
    return {
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
