"""Hourly ingest: Spotify recently-played -> raw_plays (Group WW).

Spotify only exposes the last 50 plays, so this runs hourly and always
fetches that latest page -- no ``after`` cursor. Inserts are idempotent
on (played_at, track_id), so overlap with earlier runs is absorbed for
free, and plays that sync late (offline/mobile) with a played_at older
than the stored watermark are still captured as long as they are within
the last 50. If a full page's oldest play is newer than the watermark,
plays in between may be unrecoverable and a "possible gap" warning is
logged. Every run is recorded in pipeline_runs; failures are recorded
and then re-raised so the cron exits non-zero.
"""

import logging
from datetime import datetime

import db
from snapshot import _get_sp_from_token

logger = logging.getLogger(__name__)

JOB = "ingest_plays"
PAGE_LIMIT = 50


def _played_at(item: dict) -> datetime:
    return datetime.fromisoformat(item["played_at"])


def fetch_recent_plays(sp, watermark: datetime | None) -> list[dict]:
    items = sp.current_user_recently_played(limit=PAGE_LIMIT)["items"]
    logger.info(
        "fetched %d recent plays (watermark=%s)", len(items), watermark
    )
    if watermark is not None and len(items) >= PAGE_LIMIT:
        oldest = min(_played_at(item) for item in items)
        if oldest > watermark:
            # The page doesn't reach back to the last stored play:
            # anything played in between is no longer retrievable.
            logger.warning(
                "recently-played page is full (%d) and its oldest play "
                "%s is newer than watermark %s; possible gap in history",
                len(items), oldest, watermark,
            )
    return items


def run_ingest() -> None:
    run_id = db.start_pipeline_run(JOB)
    fetched = inserted = None
    try:
        refresh_token = db.get_refresh_token()
        if not refresh_token:
            raise RuntimeError(
                "no stored Spotify refresh token; log in to the app once"
            )
        sp = _get_sp_from_token(refresh_token)
        watermark = db.get_play_watermark()
        items = fetch_recent_plays(sp, watermark)
        fetched = len(items)
        inserted = db.insert_plays(items)
    except Exception as exc:
        logger.exception("ingest_plays run %s failed", run_id)
        db.finish_pipeline_run(
            run_id, "failed", fetched, inserted, error=str(exc)
        )
        raise
    db.finish_pipeline_run(run_id, "success", fetched, inserted)
    logger.info(
        "ingest_plays run %s: fetched %s, inserted %s",
        run_id, fetched, inserted,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    run_ingest()
