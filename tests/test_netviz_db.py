from unittest.mock import patch

from netviz.db import (
    upsert_musician,
    upsert_release,
    upsert_musician_by_discogs,
    upsert_release_by_discogs,
    backfill_active_years,
    backfill_primary_genre,
    add_credit,
    replace_edges,
    get_graph,
)

# mock_conn / mock_cursor fixtures live in conftest.py


class TestUpsertMusician:
    def test_upserts_on_mbid_and_returns_id(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (7,)
        with patch("netviz.db.get_connection", return_value=mock_conn):
            result = upsert_musician(mbid="mbid-1", name="Lee Morgan")
        assert result == 7
        sql, params = mock_cursor.execute.call_args[0]
        assert "nv_musicians" in sql
        assert "ON CONFLICT" in sql.upper()
        assert "mbid-1" in params
        assert "Lee Morgan" in params

    def test_idempotent_repeat_returns_same_id(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (7,)
        with patch("netviz.db.get_connection", return_value=mock_conn):
            first = upsert_musician(mbid="mbid-1", name="Lee Morgan")
            second = upsert_musician(mbid="mbid-1", name="Lee Morgan")
        assert first == second == 7

    def test_commits(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (1,)
        with patch("netviz.db.get_connection", return_value=mock_conn):
            upsert_musician(mbid="m", name="n")
        mock_conn.commit.assert_called_once()


class TestUpsertRelease:
    def test_upserts_on_mbid_and_returns_id(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (12,)
        with patch("netviz.db.get_connection", return_value=mock_conn):
            result = upsert_release(mbid="rel-1", title="The Sidewinder")
        assert result == 12
        sql, params = mock_cursor.execute.call_args[0]
        assert "nv_releases" in sql
        assert "ON CONFLICT" in sql.upper()
        assert "rel-1" in params
        assert "The Sidewinder" in params

    def test_idempotent_repeat_returns_same_id(self, mock_conn, mock_cursor):
        mock_cursor.fetchone.return_value = (12,)
        with patch("netviz.db.get_connection", return_value=mock_conn):
            first = upsert_release(mbid="rel-1", title="The Sidewinder")
            second = upsert_release(mbid="rel-1", title="The Sidewinder")
        assert first == second == 12


class TestUpsertMusicianByDiscogs:
    def test_upserts_on_discogs_id_and_returns_id(self, mock_conn,
                                                  mock_cursor):
        mock_cursor.fetchone.return_value = (9,)
        with patch("netviz.db.get_connection", return_value=mock_conn):
            result = upsert_musician_by_discogs("200", "Joe Henderson",
                                                "Tenor Saxophone")
        assert result == 9
        sql, params = mock_cursor.execute.call_args[0]
        assert "nv_musicians" in sql
        assert "ON CONFLICT (discogs_id)" in sql
        assert params == ("200", "Joe Henderson", "Tenor Saxophone")


class TestUpsertReleaseByDiscogs:
    def test_upserts_on_discogs_id_and_returns_id(self, mock_conn,
                                                  mock_cursor):
        mock_cursor.fetchone.return_value = (14,)
        with patch("netviz.db.get_connection", return_value=mock_conn):
            result = upsert_release_by_discogs(
                "111", "The Real McCoy", 1967, "Blue Note",
                styles=["Hard Bop", "Modal"],
            )
        assert result == 14
        sql, params = mock_cursor.execute.call_args[0]
        assert "nv_releases" in sql
        assert "ON CONFLICT (discogs_id)" in sql
        assert "styles" in sql
        assert params == (
            "111", "The Real McCoy", 1967, "Blue Note",
            ["Hard Bop", "Modal"],
        )


class TestBackfillActiveYears:
    def test_runs_update_and_commits(self, mock_conn, mock_cursor):
        with patch("netviz.db.get_connection", return_value=mock_conn):
            backfill_active_years()
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE nv_musicians" in sql
        assert "MIN(r.year)" in sql
        mock_conn.commit.assert_called_once()


class TestBackfillPrimaryGenre:
    def test_aggregates_styles_and_updates_dominant_genre(
        self, mock_conn, mock_cursor
    ):
        # Musician 1 spans two releases -> Hard Bop dominates; musician
        # 2 -> Free/Avant-Garde.
        mock_cursor.fetchall.return_value = [
            (1, ["Hard Bop", "Modal"]),
            (1, ["Hard Bop"]),
            (2, ["Free Jazz"]),
        ]
        with patch("netviz.db.get_connection", return_value=mock_conn):
            backfill_primary_genre()

        sql = mock_cursor.executemany.call_args[0][0]
        updates = mock_cursor.executemany.call_args[0][1]
        assert "UPDATE nv_musicians" in sql
        assert "primary_genre" in sql
        assert set(updates) == {("Hard Bop", 1), ("Free/Avant-Garde", 2)}
        mock_conn.commit.assert_called_once()

    def test_no_styled_releases_skips_update(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        with patch("netviz.db.get_connection", return_value=mock_conn):
            backfill_primary_genre()
        mock_cursor.executemany.assert_not_called()
        mock_conn.commit.assert_called_once()


class TestAddCredit:
    def test_inserts_credit_idempotently(self, mock_conn, mock_cursor):
        with patch("netviz.db.get_connection", return_value=mock_conn):
            add_credit(musician_id=1, release_id=2, role="trumpet")
        sql, params = mock_cursor.execute.call_args[0]
        assert "nv_credits" in sql
        assert "ON CONFLICT" in sql.upper()
        assert params == (1, 2, "trumpet")

    def test_commits(self, mock_conn, mock_cursor):
        with patch("netviz.db.get_connection", return_value=mock_conn):
            add_credit(musician_id=1, release_id=2, role="trumpet")
        mock_conn.commit.assert_called_once()


class TestReplaceEdges:
    def test_clears_then_inserts(self, mock_conn, mock_cursor):
        edges = [
            {
                "musician_a": 1,
                "musician_b": 2,
                "weight": 3,
                "sample_releases": ["The Sidewinder"],
            }
        ]
        with patch("netviz.db.get_connection", return_value=mock_conn):
            replace_edges(edges)
        all_sql = " ".join(
            c[0][0] for c in mock_cursor.execute.call_args_list
        ) + " ".join(
            c[0][0] for c in mock_cursor.executemany.call_args_list
        )
        assert "DELETE" in all_sql.upper()
        assert "nv_edges" in all_sql
        mock_conn.commit.assert_called_once()


class TestGetGraph:
    def test_returns_nodes_and_edges_shape(self, mock_conn, mock_cursor):
        # First fetchall -> musicians, second -> edges.
        mock_cursor.fetchall.side_effect = [
            [
                (1, "Lee Morgan", 1956, "trumpet", "Hard Bop"),
                (2, "Art Blakey", 1954, "drums", "Hard Bop"),
            ],
            [
                (1, 2, 4, ["The Sidewinder"]),
            ],
        ]
        with patch("netviz.db.get_connection", return_value=mock_conn):
            graph = get_graph()

        assert set(graph.keys()) == {"nodes", "edges"}

        node = next(n for n in graph["nodes"] if n["id"] == 1)
        assert node["name"] == "Lee Morgan"
        assert node["era"] == 1956
        assert node["genre"] == "Hard Bop"
        assert node["degree"] == 1  # touched by one edge

        edge = graph["edges"][0]
        assert edge["source"] == 1
        assert edge["target"] == 2
        assert edge["weight"] == 4

    def test_empty_graph(self, mock_conn, mock_cursor):
        mock_cursor.fetchall.side_effect = [[], []]
        with patch("netviz.db.get_connection", return_value=mock_conn):
            graph = get_graph()
        assert graph == {"nodes": [], "edges": []}
