import logging
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

SCOPE = " ".join(
    [
        "user-top-read",
        "playlist-read-private",
        "playlist-modify-private",
        "playlist-modify-public",
        "streaming",
        "user-read-private",
    ]
)


def _oauth_manager() -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
        scope=SCOPE,
    )


def get_auth_url() -> str:
    return _oauth_manager().get_authorize_url()


def handle_callback(code: str) -> dict:
    token = _oauth_manager().get_access_token(code, as_dict=True)
    refresh_token = token.get("refresh_token")
    if refresh_token:
        try:
            import db
            db.save_refresh_token(refresh_token)
        except Exception as e:
            logger.warning("Could not save refresh token to DB: %s", e)
    return token


def get_sp_from_session(session: dict):
    token = session.get("token")
    if not token:
        return None
    # H-04: attempt token refresh; redirect to login if it fails
    try:
        oauth = _oauth_manager()
        if oauth.is_token_expired(token):
            token = oauth.refresh_access_token(token["refresh_token"])
            session["token"] = token
        return spotipy.Spotify(auth=token["access_token"])
    except Exception as e:
        logger.warning("Token refresh failed, clearing session: %s", e)
        session.clear()
        return None
