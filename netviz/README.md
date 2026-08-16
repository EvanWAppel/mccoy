# netviz — the `/network` musician graph

The `/network` page renders a graph of musicians (nodes) connected by
shared releases (edges). **It works out of the box from a committed
artifact — you do not need any data dump or API token to run it.**

## How the page gets its data

`components/network.py:load_graph()` tries the live Postgres `nv_*`
tables first and **falls back to the committed `netviz/graph.json`**
whenever the DB is empty or unreachable. So:

- A fresh clone (or a logged-out visitor on a cold deploy) renders
  straight from `graph.json`. This is the shipped artifact and the demo
  is never empty.
- If you populate the `nv_*` tables (below), the page serves that live
  graph instead.

**Rebuilding `graph.json` is optional** — only do it if you want to
change the graph's contents. Neither rebuild path runs on Railway; both
are offline jobs.

## Rebuild path A — API crawl (`ingest.py`)

Snowballs out from a curated seed list via the MusicBrainz and Discogs
APIs, writing the `nv_*` tables, then rebuilds edges.

```bash
uv run python -m netviz.ingest
```

Requires `DATABASE_URL` and, for the Discogs half, `DISCOGS_TOKEN`
(generate one at discogs.com → Settings → Developers). Bounded and
idempotent — re-running extends the cache without duplicating rows.

## Rebuild path B — Discogs monthly dump (`dumps.py`)

Builds the multi-genre atlas from a Discogs monthly *releases* dump.
This is what produced the committed `graph.json`. Two stages, split so
the slow part runs once:

```bash
# extract: stream the ~10GB dump ONCE, keep only in-scope releases
uv run python -m netviz.dumps extract <dump.xml.gz|url> data/inscope.jsonl

# build: fast, no network — tune this freely and re-run in seconds
uv run python -m netviz.dumps build data/inscope.jsonl netviz/graph.json
```

The dump download is IP-throttled by data.discogs.com, so run `extract`
locally against a file you have already downloaded. **A cloner does not
need the 9GB dump** — the committed `graph.json` already contains the
built graph.

> Note: the large local extracts (`releases.xml.gz`, `netviz/data/`) are
> gitignored and never committed. Delete them to reclaim disk once
> `graph.json` is built.
