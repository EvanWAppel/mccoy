import pytest
import spotipy
from unittest.mock import patch, MagicMock
from auth import get_auth_url, handle_callback, get_sp_from_session


@pytest.fixture(autouse=True)
def spotify_env(monkeypatch):
    monkeypatch.setenv("SPOTIPY_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("SPOTIPY_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("SPOTIPY_REDIRECT_URI", "http://localhost:8050/callback")


class TestGetAuthUrl:
    def test_returns_string(self):
        url = get_auth_url()
        assert isinstance(url, str)

    def test_url_contains_spotify_domain(self):
        url = get_auth_url()
        assert "spotify.com" in url or "accounts.spotify" in url

    def test_url_contains_scope(self):
        url = get_auth_url()
        assert "user-top-read" in url

    @pytest.mark.parametrize(
        "scope",
        [
            "playlist-read-private",
            "playlist-modify-private",
            "playlist-modify-public",
            "streaming",
            "user-read-private",
        ],
    )
    def test_url_contains_rustling_scope(self, scope):
        url = get_auth_url()
        assert scope in url

    def test_url_contains_redirect_uri(self):
        url = get_auth_url()
        assert "localhost" in url or "redirect_uri" in url


class TestHandleCallback:
    def test_saves_refresh_token(self):
        token = {"access_token": "access", "refresh_token": "refresh"}
        with patch("auth._oauth_manager") as mock_oauth_manager:
            mock_oauth_manager.return_value.get_access_token.return_value = token
            with patch("db.save_refresh_token") as mock_save:
                result = handle_callback("code")

        assert result == token
        mock_save.assert_called_once_with("refresh")


class TestGetSpFromSession:
    def test_returns_none_when_no_token(self):
        result = get_sp_from_session({})
        assert result is None

    def test_returns_none_when_token_key_missing(self):
        result = get_sp_from_session({"user": "evan"})
        assert result is None

    def test_returns_spotipy_client_with_valid_token(self, mock_token):
        session = {"token": mock_token}
        result = get_sp_from_session(session)
        assert result is not None
        assert isinstance(result, spotipy.Spotify)

    def test_clears_session_when_scope_is_insufficient(
        self, stale_scope_token
    ):
        session = {"token": stale_scope_token}
        result = get_sp_from_session(session)
        assert result is None
        assert "token" not in session

    def test_passes_when_token_scope_is_superset(self, mock_token):
        # Token granted strictly more scopes than we require — still valid
        extra = dict(mock_token)
        extra["scope"] = mock_token["scope"] + " user-read-email"
        session = {"token": extra}
        result = get_sp_from_session(session)
        assert result is not None
