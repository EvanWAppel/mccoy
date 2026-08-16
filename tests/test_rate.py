"""Rate feature — component, db, and spotify unit tests.

Mirrors the Rustle test style: components return Dash nodes, db calls
are exercised against a mocked psycopg2 connection, and the spotify
mapper is checked against a mocked Spotipy client.
"""
from unittest.mock import patch

import pytest
from dash import dcc, html

from components.rate import (
    RATE_ALBUM_END_MESSAGE,
    RATE_SEARCH_END_MESSAGE,
    album_card,
    rate_search_bar,
    rate_sub_tabs,
    rating_card,
    rating_scale,
    ratings_table,
)
from db import RATING_SORTS, get_ratings, get_ratings_for_uris, save_rating
from spotify import get_album_rating_tracks

# --- Components ---

class TestRateComponents:
    def test_sub_tabs_has_flip_and_rated(self):
        tabs = rate_sub_tabs()
        assert isinstance(tabs, dcc.Tabs)
        values = [t.value for t in tabs.children]
        assert "flip" in values
        assert "rated" in values

    def test_search_bar_is_div_with_input(self):
        bar = rate_search_bar("jazz")
        assert isinstance(bar, html.Div)
        assert "jazz" in str(bar)

    def test_album_card_renders_name_and_art(self):
        card = album_card({"id": "a", "name": "Rumours",
                           "image_url": "http://img"})
        assert isinstance(card, html.Div)
        assert "Rumours" in str(card)
        assert "http://img" in str(card)

    def test_album_card_placeholder_when_no_art(self):
        card = album_card({"id": "a", "name": "X", "image_url": None})
        assert "placeholder" in str(card)

    def test_rating_card_shows_artist_and_year(self):
        card = rating_card(
            {"name": "Dreams", "uri": "u", "artist": "Fleetwood Mac",
             "year": "1977"}
        )
        s = str(card)
        assert "Dreams" in s
        assert "Fleetwood Mac" in s
        assert "1977" in s
        # rating track cards must NOT be the Rustle "track" card, whose
        # up-swipe triggers an "Added" stamp in assets/rustle.js.
        assert "rustle-card--track" not in s

    def test_rating_card_shows_current_score(self):
        card = rating_card({"name": "T", "uri": "u"}, current=8)
        assert "8/10" in str(card)

    def test_rating_scale_has_ten_buttons(self):
        scale = rating_scale()
        # ten numbered tap targets
        s = str(scale)
        for n in range(1, 11):
            assert f"'value': {n}" in s or f'"value": {n}' in s

    def test_rating_scale_marks_current(self):
        scale = rating_scale(current=7)
        assert "rate-scale__btn--active" in str(scale)

    def test_ratings_table_empty_state(self):
        node = ratings_table([], "rating")
        assert "No rated songs" in str(node)

    def test_ratings_table_renders_rows_and_sort_headers(self):
        ratings = [
            {"name": "Dreams", "artist": "Fleetwood Mac", "year": "1977",
             "rating": 9, "uri": "u1"},
        ]
        node = ratings_table(ratings, "rating")
        s = str(node)
        assert "Dreams" in s
        assert "9/10" in s
        # sortable headers for each dimension the issue asks for
        for label in ("Title", "Artist", "Year", "Rating"):
            assert label in s

    def test_end_messages_are_strings(self):
        assert isinstance(RATE_SEARCH_END_MESSAGE, str)
        assert isinstance(RATE_ALBUM_END_MESSAGE, str)


# --- Spotify mapper ---

