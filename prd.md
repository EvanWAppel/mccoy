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
- Historical data storage / long-term trend tracking beyond Spotify's native windows
- Recently played tracks
- Currently playing / now-playing widget
- Playlist analysis
- Custom domain
- Mobile-optimized layout (desktop first)
