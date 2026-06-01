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

## Production smoke test

1. Open the deployed app.
2. Log in with Spotify to save a refresh token.
3. Manually trigger the cron service once in Railway.
4. Confirm Railway logs include saved snapshots for all three time ranges.
5. Open the Trends tab and verify the bump chart renders after at least two
   snapshots exist.