class TestGetAlbumRatingTracks:
    def test_maps_tracks_with_artist_and_year(self, mock_sp):
        mock_sp.album.return_value = {
            "images": [{"url": "http://cover"}],
            "artists": [{"name": "Radiohead"}],
            "release_date": "1997-05-21",
            "tracks": {
                "items": [
                    {"name": "Airbag", "uri": "spotify:track:1",
                     "track_number": 1, "preview_url": "p1"},
                    {"name": "Paranoid Android", "uri": "spotify:track:2",
                     "track_number": 2, "preview_url": None},
                ]
            },
        }
        result = get_album_rating_tracks(mock_sp, "alb1")
        assert result[0] == {
            "name": "Airbag",
            "uri": "spotify:track:1",
            "track_number": 1,
            "image_url": "http://cover",
            "preview_url": "p1",
            "artist": "Radiohead",
            "year": "1997",
        }
        assert result[1]["artist"] == "Radiohead"
        assert result[1]["year"] == "1997"

    def test_handles_missing_artist_and_date(self, mock_sp):
        mock_sp.album.return_value = {
            "images": [],
            "tracks": {
                "items": [
                    {"name": "T", "uri": "u", "track_number": 1,
                     "preview_url": None},
                ]
            },
        }
        result = get_album_rating_tracks(mock_sp, "x")
        assert result[0]["artist"] == ""
        assert result[0]["year"] == ""
        assert result[0]["image_url"] is None

    def test_year_from_year_only_release_date(self, mock_sp):
        mock_sp.album.return_value = {
            "images": [],
            "artists": [{"name": "A"}],
            "release_date": "1969",
            "tracks": {"items": [
                {"name": "T", "uri": "u", "track_number": 1,
                 "preview_url": None},
            ]},
        }
        result = get_album_rating_tracks(mock_sp, "x")
        assert result[0]["year"] == "1969"


# --- DB ---

@pytest.fixture
def mock_conn():
    from unittest.mock import MagicMock
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: s
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def mock_cursor(mock_conn):
    return mock_conn.cursor.return_value


class TestSaveRating:
    def test_upserts_and_commits(self, mock_conn, mock_cursor):
        track = {"uri": "spotify:track:1", "name": "Dreams",
                 "artist": "Fleetwood Mac", "year": "1977",
                 "image_url": "http://img"}
        with patch("db.get_connection", return_value=mock_conn):
            save_rating("evan", track, 9)
        mock_cursor.execute.assert_called_once()
        sql, params = mock_cursor.execute.call_args[0]
        assert "song_ratings" in sql
        assert "ON CONFLICT" in sql.upper()
        assert "evan" in params
        assert "spotify:track:1" in params
        assert 9 in params
        mock_conn.commit.assert_called_once()


class TestGetRatings:
    def test_returns_mapped_dicts(self, mock_conn, mock_cursor):
        from datetime import datetime, timezone
        mock_cursor.fetchall.return_value = [
            ("u1", "Dreams", "Fleetwood Mac", "1977", None, 9,
             datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        with patch("db.get_connection", return_value=mock_conn):
            result = get_ratings("evan", "rating")
        assert result == [{
            "uri": "u1",
            "name": "Dreams",
            "artist": "Fleetwood Mac",
            "year": "1977",
            "image_url": None,
            "rating": 9,
            "rated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }]

    def test_default_sort_when_unknown_key(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            get_ratings("evan", "not-a-column")
        sql = mock_cursor.execute.call_args[0][0]
        # unknown sort keys fall back to the rating clause, never the
        # raw user input (guards against SQL injection via sort_by)
        assert RATING_SORTS["rating"] in sql
        assert "not-a-column" not in sql

    @pytest.mark.parametrize("key", ["title", "artist", "year", "rating"])
    def test_each_documented_sort_is_supported(self, mock_conn,
                                               mock_cursor, key):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            get_ratings("evan", key)
        sql = mock_cursor.execute.call_args[0][0]
        assert RATING_SORTS[key] in sql


class TestGetRatingsForUris:
    def test_empty_uris_short_circuits(self, mock_conn, mock_cursor):
        with patch("db.get_connection", return_value=mock_conn) as gc:
            result = get_ratings_for_uris("evan", [])
        assert result == {}
        gc.assert_not_called()

    def test_returns_uri_to_rating_map(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = [("u1", 8), ("u2", 3)]
        with patch("db.get_connection", return_value=mock_conn):
            result = get_ratings_for_uris("evan", ["u1", "u2"])
        assert result == {"u1": 8, "u2": 3}
