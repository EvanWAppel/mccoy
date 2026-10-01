# mccoy deployment runbook

## Railway services

Create or confirm these services in the same Railway project:

1. Web app service
   - Source: `EvanWAppel/mccoy`
   - Start command: uses `Procfile`
   - Environment variables:
     - `SPOTIPY_CLIENT_ID`
     - `SPOTIPY_CLIENT_SECRET`
     - `SPOTIPY_REDIRECT_URI`
     - `FLASK_SECRET_KEY`
     - `DATABASE_URL`
     - `OWNER_SPOTIFY_ID` — the owner's Spotify user id; only this
       login's refresh token is stored and sees the Patterns tab
       (unset = nobody is the owner)

2. Postgres service
   - Add a Railway PostgreSQL database to the project.
   - Reference its `DATABASE_URL` from both app services.

3. Snapshot cron service
   - Source: `EvanWAppel/mccoy`
   - Start command: `python snapshot.py`
   - Cron schedule: `0 0 * * 0`
   - Environment variables:
     - `SPOTIPY_CLIENT_ID`
     - `SPOTIPY_CLIENT_SECRET`
     - `SPOTIPY_REDIRECT_URI`
     - `DATABASE_URL`

4. Play-history pipeline cron service (Group WW)
   - Source: `EvanWAppel/mccoy`
   - Start command: `python pipeline.py`
     (hourly recently-played ingest, then `dbt build` in `analytics/`)
   - Cron schedule: `0 * * * *` (hourly — Spotify only returns the
     last 50 plays, so less often risks gaps)
   - Environment variables: same four as the snapshot cron.
   - Needs the `user-read-recently-played` grant: log in to the live
     app once after this deploys so the stored refresh token carries it.
   - Every run writes to `pipeline_runs`; a failed run exits non-zero
     and shows as "Last run failed" in the About tab's health panel.

### Owner gate: deploy order (Group WW)

1. Set `OWNER_SPOTIFY_ID` on the web service **before** deploying.
   Without it the app fails closed: no login's refresh token is saved
   and the Patterns tab is private to everyone.
2. Deploy, then **log out and log back in** as the owner. Sessions
   from before this change carry no Spotify user id, so Patterns shows
   "private to the site owner" until you re-login (it fails safe). The
   new `user-read-recently-played` scope forces this re-login anyway.
3. That owner login overwrites `stored_token`, replacing any refresh
   token a non-owner may have saved before the gate existed. If the
   pipeline ever ran before the gate, check `raw_plays` for plays that
   aren't yours (`payload->'track'` you don't recognize) and delete
   them; on a fresh deploy the table is new, so there is nothing to
   clean.
4. A failed owner refresh-token save now raises at login (error page)
   instead of being logged and ignored — check the web logs if it does.

## One-time database initialization

After Railway Postgres is attached, run the migration once against the
Railway database:

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
from db import init_db
init_db()
"
```

For local verification with Docker Postgres:

```bash
docker start mccoy-postgres
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
from db import init_db
init_db()
"
uv run python snapshot.py
```

## Pre-send liveness check

Before linking a recruiter to the live demo, confirm it is up:

```bash
uv run python scripts/check_live.py            # defaults to prod URL
uv run python scripts/check_live.py <other-url>
```

Exits 0 when the URL returns 200 and the demo's og:title marker is
present; non-zero otherwise.

## Production smoke test

1. Open the deployed app.
2. Log in with Spotify to save a refresh token.
3. Manually trigger the cron service once in Railway.
4. Confirm Railway logs include saved snapshots for all three time ranges.
5. Open the Trends tab and verify the bump chart renders after at least two
   snapshots exist.
