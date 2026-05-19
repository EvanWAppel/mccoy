# mccoy — Product Requirements Document

## Overview

**mccoy** is a personal Spotify listening habits dashboard. It visualizes your top artists and genre trends across Spotify's three native time windows. Built entirely in Python using Plotly Dash, deployed on Railway.

---

## Goals

- Surface artists and genres you listen to most, across short, medium, and long time horizons
- Personal use only — single-user, no multi-tenancy
- No database — stateless, all data fetched live from Spotify on each visit

---

## Authentication

- **Flow:** Full OAuth 2.0 (Authorization Code Flow via Spotipy)
- **Library:** Spotipy
- **Token storage:** Flask session (cookie-based, server-side session secret)
- **Token refresh:** Auto-refresh silently using Spotipy's built-in refresh logic
- **Redirect URIs:**
  - Local dev: `http://localhost:8050/callback`
  - Production: `https://<app>.up.railway.app/callback`
- **Login page:** Simple login screen with a "Connect Spotify" button shown if not authenticated
- **Logout:** Clears the session, returns to login screen

### Required Spotify Scopes
- `user-top-read` — read top artists

---

## Data

### Sources
| API Call | Spotipy Method | Notes |
|---|---|---|
| Top artists | `current_user_top_artists(limit=10, time_range=...)` | Called for each of 3 time ranges |
| User profile | `current_user()` | Avatar, display name |

### Time Windows
| Label | `time_range` value |
|---|---|
| 4 Weeks | `short_term` |
| 6 Months | `medium_term` |
| All Time | `long_term` |

### Genre Aggregation
- Genres come from each artist object's `genres` list
- Aggregate by simple count: how many of the top 10 artists list each genre
- Show top 20 genres in the bar chart

---

## UI

### Layout

```
┌─────────────────────────────────────────┐
│  [●] Evan Appel                 Logout  │  ← header (avatar + name)
├─────────────────────────────────────────┤
│  [ 4 Weeks ]  [ 6 Months ]  [ All Time ]│  ← time window tabs
├─────────────────────────────────────────┤
│  [ Artists ]  [ Genres ]                │  ← content tabs
│                                         │
│  (loading spinner while fetching)       │
│                                         │
│  Artists view:                          │
│  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐             │
│  │#1│ │#2│ │#3│ │#4│ │#5│             │
│  └──┘ └──┘ └──┘ └──┘ └──┘             │
│  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐             │
│  │#6│ │#7│ │#8│ │#9│ │10│             │
│  └──┘ └──┘ └──┘ └──┘ └──┘             │
│                                         │
│  Genres view:                           │
│  indie rock        ████████████  8      │
│  alternative rock  ███████████   7      │
│  ...                                    │
└─────────────────────────────────────────┘
```

