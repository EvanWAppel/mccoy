import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth


SCOPE = "user-top-read"


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
    return _oauth_manager().get_access_token(code, as_dict=True)


def get_sp_from_session(session: dict):
    token = session.get("token")
    if not token:
        return None
    return spotipy.Spotify(auth=token["access_token"])
