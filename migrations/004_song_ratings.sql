-- One row per (user, distinct rated track). Re-rating a track updates
-- the score and rated_at instead of inserting a duplicate. Backs the
-- Rate feature (flip album covers → preview → tap a 1-10 scale).
CREATE TABLE IF NOT EXISTS song_ratings (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    track_uri  TEXT NOT NULL,
    title      TEXT NOT NULL,
    artist     TEXT,
    year       TEXT,
    image_url  TEXT,
    rating     INTEGER NOT NULL,
    rated_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, track_uri)
);

CREATE INDEX IF NOT EXISTS song_ratings_user_time
    ON song_ratings (user_id, rated_at DESC);
