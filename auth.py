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
        "user-read-recently-played",
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


def is_owner(user_id: str | None) -> bool:
    """True only when OWNER_SPOTIFY_ID is set and equals user_id.

    Fails closed: with no configured owner, nobody is the owner.
    """
    owner_id = os.environ.get("OWNER_SPOTIFY_ID")
    return bool(owner_id) and user_id == owner_id


def handle_callback(code: str) -> tuple[dict, str]:
    """Exchange the OAuth code; return (token, spotify_user_id).

    Only the site owner's refresh token is persisted, so the hourly
    play-history cron never ingests another user's listening.
    """
    token = _oauth_manager().get_access_token(code, as_dict=True)
    profile = spotipy.Spotify(auth=token["access_token"]).current_user()
    user_id = profile["id"]
    if not is_owner(user_id):
        if os.environ.get("OWNER_SPOTIFY_ID"):
            logger.info(
                "Login by non-owner Spotify user; refresh token not saved"
            )
        else:
            logger.error(
                "OWNER_SPOTIFY_ID is unset; refresh token not saved"
            )
        return token, user_id
    refresh_token = token.get("refresh_token")
    if refresh_token:
        import db
        # Let a failed save surface: the hourly cron depends on it.
        db.save_refresh_token(refresh_token)
        logger.info("Saved owner refresh token for the cron")
    return token, user_id


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
