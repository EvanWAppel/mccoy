"""Group WW — hourly recently-played ingest into raw_plays."""
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import psycopg2
import pytest

import db
from ingest_plays import fetch_recent_plays, run_ingest, to_epoch_ms


def _rows(dsn, sql):
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


class TestFetchRecentPlays:
    def test_passes_after_cursor(self, recently_played):
        sp = MagicMock()
        sp.current_user_recently_played.return_value = recently_played
        items = fetch_recent_plays(sp, after_ms=1790000000000)
        sp.current_user_recently_played.assert_called_once_with(
            limit=50, after=1790000000000
        )
        assert items == recently_played["items"]

    def test_omits_after_on_first_run(self, recently_played):
        sp = MagicMock()
        sp.current_user_recently_played.return_value = recently_played
        fetch_recent_plays(sp, after_ms=None)
        sp.current_user_recently_played.assert_called_once_with(limit=50)

    def test_warns_when_page_is_full(self, recently_played, caplog):
        full = dict(recently_played,
                    items=recently_played["items"][:1] * 50)
        sp = MagicMock()
        sp.current_user_recently_played.return_value = full
        with caplog.at_level(logging.WARNING):
            fetch_recent_plays(sp, after_ms=None)
        assert "possible gap" in caplog.text


class TestToEpochMs:
    def test_converts_aware_datetime(self):
        ts = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)
        assert to_epoch_ms(ts) == 1790496000000

    def test_none_passes_through(self):
        assert to_epoch_ms(None) is None


class TestPlayStorage:
    def test_watermark_empty_is_none(self, pg_db):
        assert db.get_play_watermark() is None

    def test_insert_counts_and_skips_local_files(
        self, pg_db, recently_played
    ):
        inserted = db.insert_plays(recently_played["items"])
        assert inserted == 5  # 6 items, one local file without an id
        assert _rows(pg_db, "SELECT count(*) FROM raw_plays")[0][0] == 5

    def test_insert_is_idempotent(self, pg_db, recently_played):
        db.insert_plays(recently_played["items"])
        assert db.insert_plays(recently_played["items"]) == 0
        assert _rows(pg_db, "SELECT count(*) FROM raw_plays")[0][0] == 5

    def test_payload_is_stored_raw(self, pg_db, recently_played):
        db.insert_plays(recently_played["items"])
        (name,) = _rows(
            pg_db,
            "SELECT payload->'track'->>'name' FROM raw_plays "
            "WHERE track_id = 't4'",
        )[0]
        assert name == "Maiden Voyage"

    def test_watermark_is_latest_play(self, pg_db, recently_played):
        db.insert_plays(recently_played["items"])
        assert db.get_play_watermark() == datetime(
            2026, 9, 27, 8, 15, 9, tzinfo=timezone.utc
        )


@pytest.fixture
def ingest_sp(mocker, recently_played):
    mocker.patch("ingest_plays.db.get_refresh_token", return_value="tok")
    sp = MagicMock()
    sp.current_user_recently_played.return_value = recently_played
    mocker.patch("ingest_plays._get_sp_from_token", return_value=sp)
    return sp


class TestRunIngest:
    def test_success_records_run(self, pg_db, ingest_sp):
        run_ingest()
        status, fetched, inserted, error, finished = _rows(
            pg_db,
            "SELECT status, rows_fetched, rows_inserted, error, "
            "finished_at FROM pipeline_runs",
        )[0]
        assert (status, fetched, inserted, error) == (
            "success", 6, 5, None
        )
        assert finished is not None

    def test_second_run_uses_watermark(self, pg_db, ingest_sp):
        run_ingest()
        run_ingest()
        last_call = ingest_sp.current_user_recently_played.call_args
        assert last_call.kwargs["after"] == to_epoch_ms(
            datetime(2026, 9, 27, 8, 15, 9, tzinfo=timezone.utc)
        )

    def test_failure_is_recorded_and_reraised(self, pg_db, ingest_sp):
        ingest_sp.current_user_recently_played.side_effect = RuntimeError(
            "403 insufficient scope"
        )
        with pytest.raises(RuntimeError, match="insufficient scope"):
            run_ingest()
        status, error = _rows(
            pg_db, "SELECT status, error FROM pipeline_runs"
        )[0]
        assert status == "failed"
        assert "insufficient scope" in error

    def test_missing_refresh_token_fails_loudly(self, pg_db, mocker):
        mocker.patch(
            "ingest_plays.db.get_refresh_token", return_value=None
        )
        with pytest.raises(RuntimeError, match="refresh token"):
            run_ingest()
        assert _rows(pg_db, "SELECT status FROM pipeline_runs")[0][0] == (
            "failed"
        )


class TestPipelineHealthQuery:
    def test_none_before_any_run(self, pg_db):
        assert db.get_pipeline_health() is None

    def test_summarizes_runs(self, pg_db):
        ok = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(ok, "success", 3, 3)
        bad = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(bad, "failed", error="403")
        build = db.start_pipeline_run("dbt_build")
        db.finish_pipeline_run(
            build, "success",
            details={"models_built": 8, "tests_passed": 19,
                     "tests_failed": 0},
        )
        health = db.get_pipeline_health()
        assert health["last_ingest_status"] == "failed"
        assert health["last_success_at"] is not None
        assert (health["runs_7d"], health["successes_7d"]) == (2, 1)
        assert health["dbt"]["tests_passed"] == 19
