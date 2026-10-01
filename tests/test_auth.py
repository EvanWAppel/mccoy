from unittest.mock import patch

import pytest
import spotipy

from auth import (
    get_app_token_client,
    get_auth_url,
    get_sp_from_session,
    handle_callback,
    is_owner,
)


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

    def test_url_contains_play_history_scope(self):
        # Group WW: hourly recently-played ingest needs this grant.
        assert "user-read-recently-played" in get_auth_url()

    def test_url_contains_redirect_uri(self):
        url = get_auth_url()
        assert "localhost" in url or "redirect_uri" in url

    def test_url_forces_show_dialog(self):
        # Forces Spotify to show the consent dialog on every login, so
        # cached grants can't silently bypass a scope expansion.
        url = get_auth_url()
        assert "show_dialog=true" in url.lower()


class TestIsOwner:
    def test_true_when_id_matches(self, owner_env):
        assert is_owner("owner_id") is True

    def test_false_for_other_user(self, owner_env):
        assert is_owner("someone_else") is False

    def test_false_when_owner_unset(self, monkeypatch):
        # Fail closed: no configured owner means nobody is the owner.
        monkeypatch.delenv("OWNER_SPOTIFY_ID", raising=False)
        assert is_owner("owner_id") is False

    def test_false_when_owner_empty(self, monkeypatch):
        monkeypatch.setenv("OWNER_SPOTIFY_ID", "")
        assert is_owner("") is False

    def test_false_for_none_user(self, owner_env):
        assert is_owner(None) is False


class TestHandleCallback:
    TOKEN = {
        "access_token": "acc-secret",
        "refresh_token": "ref-secret",
    }

    def _run(self, user_id):
        with patch("auth._oauth_manager") as mock_oauth_manager, patch(
            "auth.spotipy.Spotify"
        ) as mock_spotify, patch("db.save_refresh_token") as mock_save:
            mock_oauth_manager.return_value.get_access_token.return_value = (
                dict(self.TOKEN)
            )
            mock_spotify.return_value.current_user.return_value = {
                "id": user_id
            }
            result = handle_callback("code")
        return result, mock_save, mock_spotify

    def test_saves_refresh_token_for_owner(self, owner_env):
        (token, user_id), mock_save, _ = self._run("owner_id")
        assert token == self.TOKEN
        assert user_id == "owner_id"
        mock_save.assert_called_once_with("ref-secret")

    def test_owner_save_failure_raises(self, owner_env):
        # The cron depends on this token; a failed save must not be
        # swallowed (house rule: don't hide errors).
        with patch("auth._oauth_manager") as mock_oauth_manager, patch(
            "auth.spotipy.Spotify"
        ) as mock_spotify, patch(
            "db.save_refresh_token",
            side_effect=RuntimeError("db down"),
        ):
            mock_oauth_manager.return_value.get_access_token.return_value = (
                dict(self.TOKEN)
            )
            mock_spotify.return_value.current_user.return_value = {
                "id": "owner_id"
            }
            with pytest.raises(RuntimeError, match="db down"):
                handle_callback("code")

    def test_looks_up_user_with_access_token(self, owner_env):
        _, _, mock_spotify = self._run("owner_id")
        mock_spotify.assert_called_once_with(auth="acc-secret")

    def test_non_owner_token_not_saved(self, owner_env, caplog):
        caplog.set_level("INFO", logger="auth")
        (token, user_id), mock_save, _ = self._run("intruder")
        assert token == self.TOKEN
        assert user_id == "intruder"
        mock_save.assert_not_called()
        assert any(
            r.levelname == "INFO" and "non-owner" in r.getMessage()
            for r in caplog.records
        )
        assert "secret" not in caplog.text

    def test_owner_unset_token_not_saved(self, monkeypatch, caplog):
        monkeypatch.delenv("OWNER_SPOTIFY_ID", raising=False)
        caplog.set_level("INFO", logger="auth")
        (_, user_id), mock_save, _ = self._run("owner_id")
        assert user_id == "owner_id"
        mock_save.assert_not_called()
        assert any(
            r.levelname == "ERROR" and "OWNER_SPOTIFY_ID" in r.getMessage()
            for r in caplog.records
        )
        assert "secret" not in caplog.text


class TestGetAppTokenClient:
    def test_returns_spotipy_client(self):
        result = get_app_token_client()
        assert isinstance(result, spotipy.Spotify)

    def test_uses_client_credentials_manager(self):
        # App-token (client-credentials) flow: no user scopes, no
        # redirect round-trip. Built from client id/secret only.
        with patch("auth.SpotifyClientCredentials") as mock_ccm:
            get_app_token_client()
        mock_ccm.assert_called_once()
        kwargs = mock_ccm.call_args.kwargs
        assert kwargs["client_id"] == "test_client_id"
        assert kwargs["client_secret"] == "test_client_secret"


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
