"""Group WW — dbt models over the hand-built recently-played fixture.

Fixture plays (UTC -> America/Los_Angeles, PDT = UTC-7):
  Session A  Sat 2026-09-26 14:08, 14:18, 14:26 local  (t1, t2, t1)
  Session B  Sun 2026-09-27 01:07, 01:15 local         (t3, t4)
Durations: t1 491s, t2 604s, t3 433s, t4 476s.
"""
import copy
from datetime import date

import psycopg2
import pytest
from psycopg2.extensions import make_dsn

import db
from pipeline import dbt_env, run_dbt


def _query(dsn, sql):
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


@pytest.fixture
def built(pg_db, recently_played):
    """Fixture plays + one extra Shorter play next day, then dbt build."""
    items = recently_played["items"]
    extra = copy.deepcopy(next(
        i for i in items if i["track"]["id"] == "t1"
    ))
    extra["played_at"] = "2026-09-27T20:00:00.000Z"  # Sun 13:00 local
    db.insert_plays(items + [extra])
    result = run_dbt(["build"], pg_db)
    return pg_db, result


class TestDbtEnv:
    def test_maps_dsn_to_dbt_vars(self):
        env = dbt_env("postgresql://u:pw@db.example:6543/mccoy")
        assert env == {
            "DBT_HOST": "db.example",
            "DBT_PORT": "6543",
            "DBT_USER": "u",
            "DBT_PASSWORD": "pw",
            "DBT_DBNAME": "mccoy",
        }

    def test_defaults_port_and_password(self):
        env = dbt_env("postgresql://u@localhost/mccoy")
        assert env["DBT_PORT"] == "5432"
        assert env["DBT_PASSWORD"] == ""


class TestDbtBuild:
    def test_build_succeeds_and_reports_tests(self, built):
        _, result = built
        assert result["status"] == "success"
        assert result["tests_passed"] >= 10
        assert result["tests_failed"] == 0
        assert result["models_built"] == 8

    def test_sessions_split_on_gap(self, built):
        dsn, _ = built
        rows = _query(
            dsn,
            "SELECT plays, minutes FROM marts.fct_listening_sessions "
            "ORDER BY started_at",
        )
        # A: 491+604+491 s; B: 433+476 s; extra Sun play is alone.
        assert [(p, float(m)) for p, m in rows] == [
            (3, 26.43), (2, 15.15), (1, 8.18)
        ]

    def test_daily_uses_local_dates(self, built):
        dsn, _ = built
        rows = _query(
            dsn,
            "SELECT listen_date, plays, distinct_artists "
            "FROM marts.mart_daily_listening ORDER BY listen_date",
        )
        assert rows == [
            (date(2026, 9, 26), 3, 2),
            (date(2026, 9, 27), 3, 3),
        ]

    def test_hour_of_week_buckets(self, built):
        dsn, _ = built
        rows = _query(
            dsn,
            "SELECT iso_dow, hour, plays FROM marts.mart_hour_of_week "
            "ORDER BY iso_dow, hour",
        )
        assert rows == [(6, 14, 3), (7, 1, 2), (7, 13, 1)]

    def test_artist_streak_spans_consecutive_days(self, built):
        dsn, _ = built
        rows = _query(
            dsn,
            "SELECT artist_name, streak_start, streak_days "
            "FROM marts.mart_artist_streaks ORDER BY streak_days DESC, "
            "artist_name",
        )
        assert rows[0] == ("Wayne Shorter", date(2026, 9, 26), 2)
        assert all(days == 1 for _, _, days in rows[1:])

    def test_marts_live_in_marts_schema(self, built):
        dsn, _ = built
        tables = {
            t for (t,) in _query(
                dsn,
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts'",
            )
        }
        assert {
            "fct_plays", "fct_listening_sessions",
            "mart_daily_listening", "mart_hour_of_week",
            "mart_artist_streaks",
        } <= tables


class TestGetListeningPatterns:
    def test_reads_marts(self, built):
        data = db.get_listening_patterns()
        assert {"iso_dow": 6, "hour": 14, "plays": 3,
                "minutes": 26.43} in data["hour_of_week"]
        assert [d["listen_date"] for d in data["daily"]] == [
            date(2026, 9, 26), date(2026, 9, 27)
        ]
        top = data["streaks"][0]
        assert (top["artist_name"], top["streak_days"]) == (
            "Wayne Shorter", 2
        )


class TestDbtFailure:
    def test_failed_build_raises(self, pg_db):
        # Point dbt at a database that doesn't exist.
        bad = make_dsn(pg_db, dbname="no_such_db")
        with pytest.raises(RuntimeError, match="dbt build failed"):
            run_dbt(["build"], bad)


class TestRunPipeline:
    def test_records_dbt_run_with_counts(self, pg_db, mocker):
        mocker.patch("pipeline.run_ingest")
        from pipeline import run_pipeline
        run_pipeline()
        status, details = _query(
            pg_db,
            "SELECT status, details FROM pipeline_runs "
            "WHERE job = 'dbt_build'",
        )[0]
        assert status == "success"
        assert details["models_built"] == 8
        assert details["tests_failed"] == 0

    def test_dbt_failure_recorded_and_reraised(self, pg_db, mocker):
        mocker.patch("pipeline.run_ingest")
        mocker.patch(
            "pipeline.run_dbt", side_effect=RuntimeError("dbt build failed")
        )
        from pipeline import run_pipeline
        with pytest.raises(RuntimeError):
            run_pipeline()
        status, error = _query(
            pg_db,
            "SELECT status, error FROM pipeline_runs "
            "WHERE job = 'dbt_build'",
        )[0]
        assert (status, error) == ("failed", "dbt build failed")

    def test_ingest_failure_skips_dbt(self, pg_db, mocker):
        mocker.patch(
            "pipeline.run_ingest", side_effect=RuntimeError("403")
        )
        dbt = mocker.patch("pipeline.run_dbt")
        from pipeline import run_pipeline
        with pytest.raises(RuntimeError):
            run_pipeline()
        dbt.assert_not_called()