### Artist Cards
- **Count:** 10 per time window
- **Content always visible:** Artist photo, rank number (#1–#10), artist name
- **Layout:** 5-column grid (2 rows of 5)
- **Interaction:** None (display only)
- **Image source:** Spotify artist image URL

### Genre Bar Chart
- **Type:** Horizontal bar chart (Plotly)
- **Metric:** Count of top 10 artists who list that genre
- **Count:** Top 20 genres shown
- **Axis:** Genre name on Y axis, count on X axis

### Loading States
- Spinner shown while Spotify API call is in flight
- Triggered on: initial page load, time window tab switch

---

## Aesthetic

- **Theme:** Spotify-native dark
- **Background:** `#121212` (Spotify's dark background)
- **Surface:** `#1E1E1E` (cards, panels)
- **Primary text:** `#FFFFFF`
- **Secondary text:** `#B3B3B3`
- **Accent:** `#1DB954` (Spotify green — used for active tabs, bars, highlights)
- **Font:** System sans-serif (or Circular/Inter if available)

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | Plotly Dash | Python-native web UI |
| Charts | Plotly (built into Dash) | Horizontal bar + custom card layout |
| Spotify client | Spotipy | OAuth + API calls |
| Python deps | uv + `pyproject.toml` | Lockfile via `uv.lock` |
| Hosting | Railway | Persistent server, supports Flask/Dash |
| Secrets | Railway environment variables | Injected at runtime |
| CI/CD | GitHub → Railway auto-deploy | Push to `main` triggers deploy |
| Local dev | Mac, `uv run python app.py` | `.env` file for local secrets |

---

## Environment Variables

| Variable | Description |
|---|---|
| `SPOTIPY_CLIENT_ID` | Spotify app client ID |
| `SPOTIPY_CLIENT_SECRET` | Spotify app client secret |
| `SPOTIPY_REDIRECT_URI` | OAuth callback URL |
| `FLASK_SECRET_KEY` | Secret for signing Flask sessions |

---

## Project Structure (proposed)

```
mccoy/
├── app.py              # Dash app entry point, layout, callbacks
├── auth.py             # Spotipy OAuth helpers
├── spotify.py          # Spotify data fetching functions
├── components/
│   ├── header.py       # Profile header component
│   ├── artist_grid.py  # Artist card grid
│   └── genre_chart.py  # Genre bar chart
├── assets/
│   └── style.css       # Global dark theme overrides
├── pyproject.toml      # uv dependencies
├── uv.lock
├── .env.example        # Template for local env vars
├── Procfile            # Railway start command
├── prd.md              # This file
└── README.md
```

---

## Setup Steps (for implementation)

1. Create Spotify Developer app at developer.spotify.com
2. Add both redirect URIs (localhost + Railway URL) to the Spotify app settings
3. Create Railway project, link to GitHub repo
4. Set env vars in Railway dashboard
5. Push to GitHub → Railway auto-deploys

---

## Out of Scope

- Multi-user support
- Recently played tracks
- Currently playing / now-playing widget
- Playlist analysis
- Custom domain
- Mobile-optimized layout (desktop first)

---

## Feature: Listening Trends Over Time

### Overview

Store weekly snapshots of top artists and genres to visualize how listening habits change over time. Adds a Postgres database, a Railway cron job, and a new Trends tab to the UI.

### Data Collection

- **Cadence:** Weekly cron job (Railway Cron service)
- **Time windows captured per snapshot:** All three — `short_term`, `medium_term`, `long_term`
- **Artists per window:** Top 50 (Spotify API max)
- **On failure:** Skip silently, wait for next scheduled run. No alerts.
- **First snapshot:** Taken immediately when cron job is first deployed

### Authentication for Cron

- On user login via OAuth, the refresh token is automatically saved to Postgres
- Cron job reads the refresh token from DB, exchanges it for a fresh access token, fetches data, stores snapshot
- No manual steps required after first login

### Database

- **Host:** Railway Postgres (add-on in Railway dashboard)
- **ORM/client:** psycopg2 or SQLAlchemy (TBD at implementation)

#### Schema

```sql
-- Stores the user's refresh token for headless cron auth
CREATE TABLE stored_token (
    id          SERIAL PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- One row per weekly capture per time window
CREATE TABLE snapshots (
    id          SERIAL PRIMARY KEY,
    captured_at TIMESTAMPTZ DEFAULT now(),
    time_range  TEXT NOT NULL  -- 'short_term' | 'medium_term' | 'long_term'
);

-- One row per artist per snapshot
CREATE TABLE artist_entries (
    id          SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    rank        INTEGER NOT NULL,
    artist_name TEXT NOT NULL,
    artist_id   TEXT NOT NULL,  -- Spotify artist ID
    image_url   TEXT,
    genres      TEXT[]          -- Postgres array of genre strings
);
```

### Cron Job

- **Script:** `snapshot.py` — standalone Python script, not part of the Dash app
- **Schedule:** Weekly (e.g. every Sunday at midnight UTC)
- **Steps:**
  1. Read refresh token from `stored_token` table
  2. Exchange for access token via Spotipy
  3. For each of 3 time windows: fetch top 50 artists, insert `snapshot` row + 50 `artist_entry` rows
  4. On any error: log and exit cleanly (no retry)

### UI — Trends Tab

Added as a third content tab alongside **Artists** and **Genres**.

**Controlled by:** Short term (`short_term`) window only — no time window tab interaction.

#### Artist Bump Chart

- **Type:** Bump chart (rank on Y axis inverted so #1 is top, time on X axis)
- **Data:** Artist rank per weekly snapshot, short_term window
- **Artists shown:** Configurable via slider — default 10, range 5–50
- **History:** All available snapshots
- **Empty state (< 2 snapshots):** Message: *"First snapshot captured. Check back next week to see your trends."* + date of next scheduled snapshot

#### Genre Stacked Area Chart

- **Type:** Stacked area chart
- **Data:** Genre counts per weekly snapshot, short_term window (count = number of top 50 artists listing that genre)
- **Genres shown:** Top 10 by total count across all snapshots
- **History:** All available snapshots
- **Empty state:** Same friendly message as bump chart

### Updated Project Structure

```
mccoy/
├── app.py
├── auth.py
├── spotify.py
├── snapshot.py          # NEW: cron job script
├── db.py                # NEW: database connection + queries
├── components/
│   ├── header.py
│   ├── artist_grid.py
│   ├── genre_chart.py
│   └── trends.py        # NEW: bump chart + stacked area components
├── assets/style.css
├── migrations/
│   └── 001_initial.sql  # NEW: schema
├── pyproject.toml
├── Procfile
└── ...
```

### Updated Environment Variables

| Variable | Description |
|---|---|
| `SPOTIPY_CLIENT_ID` | Spotify app client ID |
| `SPOTIPY_CLIENT_SECRET` | Spotify app client secret |
| `SPOTIPY_REDIRECT_URI` | OAuth callback URL |
| `FLASK_SECRET_KEY` | Secret for signing Flask sessions |
| `DATABASE_URL` | Injected automatically by Railway Postgres |
