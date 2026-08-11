-- Music Network Visualization (Hard Bop) — standalone nv_* schema.
-- Decoupled from all Spotify tables. Populated offline by the netviz
-- ingest job; the /network page reads a ready-made graph.

-- One row per musician (a person)
CREATE TABLE IF NOT EXISTS nv_musicians (
    id                 SERIAL PRIMARY KEY,
    mbid               TEXT UNIQUE,       -- MusicBrainz id
    discogs_id         TEXT UNIQUE,       -- Discogs artist id (crawl key)
    name               TEXT NOT NULL,
    primary_instrument TEXT,
    active_start_year  INTEGER,           -- for era coloring
    active_end_year    INTEGER
);

-- One row per release (album / session)
CREATE TABLE IF NOT EXISTS nv_releases (
    id         SERIAL PRIMARY KEY,
    mbid       TEXT UNIQUE,
    discogs_id TEXT UNIQUE,              -- Discogs release id (crawl key)
    title      TEXT NOT NULL,
    year       INTEGER,
    label      TEXT
);

-- Raw fact: musician credited on a release
CREATE TABLE IF NOT EXISTS nv_credits (
    id          SERIAL PRIMARY KEY,
    musician_id INTEGER REFERENCES nv_musicians(id) ON DELETE CASCADE,
    release_id  INTEGER REFERENCES nv_releases(id) ON DELETE CASCADE,
    role        TEXT,                      -- instrument / producer / etc.
    UNIQUE (musician_id, release_id, role)
);

-- Precomputed musician<->musician edges (rebuilt from nv_credits)
CREATE TABLE IF NOT EXISTS nv_edges (
    id              SERIAL PRIMARY KEY,
    musician_a      INTEGER REFERENCES nv_musicians(id) ON DELETE CASCADE,
    musician_b      INTEGER REFERENCES nv_musicians(id) ON DELETE CASCADE,
    weight          INTEGER NOT NULL,      -- number of shared releases
    sample_releases TEXT[],                -- a few titles for the tooltip
    UNIQUE (musician_a, musician_b)
);

CREATE INDEX IF NOT EXISTS nv_credits_release ON nv_credits (release_id);
CREATE INDEX IF NOT EXISTS nv_credits_musician ON nv_credits (musician_id);
