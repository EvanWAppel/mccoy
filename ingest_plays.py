"""Hourly ingest: Spotify recently-played -> raw_plays (Group WW).

Spotify only returns the last 50 plays, so this runs hourly and asks
for everything after the stored watermark. Inserts are idempotent on
(played_at, track_id). Every run is recorded in pipeline_runs; failures
are recorded and then re-raised so the cron exits non-zero.
"""

import logging
from datetime import datetime

import db
from snapshot import _get_sp_from_token

logger = logging.getLogger(__name__)

JOB = "ingest_plays"
PAGE_LIMIT = 50


def to_epoch_ms(ts: datetime | None) -> int | None:
    return None if ts is None else int(ts.timestamp() * 1000)


def fetch_recent_plays(sp, after_ms: int | None) -> list[dict]:
    kwargs = {"limit": PAGE_LIMIT}
    if after_ms is not None:
        kwargs["after"] = after_ms
    items = sp.current_user_recently_played(**kwargs)["items"]
    logger.info("fetched %d recent plays (after=%s)", len(items), after_ms)
    if len(items) >= PAGE_LIMIT:
        # More than a page since the last run: older plays in between
        # are no longer retrievable from Spotify.
        logger.warning(
            "recently-played page is full (%d); possible gap in history",
            len(items),
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
        items = fetch_recent_plays(sp, to_epoch_ms(watermark))
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
