"""Group II — public (logged-out) shell + read-only Stats demo.

These exercise the layout/branch logic in app.render_page and the
public Stats callback. The owner (logged-in) path must stay intact.
"""
import os
import random
from unittest.mock import MagicMock, patch

import pytest

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
        # owner now also has the Network pane + its graph
        assert _find_id(tree, "network-wrap")
        assert _find_id(tree, "network-graph")


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

    def test_falls_back_to_demo_when_no_snapshot(self):
        # With no real snapshot, the public grid shows deterministic
        # demo data (never an empty state) so recruiters see content.
        with patch.object(
            app_module.db, "get_latest_snapshot", return_value=None
        ):
            out = app_module.render_public_stats("short_term")
        assert _find_id(out, "public-artist-grid-inner")
        assert "Radiohead" in str(out)

    def test_uses_requested_time_range(self):
        with patch.object(
            app_module.db, "get_latest_snapshot", return_value=None
        ) as mock_latest:
            app_module.render_public_stats("medium_term")
        mock_latest.assert_called_once_with("medium_term")

    def test_real_snapshot_shows_real_caption(self):
        snap = {
            "snapshot_id": 1,
            "captured_at": None,
            "time_range": "short_term",
            "artists": [
                {"rank": 1, "name": "Radiohead", "artist_id": "a",
                 "image_url": None, "genres": []},
            ],
        }
        with patch.object(
            app_module.db, "get_latest_snapshot", return_value=snap
        ):
            out = app_module.render_public_stats("short_term")
        assert app_module.PUBLIC_DATA_CAPTION in str(out)
        assert app_module.PUBLIC_DEMO_CAPTION not in str(out)

    def test_demo_fallback_shows_demo_caption(self):
        # The "real data" claim must not be shown over demo fallback data.
        with patch.object(
            app_module.db, "get_latest_snapshot", return_value=None
        ):
            out = app_module.render_public_stats("short_term")
        assert app_module.PUBLIC_DEMO_CAPTION in str(out)
        assert app_module.PUBLIC_DATA_CAPTION not in str(out)


