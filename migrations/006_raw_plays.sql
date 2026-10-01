-- Play-history pipeline: raw layer + run log (Group WW).
-- raw_plays is append-only and untyped beyond its keys; modeling
-- happens in dbt (analytics/). The (played_at, track_id) key makes the
-- hourly ingest idempotent.
CREATE TABLE IF NOT EXISTS raw_plays (
    played_at   TIMESTAMPTZ NOT NULL,
    track_id    TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (played_at, track_id)
);

-- One row per pipeline job run, success or failure.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            SERIAL PRIMARY KEY,
    job           TEXT        NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        TEXT        NOT NULL
        CHECK (status IN ('running', 'success', 'failed')),
    rows_fetched  INTEGER,
    rows_inserted INTEGER,
    error         TEXT
);
