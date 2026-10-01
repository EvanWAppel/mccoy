"""Group WW — hourly recently-played ingest into raw_plays."""
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import psycopg2
import pytest

import db
from ingest_plays import PAGE_LIMIT, fetch_recent_plays, run_ingest


def _rows(dsn, sql):
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


WATERMARK = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)


def _full_page(recently_played, oldest):
    """A 50-item page whose oldest play is at ``oldest``."""
    item = recently_played["items"][0]
    items = [dict(item) for _ in range(PAGE_LIMIT - 1)]
    items.append(dict(item, played_at=oldest))
    return dict(recently_played, items=items)


def _execute(dsn, sql):
    conn = psycopg2.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


class TestFetchRecentPlays:
    def test_always_fetches_latest_page(self, recently_played):
        sp = MagicMock()
        sp.current_user_recently_played.return_value = recently_played
        items = fetch_recent_plays(sp, WATERMARK)
        sp.current_user_recently_played.assert_called_once_with(limit=50)
        assert items == recently_played["items"]

    def test_first_run_fetches_latest_page(self, recently_played):
        sp = MagicMock()
        sp.current_user_recently_played.return_value = recently_played
        fetch_recent_plays(sp, None)
        sp.current_user_recently_played.assert_called_once_with(limit=50)

    def test_warns_when_full_page_misses_watermark(
        self, recently_played, caplog
    ):
        page = _full_page(recently_played, "2026-09-27T08:05:00.000Z")
        sp = MagicMock()
        sp.current_user_recently_played.return_value = page
        with caplog.at_level(logging.WARNING):
            fetch_recent_plays(sp, WATERMARK)
        assert "possible gap" in caplog.text

    def test_no_warning_when_full_page_overlaps_watermark(
        self, recently_played, caplog
    ):
        page = _full_page(recently_played, "2026-09-27T07:55:00.000Z")
        sp = MagicMock()
        sp.current_user_recently_played.return_value = page
        with caplog.at_level(logging.WARNING):
            fetch_recent_plays(sp, WATERMARK)
        assert "possible gap" not in caplog.text

    def test_no_warning_for_partial_page(self, recently_played, caplog):
        sp = MagicMock()
        sp.current_user_recently_played.return_value = recently_played
        with caplog.at_level(logging.WARNING):
            fetch_recent_plays(
                sp, datetime(2020, 1, 1, tzinfo=timezone.utc)
            )
        assert "possible gap" not in caplog.text

    def test_no_warning_on_first_run(self, recently_played, caplog):
        page = _full_page(recently_played, "2026-09-27T08:05:00.000Z")
        sp = MagicMock()
        sp.current_user_recently_played.return_value = page
        with caplog.at_level(logging.WARNING):
            fetch_recent_plays(sp, None)
        assert "possible gap" not in caplog.text


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

    def test_never_passes_after_cursor(self, pg_db, ingest_sp):
        run_ingest()
        run_ingest()
        for call in ingest_sp.current_user_recently_played.call_args_list:
            assert "after" not in call.kwargs
            assert call.kwargs == {"limit": 50}

    def test_second_run_refetch_is_harmless(self, pg_db, ingest_sp):
        run_ingest()
        run_ingest()
        runs = _rows(
            pg_db,
            "SELECT status, rows_fetched, rows_inserted "
            "FROM pipeline_runs ORDER BY id",
        )
        assert runs == [("success", 6, 5), ("success", 6, 0)]
        assert _rows(pg_db, "SELECT count(*) FROM raw_plays")[0][0] == 5

    def test_late_synced_play_is_captured(
        self, pg_db, ingest_sp, recently_played
    ):
        run_ingest()
        # An offline play syncs later, older than the stored watermark.
        late = dict(
            recently_played["items"][0],
            played_at="2026-09-27T07:30:00.000Z",
        )
        items = recently_played["items"]
        page = items[:2] + [late] + items[2:]

        def spotify(limit, after=None):
            # Like Spotify: an ``after`` cursor hides older plays.
            if after is None:
                return dict(recently_played, items=page)
            return dict(recently_played, items=[
                i for i in page
                if datetime.fromisoformat(i["played_at"]).timestamp()
                * 1000 > after
            ])

        ingest_sp.current_user_recently_played.side_effect = spotify
        run_ingest()
        assert _rows(
            pg_db,
            "SELECT count(*) FROM raw_plays "
            "WHERE played_at = '2026-09-27T07:30:00Z'",
        )[0][0] == 1
        assert _rows(
            pg_db,
            "SELECT rows_inserted FROM pipeline_runs ORDER BY id DESC",
        )[0][0] == 1

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

    def test_last_dbt_status_reports_failed_build(self, pg_db):
        ok = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(ok, "success", 3, 3)
        good = db.start_pipeline_run("dbt_build")
        db.finish_pipeline_run(
            good, "success",
            details={"models_built": 8, "tests_passed": 19,
                     "tests_failed": 0},
        )
        bad = db.start_pipeline_run("dbt_build")
        db.finish_pipeline_run(bad, "failed", error="boom")
        health = db.get_pipeline_health()
        assert health["last_dbt_status"] == "failed"
        assert health["dbt"]["models_built"] == 8

    def test_last_dbt_status_none_without_builds(self, pg_db):
        ok = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(ok, "success", 3, 3)
        assert db.get_pipeline_health()["last_dbt_status"] is None

    def _age(self, dsn, run_id, hours):
        _execute(
            dsn,
            "UPDATE pipeline_runs SET started_at = now() - "
            f"interval '{int(hours)} hours' WHERE id = {int(run_id)}",
        )

    def test_stale_running_ingest_is_stuck(self, pg_db):
        stuck = db.start_pipeline_run("ingest_plays")
        self._age(pg_db, stuck, 3)
        health = db.get_pipeline_health()
        assert health["stuck_ingest_7d"] == 1

    def test_fresh_running_ingest_is_not_stuck(self, pg_db):
        db.start_pipeline_run("ingest_plays")
        assert db.get_pipeline_health()["stuck_ingest_7d"] == 0

    def test_finished_old_run_is_not_stuck(self, pg_db):
        ok = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(ok, "success", 3, 3)
        self._age(pg_db, ok, 3)
        assert db.get_pipeline_health()["stuck_ingest_7d"] == 0

    def test_hourly_orphans_are_all_counted(self, pg_db):
        # Review scenario: cron killed every hour; each new orphan
        # replaces the last as "latest", so latest-only checks miss it.
        ok = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(ok, "success", 3, 3)
        self._age(pg_db, ok, 30)
        for hours in range(24, 2, -1):  # 22 orphans, 3h-24h old
            self._age(pg_db, db.start_pipeline_run("ingest_plays"), hours)
        self._age(pg_db, db.start_pipeline_run("ingest_plays"), 1)
        db.start_pipeline_run("ingest_plays")  # fresh, in flight
        health = db.get_pipeline_health()
        # The 1h-old and fresh runs are still in flight, not stuck.
        assert health["stuck_ingest_7d"] == 22
        assert (health["runs_7d"], health["successes_7d"]) == (23, 1)

    def test_only_fresh_running_rows_excluded_from_7d(self, pg_db):
        ok = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(ok, "success", 3, 3)
        db.start_pipeline_run("ingest_plays")  # fresh: excluded
        health = db.get_pipeline_health()
        assert (health["runs_7d"], health["successes_7d"]) == (1, 1)

    def test_stale_running_dbt_build_is_stuck(self, pg_db):
        ok = db.start_pipeline_run("ingest_plays")
        db.finish_pipeline_run(ok, "success", 3, 3)
        self._age(pg_db, db.start_pipeline_run("dbt_build"), 3)
        db.start_pipeline_run("dbt_build")  # fresh, in flight
        assert db.get_pipeline_health()["stuck_dbt_7d"] == 1
