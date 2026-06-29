import logging
import os

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

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
        show_dialog=True,
    )


def get_auth_url() -> str:
    return _oauth_manager().get_authorize_url()


def get_app_token_client() -> spotipy.Spotify:
    """App-level (client-credentials) client for the public Rustle
    sandbox: powers search + public reads with no user login."""
    manager = SpotifyClientCredentials(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
    )
    return spotipy.Spotify(client_credentials_manager=manager)


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
    # If the token's granted scope doesn't cover what we now require
    # (e.g. SCOPE was expanded after the user last logged in), force a
    # full re-auth so Spotify shows the consent dialog again.
    granted = set((token.get("scope") or "").split())
    required = set(SCOPE.split())
    if not required.issubset(granted):
        logger.info(
            "Session token missing scopes %s; clearing session for re-auth",
            required - granted,
        )
        session.clear()
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
