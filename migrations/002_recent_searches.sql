-- One row per (user, distinct search query). Re-running a query
-- updates searched_at instead of inserting a duplicate.
CREATE TABLE IF NOT EXISTS recent_searches (
    id           SERIAL PRIMARY KEY,
    user_id      TEXT NOT NULL,
    query        TEXT NOT NULL,
    searched_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, query)
);

CREATE INDEX IF NOT EXISTS recent_searches_user_time
    ON recent_searches (user_id, searched_at DESC);
