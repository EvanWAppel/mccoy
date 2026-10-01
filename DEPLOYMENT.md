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
