from collections import Counter


def get_top_artists(sp, time_range: str) -> list[dict]:
    response = sp.current_user_top_artists(limit=10, time_range=time_range)
    artists = []
    for rank, item in enumerate(response["items"], start=1):
        images = item.get("images", [])
        artists.append({
            "name": item["name"],
            "image_url": images[0]["url"] if images else None,
            "rank": rank,
            "genres": item.get("genres", []),
        })
    return artists


def get_user_profile(sp) -> dict:
    data = sp.current_user()
    images = data.get("images", [])
    return {
        "display_name": data.get("display_name", ""),
        "avatar_url": images[0]["url"] if images else None,
    }


def aggregate_genres(artists: list[dict]) -> list[dict]:
    counter: Counter = Counter()
    for artist in artists:
        for genre in artist.get("genres", []):
            counter[genre] += 1
    return [
        {"genre": genre, "count": count}
        for genre, count in counter.most_common(20)
    ]
