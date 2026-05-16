import os
import pytest
import spotipy
from unittest.mock import patch, MagicMock
from auth import get_auth_url, get_sp_from_session


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

    def test_url_contains_redirect_uri(self):
        url = get_auth_url()
        assert "localhost" in url or "redirect_uri" in url


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
