-- Music Network Visualization — genre dimension.
-- Capture Discogs style tags per release and a derived dominant genre
-- per musician, so the /network page can color/filter by genre.

ALTER TABLE nv_releases
    ADD COLUMN IF NOT EXISTS styles TEXT[];

ALTER TABLE nv_musicians
    ADD COLUMN IF NOT EXISTS primary_genre TEXT;
