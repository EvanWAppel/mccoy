"""Group II — public (logged-out) shell + read-only Stats demo.

These exercise the layout/branch logic in app.render_page and the
public Stats callback. The owner (logged-in) path must stay intact.
"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("FLASK_SECRET_KEY", "test_secret")

import app as app_module  # noqa: E402


def _find_id(node, target):
    """Walk a Dash component tree looking for a component with id."""
    if node is None:
        return False
    if getattr(node, "id", None) == target:
        return True
    children = getattr(node, "children", None)
    if children is None:
        return False
    if not isinstance(children, (list, tuple)):
        children = [children]
    return any(_find_id(c, target) for c in children)


class TestRenderPageLoggedOut:
    def test_renders_demo_about_shell(self):
        with patch.object(app_module.flask, "session", {}):
            tree = app_module.render_page("/")
        assert _find_id(tree, "public-tabs")

    def test_is_not_the_login_page(self):
        with patch.object(app_module.flask, "session", {}):
            tree = app_module.render_page("/")
        assert tree is not app_module.LOGIN_PAGE

    def test_has_connect_spotify_link(self):
        with patch.object(app_module.flask, "session", {}):
            tree = app_module.render_page("/")
        assert "/login" in str(tree)

    def test_demo_tab_is_default(self):
        with patch.object(app_module.flask, "session", {}):
            tree = app_module.render_page("/")
        # the top-level tabs default to the demo value
        assert "demo" in str(tree)


class TestRenderPageLoggedInUnchanged:
    def test_owner_still_sees_mode_switcher(self):
        sp = MagicMock()
        with patch.object(
            app_module.flask, "session", {"token": {"access_token": "x"}}
        ), patch.object(
            app_module, "get_sp_from_session", return_value=sp
        ), patch.object(
            app_module,
            "get_user_profile",
            return_value={"display_name": "Evan", "avatar_url": None,
                          "user_id": "evan"},
        ):
            tree = app_module.render_page("/")
        # owner keeps today's UI (mode-tabs), not the public shell
        assert _find_id(tree, "mode-tabs")
        assert not _find_id(tree, "public-tabs")


class TestPublicStats:
    def test_renders_grid_from_latest_snapshot(self):
        snap = {
            "snapshot_id": 1,
            "captured_at": None,
            "time_range": "short_term",
            "artists": [
                {"rank": 1, "name": "Radiohead", "artist_id": "a",
                 "image_url": None, "genres": []},
                {"rank": 2, "name": "Portishead", "artist_id": "b",
                 "image_url": None, "genres": []},
            ],
        }
        with patch.object(
            app_module.db, "get_latest_snapshot", return_value=snap
        ):
            out = app_module.render_public_stats("short_term")
        assert _find_id(out, "public-artist-grid-inner") or \
            "Radiohead" in str(out)

    def test_empty_state_when_no_snapshot(self):
        with patch.object(
            app_module.db, "get_latest_snapshot", return_value=None
        ):
            out = app_module.render_public_stats("short_term")
        assert "Radiohead" not in str(out)
        # some non-empty placeholder is rendered
        assert out is not None

    def test_uses_requested_time_range(self):
        with patch.object(
            app_module.db, "get_latest_snapshot", return_value=None
        ) as mock_latest:
            app_module.render_public_stats("medium_term")
        mock_latest.assert_called_once_with("medium_term")


class TestPublicRustleSandbox:
    def test_track_view_shows_sign_in_hint(self):
        queue = [{"name": "Song", "uri": "spotify:track:t1",
                  "album_id": "a1", "album_image_url": None,
                  "preview_url": None}]
        view = app_module._public_track_view(queue, 0)
        assert app_module.PUBLIC_SIGN_IN_HINT in str(view)

    def test_track_view_embeds_player(self):
        queue = [{"name": "Song", "uri": "spotify:track:t1",
                  "album_id": "a1", "album_image_url": None}]
        view = app_module._public_track_view(queue, 0)
        assert "open.spotify.com/embed/track/t1" in str(view)

    def test_commit_up_in_track_is_noop_with_hint(self):
        # JJ-09: 'up' (save) in the sandbox must not write — it only
        # surfaces the sign-in hint. handle_public_gesture has no add
        # path at all; assert it returns the hint and leaves nav alone.
        gesture = {"direction": "up", "ts": 1}
        queue = [{"name": "S", "uri": "spotify:track:t1",
                  "album_id": "a1"}]
        result = app_module.handle_public_gesture(
            gesture, "track", [], 0, queue, 0,
        )
        # outputs: (pl_idx, tr_queue, tr_idx, view, hint)
        hint = result[4]
        tr_idx = result[2]
        assert hint == app_module.PUBLIC_SIGN_IN_HINT
        assert tr_idx is app_module.no_update  # card did not advance

    def test_up_in_search_enters_album(self):
        # album-first: 'up' on an album card loads its tracks
        gesture = {"direction": "up", "ts": 1}
        albums = [{"id": "al1", "name": "OK Computer", "image_url": None}]
        tracks = [{"name": "Airbag", "uri": "spotify:track:x",
                   "image_url": None}]
        with patch.object(
            app_module, "get_app_token_client", return_value=MagicMock()
        ), patch.object(
            app_module, "get_album_tracks", return_value=tracks
        ):
            result = app_module.handle_public_gesture(
                gesture, "search", albums, 0, [], 0,
            )
        # (pl_idx, tr_queue, tr_idx, view, hint)
        assert result[1] == tracks
        assert result[3] == "track"

    def test_search_falls_back_to_crate_on_error(self):
        with patch.object(
            app_module, "get_app_token_client", return_value=MagicMock()
        ), patch.object(
            app_module, "search_albums", side_effect=RuntimeError("x")
        ):
            queue, idx, view, q = app_module.run_public_search("indie")
        assert queue == app_module.CURATED_CRATE

    def test_search_returns_results_on_success(self):
        fake = [{"id": "p1", "name": "Indie", "image_url": None}]
        with patch.object(
            app_module, "get_app_token_client", return_value=MagicMock()
        ), patch.object(
            app_module, "search_albums", return_value=fake
        ):
            queue, idx, view, q = app_module.run_public_search("indie")
        assert queue == fake
        assert q == "indie"


class TestPublicTrendsGating:
    def test_trends_hidden_when_under_two_snapshots(self):
        tabs = app_module._public_stats_tabs(1)
        values = [t.value for t in tabs]
        assert values == ["artists"]

    def test_trends_shown_with_two_or_more_snapshots(self):
        tabs = app_module._public_stats_tabs(2)
        values = [t.value for t in tabs]
        assert "artists" in values and "trends" in values

    def test_content_toggle_shows_trends(self):
        artists_style, trends_style = app_module.toggle_public_content(
            "trends"
        )
        assert trends_style == {"display": "block"}
        assert artists_style == {"display": "none"}

    def test_content_toggle_defaults_to_artists(self):
        artists_style, trends_style = app_module.toggle_public_content(
            "artists"
        )
        assert artists_style == {"display": "block"}
        assert trends_style == {"display": "none"}


class TestPublicTabToggle:
    def test_demo_visible_about_hidden(self):
        demo_style, about_style = app_module.toggle_public_tabs("demo")
        assert demo_style == {"display": "block"}
        assert about_style == {"display": "none"}

    def test_about_visible_demo_hidden(self):
        demo_style, about_style = app_module.toggle_public_tabs("about")
        assert demo_style == {"display": "none"}
        assert about_style == {"display": "block"}
