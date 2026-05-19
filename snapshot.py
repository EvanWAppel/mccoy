import logging
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import db
from spotify import get_top_artists

logger = logging.getLogger(__name__)

TIME_RANGES = ["short_term", "medium_term", "long_term"]


def _get_sp_from_token(refresh_token: str) -> spotipy.Spotify:
    oauth = SpotifyOAuth(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
        scope="user-top-read",
    )
    token_info = oauth.refresh_access_token(refresh_token)
    return spotipy.Spotify(auth=token_info["access_token"])


def run_snapshot() -> None:
    refresh_token = db.get_refresh_token()
    if not refresh_token:
        logger.warning("No refresh token found — skipping snapshot")
        return

    try:
        sp = _get_sp_from_token(refresh_token)
    except Exception as e:
        logger.error("Failed to get Spotify client: %s", e)
        return

    for time_range in TIME_RANGES:
        try:
            artists = get_top_artists(sp, time_range, limit=50)
            db.save_snapshot(time_range, artists)
            logger.info("Saved snapshot for %s (%d artists)", time_range, len(artists))
        except Exception as e:
            logger.error("Failed snapshot for %s: %s", time_range, e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    run_snapshot()
