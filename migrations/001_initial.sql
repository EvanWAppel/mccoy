-- Stores the user's Spotify refresh token for headless cron auth
CREATE TABLE IF NOT EXISTS stored_token (
    id            SERIAL PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- One row per weekly capture per time window
CREATE TABLE IF NOT EXISTS snapshots (
    id          SERIAL PRIMARY KEY,
    captured_at TIMESTAMPTZ DEFAULT now(),
    time_range  TEXT NOT NULL  -- 'short_term' | 'medium_term' | 'long_term'
);

-- One row per artist per snapshot
CREATE TABLE IF NOT EXISTS artist_entries (
    id          SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    rank        INTEGER NOT NULL,
    artist_name TEXT NOT NULL,
    artist_id   TEXT NOT NULL,
    image_url   TEXT,
    genres      TEXT[]
);
