"""Marts -> parquet snapshot export (AAA-01).

The offline tests feed fixture rows through a fake connection, so they
always run. The end-to-end test exports the eval fixture marts
database (tests/evals/fixture_marts.sql) and needs TEST_DATABASE_URL
like the other Postgres tests.
"""

import datetime as dt

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import ask
from scripts import export_marts


def test_exports_one_parquet_file_per_mart(marts_conn, tmp_path):
    export_marts.export_marts(marts_conn, tmp_path)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == sorted(f"{m}.parquet" for m in ask.MARTS_SCHEMA)


def test_returns_row_counts(marts_conn, tmp_path):
    counts = export_marts.export_marts(marts_conn, tmp_path)
    assert counts == {
        "fct_plays": 2,
        "fct_listening_sessions": 1,
        "mart_daily_listening": 1,
        "mart_hour_of_week": 1,
        "mart_artist_streaks": 0,
    }


def test_columns_follow_marts_schema(marts_conn, tmp_path):
    export_marts.export_marts(marts_conn, tmp_path)
    for mart, columns in ask.MARTS_SCHEMA.items():
        table = pq.read_table(tmp_path / f"{mart}.parquet")
        assert table.column_names == [c for c, _ in columns]


def test_queries_select_named_columns_in_stable_order(marts_conn, tmp_path):
    export_marts.export_marts(marts_conn, tmp_path)
    sql = marts_conn.queries[0]
    assert "select play_id, played_at," in sql.lower()
    assert "from marts.fct_plays" in sql.lower()
    assert "order by" in sql.lower()
    assert all("*" not in q for q in marts_conn.queries)


def test_session_is_read_only(marts_conn, tmp_path):
    export_marts.export_marts(marts_conn, tmp_path)
    assert marts_conn.readonly is True


def test_types_map_from_postgres(marts_conn, tmp_path):
    export_marts.export_marts(marts_conn, tmp_path)
    plays = pq.read_table(tmp_path / "fct_plays.parquet").schema
    assert plays.field("played_at").type == pa.timestamp("us", tz="UTC")
    assert plays.field("played_at_local").type == pa.timestamp("us")
    assert plays.field("duration_ms").type == pa.int32()
    assert plays.field("session_id").type == pa.int64()
    assert plays.field("track_name").type == pa.string()
    daily = pq.read_table(tmp_path / "mart_daily_listening.parquet").schema
    assert daily.field("listen_date").type == pa.date32()
    assert daily.field("minutes").type == pa.float64()


def test_values_round_trip(marts_conn, tmp_path):
    export_marts.export_marts(marts_conn, tmp_path)
    plays = pq.read_table(tmp_path / "fct_plays.parquet").to_pylist()
    assert plays[0]["track_name"] == "Holocene"
    assert plays[0]["played_at"] == dt.datetime(
        2026, 10, 19, 4, 0, tzinfo=dt.timezone.utc
    )
    assert plays[1]["album_name"] is None
    daily = pq.read_table(tmp_path / "mart_daily_listening.parquet")
    assert daily.to_pylist() == [
        {
            "listen_date": dt.date(2026, 10, 18),
            "plays": 2,
            "minutes": 9.62,
            "distinct_artists": 2,
        }
    ]


def test_empty_mart_keeps_its_schema(marts_conn, tmp_path):
    export_marts.export_marts(marts_conn, tmp_path)
    table = pq.read_table(tmp_path / "mart_artist_streaks.parquet")
    assert table.num_rows == 0
    assert table.schema.field("streak_days").type == pa.int64()


def test_creates_missing_out_dir(marts_conn, tmp_path):
    out = tmp_path / "a" / "b"
    export_marts.export_marts(marts_conn, out)
    assert (out / "fct_plays.parquet").exists()


def test_every_schema_type_is_mapped():
    for columns in ask.MARTS_SCHEMA.values():
        for _, meaning in columns:
            assert export_marts.arrow_type(meaning) is not None


def test_unknown_type_raises():
    with pytest.raises(KeyError):
        export_marts.arrow_type("jsonb, something")


def test_db_errors_propagate(marts_conn, tmp_path, mocker):
    mocker.patch.object(
        marts_conn, "cursor", side_effect=RuntimeError("db down")
    )
    with pytest.raises(RuntimeError, match="db down"):
        export_marts.export_marts(marts_conn, tmp_path)


def test_main_uses_database_url(monkeypatch, marts_conn, tmp_path, mocker):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture")
    connect = mocker.patch.object(
        export_marts.psycopg2, "connect", return_value=marts_conn
    )
    export_marts.main(["--out", str(tmp_path)])
    connect.assert_called_once_with("postgresql://fixture")
    assert marts_conn.closed
    assert (tmp_path / "fct_plays.parquet").exists()


def test_default_out_dir_is_gitignored():
    from pathlib import Path

    root = Path(export_marts.__file__).resolve().parent.parent
    assert export_marts.DEFAULT_OUT == root / "analysis" / "data"
    assert "/analysis/data/" in (root / ".gitignore").read_text()


# --- end to end over the eval fixture marts database ---------------------


def test_exports_fixture_database(eval_db_connect, tmp_path):
    conn = eval_db_connect()
    try:
        counts = export_marts.export_marts(conn, tmp_path)
    finally:
        conn.close()
    assert counts["fct_plays"] == 10
    assert counts["fct_listening_sessions"] == 3
    plays = pq.read_table(tmp_path / "fct_plays.parquet").to_pylist()
    by_artist = {}
    for row in plays:
        name = row["primary_artist_name"]
        by_artist[name] = by_artist.get(name, 0) + 1
    assert by_artist == {
        "Bon Iver": 4,
        "Low": 3,
        "Big Thief": 2,
        "Phoebe Bridgers": 1,
    }
    sessions = pq.read_table(tmp_path / "fct_listening_sessions.parquet")
    assert sessions.column("session_id").to_pylist() == [1, 2, 3]
