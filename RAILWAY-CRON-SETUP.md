# Railway Cron Setup — Snapshot Job (do this away from your computer)

**Goal:** stand up the recurring job that captures your Spotify top-artists
snapshots into Postgres. Until this exists, the **Trends** tab never gets
new data — the whole feature is frozen at whatever snapshots already exist.

You can do all of this from **any computer with a browser** — you only need
to log into the Railway dashboard. No local repo, no CLI required. (An
optional CLI path is at the bottom if you prefer it.)

This is task **O-03** in `TASKS.md`.

---

## Before you start — what you need

- Access to the Railway account that hosts the **mccoy** project.
- The mccoy project already has (confirm in the dashboard):
  - a **Web** service (the Dash app), and
  - a **Postgres** database.
- You must have logged into the **live app with Spotify at least once**, so a
  refresh token is saved in the DB. If you've used the deployed app before,
  this is already done. The cron job reads that saved token — with no token,
  it logs "No refresh token found — skipping snapshot" and does nothing.

---

## Step 1 — Create the cron service

1. Open <https://railway.app> and open the **mccoy** project.
2. Click **+ New** (or **Create** / **+ Add Service**) → **GitHub Repo**.
3. Select **`EvanWAppel/mccoy`** (the same repo the web service uses).
4. Railway creates a second service from that repo. Rename it to something
   clear like **`snapshot-cron`** (Service → **Settings** → **Name**).

> You are intentionally deploying the *same repo* a second time. The web
> service runs the app; this service runs only the snapshot script on a
> schedule.

---

## Step 2 — Set the start command

In the **`snapshot-cron`** service → **Settings** → **Deploy** →
**Custom Start Command**, set:

```
python snapshot.py
```

That's the entry point defined at the bottom of `snapshot.py`
(`if __name__ == "__main__": run_snapshot()`).

---

## Step 3 — Set the cron schedule

Still in **`snapshot-cron`** → **Settings** → find **Cron Schedule** (under
Deploy). Enter:

```
0 0 * * 0
```

That's **weekly, Sunday 00:00 UTC**. This matches the app's "weekly cron"
story in the About tab and `DEPLOYMENT.md`.

> **If you'd rather snapshot daily**, use `0 0 * * *` instead (midnight UTC
> every day). Either is fine — daily just accumulates trend points faster.
> Pick one; don't set both.

**How Railway cron works:** the service stays stopped and Railway starts it
on the schedule. The script runs once, saves three snapshots (short / medium
/ long term), and exits. A clean exit is expected and correct — it is **not**
a crash. (Don't confuse this with a always-on service that Railway restarts.)

---

## Step 4 — Set environment variables

The cron service needs its own copy of these vars. In **`snapshot-cron`** →
**Variables**:

| Variable | Value |
|---|---|
| `SPOTIPY_CLIENT_ID` | same as the web service |
| `SPOTIPY_CLIENT_SECRET` | same as the web service |
| `SPOTIPY_REDIRECT_URI` | same as the web service |
| `DATABASE_URL` | reference the Postgres service |

Fastest way to get these right:

- For `DATABASE_URL`: use Railway's **variable reference** — click
  **+ New Variable** → reference the Postgres service's `DATABASE_URL`
  (e.g. `${{Postgres.DATABASE_URL}}`). This guarantees it points at the same
  DB as the web app.
- For the three `SPOTIPY_*` vars: open the **web** service's Variables in
  another tab and copy the exact values over. They must match — the refresh
  token was minted against that client ID/secret.

> `FLASK_SECRET_KEY` is **not** needed here (no web sessions in the cron job).
> `snapshot.py` reads `SPOTIPY_CLIENT_ID/SECRET/REDIRECT_URI` and `DATABASE_URL`
> only.

---

## Step 5 — Deploy and trigger a first run manually

1. Let the service build/deploy (it'll deploy automatically after you set
   the start command; if not, hit **Deploy**).
2. Trigger one run **now** instead of waiting for Sunday: in the
   `snapshot-cron` service, open the latest deployment and use
   **Run** / **Restart** / **Redeploy** to fire it once. (Railway's UI wording
   varies; any action that starts the service runs `python snapshot.py` once.)

---

## Step 6 — Verify it worked

**A. Check the logs** (`snapshot-cron` → **Deployments** → latest → **Logs**).
Success looks like three lines:

```
Saved snapshot for short_term (50 artists)
Saved snapshot for medium_term (50 artists)
Saved snapshot for long_term (50 artists)
```

Then the service exits cleanly. If you instead see
`No refresh token found — skipping snapshot`, go log into the **live app**
with Spotify once (Step 0 prerequisite), then re-trigger.

**B. Check the app.** Open the live site → **Trends** tab. The bump chart
renders once **two or more** snapshots exist for a window. If you've only
ever had one snapshot, run the cron a second time (or wait for the next
scheduled run) and it'll light up.

This closes **O-03** and unblocks **O-06** in `TASKS.md`.

---

## Troubleshooting

- **"No refresh token found — skipping snapshot"** → no one has logged into
  the deployed app with Spotify, or the token is in a *different* database
  than `DATABASE_URL` points to. Confirm the cron's `DATABASE_URL` references
  the same Postgres as the web service, then log into the live app once.
- **Auth / 401 errors in the log** → the `SPOTIPY_CLIENT_ID/SECRET` on the
  cron service don't match the ones the token was created with. Re-copy them
  from the web service exactly.
- **Service keeps restarting / looks like it "crashed"** → a cron service is
  *supposed* to run once and stop. If Railway is treating it as always-on and
  restart-looping, double-check the **Cron Schedule** field is actually set
  (Step 3) — that's what tells Railway to run-then-stop.

---

## Optional: do it from the Railway CLI instead

If you'd rather not use the dashboard (still works from any computer with the
repo and `railway` installed):

```bash
# from a machine logged into the Railway CLI, inside the mccoy project
railway login
railway link            # pick the mccoy project

# One-off manual run against the linked project's env (good for testing):
railway run python snapshot.py
```

Note: `railway run` executes once with the project's variables injected — it's
great for verifying the script, but the **recurring schedule still has to be
set on a service** (Steps 1–4). There's no pure-CLI way to create the cron
schedule; that field lives in the service settings.
