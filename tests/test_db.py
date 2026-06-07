import pytest
from unittest.mock import MagicMock, patch, call
from db import (
    save_refresh_token,
    get_refresh_token,
    save_snapshot,
    get_snapshots,
    save_recent_search,
    get_recent_searches,
    clear_recent_searches,
)


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: s
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def mock_cursor(mock_conn):
    return mock_conn.cursor.return_value


class TestSaveRefreshToken:
    def test_executes_upsert(self, mock_conn, mock_cursor):
        with patch("db.get_connection", return_value=mock_conn):
            save_refresh_token("my_refresh_token")
        mock_cursor.execute.assert_called_once()
        sql, params = mock_cursor.execute.call_args[0]
        assert "stored_token" in sql
        assert "my_refresh_token" in params

    def test_commits(self, mock_conn):
        with patch("db.get_connection", return_value=mock_conn):
            save_refresh_token("tok")
        mock_conn.commit.assert_called_once()


class TestGetRefreshToken:
    def test_returns_token_when_row_exists(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = ("abc123",)
        with patch("db.get_connection", return_value=mock_conn):
            result = get_refresh_token()
        assert result == "abc123"

    def test_returns_none_when_no_row(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with patch("db.get_connection", return_value=mock_conn):
            result = get_refresh_token()
        assert result is None


class TestSaveSnapshot:
    def test_returns_snapshot_id(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (42,)
        with patch("db.get_connection", return_value=mock_conn):
            result = save_snapshot("short_term", [])
        assert result == 42

    def test_inserts_snapshot_row(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (1,)
        with patch("db.get_connection", return_value=mock_conn):
            save_snapshot("short_term", [])
        first_call_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "snapshots" in first_call_sql

    def test_inserts_artist_rows(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (1,)
        artists = [
            {"name": "Radiohead", "artist_id": "abc", "rank": 1, "image_url": None, "genres": ["art rock"]},
            {"name": "Portishead", "artist_id": "def", "rank": 2, "image_url": None, "genres": ["trip hop"]},
        ]
        with patch("db.get_connection", return_value=mock_conn):
            save_snapshot("short_term", artists)
        # Should have at least one executemany or multiple execute calls for artists
        total_calls = mock_cursor.execute.call_count + mock_cursor.executemany.call_count
        assert total_calls >= 2

    def test_commits(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (1,)
        with patch("db.get_connection", return_value=mock_conn):
            save_snapshot("short_term", [])
        mock_conn.commit.assert_called_once()


class TestGetSnapshots:
    def test_returns_list(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            result = get_snapshots("short_term")
        assert isinstance(result, list)

    def test_empty_when_no_rows(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            result = get_snapshots("short_term")
        assert result == []

    def test_result_has_required_keys(self, mock_conn, mock_cursor):
        from datetime import datetime, timezone
        mock_cursor.fetchall.return_value = [
            (1, datetime(2025, 1, 1, tzinfo=timezone.utc), "short_term",
             1, "Radiohead", "abc", None, ["art rock"]),
        ]
        with patch("db.get_connection", return_value=mock_conn):
            result = get_snapshots("short_term")
        assert len(result) == 1
        snap = result[0]
        assert "snapshot_id" in snap
        assert "captured_at" in snap
        assert snap["time_range"] == "short_term"
        assert "artists" in snap

    def test_artists_nested_correctly(self, mock_conn, mock_cursor):
        from datetime import datetime, timezone
        mock_cursor.fetchall.return_value = [
            (1, datetime(2025, 1, 1, tzinfo=timezone.utc), "short_term",
             1, "Radiohead", "abc", "http://img.jpg", ["art rock"]),
            (1, datetime(2025, 1, 1, tzinfo=timezone.utc), "short_term",
             2, "Portishead", "def", None, ["trip hop"]),
        ]
        with patch("db.get_connection", return_value=mock_conn):
            result = get_snapshots("short_term")
        # Both rows share snapshot_id=1, so should collapse to 1 snapshot with 2 artists
        assert len(result) == 1
        assert len(result[0]["artists"]) == 2


class TestSaveRecentSearch:
    def test_executes_upsert(self, mock_conn, mock_cursor):
        with patch("db.get_connection", return_value=mock_conn):
            save_recent_search("user1", "indie")
        mock_cursor.execute.assert_called_once()
        sql, params = mock_cursor.execute.call_args[0]
        assert "recent_searches" in sql
        assert "ON CONFLICT" in sql.upper()
        assert params == ("user1", "indie")

    def test_commits(self, mock_conn):
        with patch("db.get_connection", return_value=mock_conn):
            save_recent_search("u1", "q1")
        mock_conn.commit.assert_called_once()


class TestGetRecentSearches:
    def test_returns_list_of_query_strings(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = [("indie",), ("jazz",)]
        with patch("db.get_connection", return_value=mock_conn):
            result = get_recent_searches("user1")
        assert result == ["indie", "jazz"]

    def test_returns_empty_when_no_rows(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            result = get_recent_searches("ghost")
        assert result == []

    def test_default_limit_is_5(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            get_recent_searches("u1")
        _, params = mock_cursor.execute.call_args[0]
        assert params == ("u1", 5)

    def test_custom_limit_passed_through(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            get_recent_searches("u1", limit=10)
        _, params = mock_cursor.execute.call_args[0]
        assert params == ("u1", 10)

    def test_orders_by_searched_at_desc(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("db.get_connection", return_value=mock_conn):
            get_recent_searches("u1")
        sql, _ = mock_cursor.execute.call_args[0]
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()
        assert "recent_searches" in sql


class TestClearRecentSearches:
    def test_deletes_for_user(self, mock_conn, mock_cursor):
        with patch("db.get_connection", return_value=mock_conn):
            clear_recent_searches("user1")
        sql, params = mock_cursor.execute.call_args[0]
        assert "DELETE" in sql.upper()
        assert "recent_searches" in sql
        assert params == ("user1",)

    def test_commits(self, mock_conn):
        with patch("db.get_connection", return_value=mock_conn):
            clear_recent_searches("u1")
        mock_conn.commit.assert_called_once()