class TestPublicTrends:
    def test_falls_back_to_demo_when_no_snapshots(self):
        # Demo provides >=2 snapshots, so a real bump chart renders
        # instead of the "first snapshot" empty state.
        with patch.object(
            app_module.db, "get_snapshots", return_value=[]
        ):
            out = app_module.render_public_trends("trends")
        assert out is not None
        assert "First snapshot captured" not in str(out)


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

    def test_search_falls_back_to_crate_on_token_error(self):
        # Task 5: a failing client-credentials *token call* must degrade
        # to the curated crate too, not throw to the recruiter's screen.
        with patch.object(
            app_module, "get_app_token_client",
            side_effect=RuntimeError("token endpoint down"),
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
        assert values == ["artists", "patterns"]

    def test_trends_shown_with_two_or_more_snapshots(self):
        tabs = app_module._public_stats_tabs(2)
        values = [t.value for t in tabs]
        assert values == ["artists", "trends", "patterns"]

    def test_content_toggle_shows_trends(self):
        artists, trends, patterns = app_module.toggle_public_content(
            "trends"
        )
        assert trends == {"display": "block"}
        assert artists == patterns == {"display": "none"}

    def test_content_toggle_shows_patterns(self):
        artists, trends, patterns = app_module.toggle_public_content(
            "patterns"
        )
        assert patterns == {"display": "block"}
        assert artists == trends == {"display": "none"}

    def test_content_toggle_defaults_to_artists(self):
        artists, trends, patterns = app_module.toggle_public_content(
            "artists"
        )
        assert artists == {"display": "block"}
        assert trends == patterns == {"display": "none"}

    def test_public_patterns_never_reads_marts(self, mocker):
        # Evan's choice: logged-out visitors only ever see demo data.
        spy = mocker.patch.object(app_module.db, "get_listening_patterns")
        with patch.object(app_module.flask, "session", {}):
            tree = app_module.render_page("/")
        assert _find_id(tree, "public-stats-patterns")
        spy.assert_not_called()


class TestOwnerPatterns:
    @pytest.fixture(autouse=True)
    def owner_session(self, owner_env, mocker):
        mocker.patch.object(
            app_module, "get_sp_from_session", return_value=MagicMock()
        )
        mocker.patch.object(
            app_module.flask, "session", {"spotify_user_id": owner_env}
        )

    def test_patterns_tab_reads_marts(self, mocker):
        mocker.patch.object(
            app_module.db, "get_listening_patterns",
            return_value=app_module.demo_data.demo_patterns(),
        )
        tree = app_module.update_content("short_term", "patterns")
        assert _find_id(tree, "patterns-heatmap")

    def test_patterns_tab_when_pipeline_never_ran(self, mocker):
        mocker.patch.object(
            app_module.db, "get_listening_patterns",
            side_effect=RuntimeError('relation "marts.fct_plays" missing'),
        )
        tree = app_module.update_content("short_term", "patterns")
        assert "pipeline" in repr(tree).lower()


class TestNonOwnerPatterns:
    PRIVATE = "Listening patterns are private to the site owner."

    @pytest.fixture(autouse=True)
    def logged_in(self, owner_env, mocker):
        mocker.patch.object(
            app_module, "get_sp_from_session", return_value=MagicMock()
        )

    @pytest.mark.parametrize(
        "session", [{"spotify_user_id": "intruder"}, {}]
    )
    def test_non_owner_sees_private_message(self, mocker, session):
        mocker.patch.object(app_module.flask, "session", session)
        spy = mocker.patch.object(app_module.db, "get_listening_patterns")
        tree = app_module.update_content("short_term", "patterns")
        assert self.PRIVATE in repr(tree)
        assert not _find_id(tree, "patterns-heatmap")
        spy.assert_not_called()

    def test_owner_unset_hides_patterns(self, mocker, monkeypatch):
        monkeypatch.delenv("OWNER_SPOTIFY_ID", raising=False)
        mocker.patch.object(
            app_module.flask, "session", {"spotify_user_id": "owner_id"}
        )
        spy = mocker.patch.object(app_module.db, "get_listening_patterns")
        tree = app_module.update_content("short_term", "patterns")
        assert self.PRIVATE in repr(tree)
        spy.assert_not_called()


class TestCallbackRoute:
    def test_stores_spotify_user_id_in_session(self, mocker):
        token = {"access_token": "a", "refresh_token": "r"}
        mocker.patch.object(
            app_module, "handle_callback", return_value=(token, "u123")
        )
        client = app_module.server.test_client()
        resp = client.get("/callback?code=abc")
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["token"] == token
            assert sess["spotify_user_id"] == "u123"

    def test_missing_code_redirects_home(self, mocker):
        spy = mocker.patch.object(app_module, "handle_callback")
        client = app_module.server.test_client()
        resp = client.get("/callback")
        assert resp.status_code == 302
        spy.assert_not_called()


class TestOwnerModeToggle:
    def test_network_mode_shows_network_wrap(self):
        stats, rustle, rate, network = app_module.toggle_mode("network")
        assert network == {"display": "block"}
        assert stats == {"display": "none"}
        assert rustle == {"display": "none"}
        assert rate == {"display": "none"}

    def test_stats_mode_hides_network_wrap(self):
        stats, rustle, rate, network = app_module.toggle_mode("stats")
        assert stats == {"display": "block"}
        assert network == {"display": "none"}


class TestPublicTabToggle:
    def test_demo_visible_about_hidden(self):
        demo, about, network = app_module.toggle_public_tabs("demo")
        assert demo == {"display": "block"}
        assert about == {"display": "none"}
        assert network == {"display": "none"}

    def test_about_visible_demo_hidden(self):
        demo, about, network = app_module.toggle_public_tabs("about")
        assert demo == {"display": "none"}
        assert about == {"display": "block"}
        assert network == {"display": "none"}

    def test_network_visible_others_hidden(self):
        demo, about, network = app_module.toggle_public_tabs("network")
        assert demo == {"display": "none"}
        assert about == {"display": "none"}
        assert network == {"display": "block"}


PATH_GRAPH = {
    "nodes": [
        {"id": 1, "name": "Lee Morgan", "era": 1956, "genre": "Jazz"},
        {"id": 2, "name": "Art Blakey", "era": 1954, "genre": "Jazz"},
        {"id": 3, "name": "Wayne Shorter", "era": 1959, "genre": "Jazz"},
        {"id": 4, "name": "Freddie Hubbard", "era": 1960, "genre": "Jazz"},
    ],
    "edges": [
        {"source": 2, "target": 1, "weight": 4,
         "sample_releases": ["Moanin'"]},
        {"source": 1, "target": 3, "weight": 2,
         "sample_releases": ["Search for the New Land"]},
        {"source": 3, "target": 4, "weight": 3,
         "sample_releases": ["Speak No Evil"]},
    ],
}
NO_FILTERS = {"era": None, "instruments": [], "min_weight": 1,
              "genres": []}


class TestNetworkPathCallback:
    def test_find_returns_chain_and_keeps_selection(self):
        result, ids, a, b = app_module.network_path_outputs(
            "network-path-find", "2", "4", NO_FILTERS, PATH_GRAPH,
            random.Random(0),
        )
        assert ids == ["2", "1", "3", "4"]
        assert (a, b) == ("2", "4")

    def test_surprise_picks_far_pair_and_fills_dropdowns(self):
        result, ids, a, b = app_module.network_path_outputs(
            "network-path-surprise", None, None, NO_FILTERS, PATH_GRAPH,
            random.Random(0),
        )
        assert len(ids) - 1 >= 3
        assert (a, b) == (ids[0], ids[-1])

    def test_filters_mark_hidden_nodes(self):
        # Era cap hides Freddie Hubbard (1960).
        filters = dict(NO_FILTERS, era=[1950, 1959])
        result, ids, _, _ = app_module.network_path_outputs(
            "network-path-find", "2", "4", filters, PATH_GRAPH,
            random.Random(0),
        )
        # Search still runs on the full graph.
        assert ids == ["2", "1", "3", "4"]
        assert "hidden by the current filters" in repr(result)
