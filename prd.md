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

(Note: the original PRD scoped this app as desktop-first. The
Rustling feature breaks that assumption — see its section below
for the mobile + desktop responsive requirements.)

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

---

## Feature: Rustling

### Overview

**Rustling** imitates a DJ flipping through crates of records to
curate a set. The user searches Spotify for playlists, swipes
through playlist cards to find one interesting, swipes through that
playlist's tracks, and can either commit a track to their target
playlist or tap into the track's parent album to swipe through every
song on it. The aesthetic is tactile, audio-first, and mobile-native.

### Information Architecture

The existing time-window + content tabs (Artists, Trends) become one
of two top-level modes. A mode switcher at the top of the app
exposes:

- **Stats** — the existing analytics UI (Artists grid + Trends tab,
  with the 4 Weeks / 6 Months / All Time time-window tabs nested
  inside).
- **Rustle** — the rustling flow described below. Time-window tabs
  are hidden in this mode (they don't apply).

```
┌────────────────────────────────────────────┐
│  [●] Evan Appel                  Logout    │
├────────────────────────────────────────────┤
│  [  STATS  ]   [ RUSTLE ]                  │ ← mode switcher
├────────────────────────────────────────────┤
│  (stats: existing UI; rustle: see below)   │
└────────────────────────────────────────────┘
```

### Surface & Responsiveness

- **Same Dash app, mobile + desktop responsive.** Touch swipes drive
  the flow on mobile; on desktop, arrow keys (← → ↑ ↓) and
  click-and-drag mirror the same gestures.
- **Mobile-first layout** inside Rustle mode. Cards center,
  full-width on phones; constrained to a max-width column on
  desktop.

### Authentication & Scopes

Rustling requires writing to playlists and (for Premium users)
streaming full tracks. Next login forces re-consent.

#### Additional Spotify Scopes

| Scope | Purpose |
|---|---|
| `playlist-read-private` | List user's own + collaborative playlists for the target picker; detect duplicate tracks |
| `playlist-modify-private` | Add tracks to private playlists |
| `playlist-modify-public` | Add tracks to public playlists |
| `streaming` | Play full tracks via Web Playback SDK (Premium fallback) |
| `user-read-private` | Detect Premium vs Free (`product` field) |

### Target Playlist Picker (modal on entry)

Every time the user enters Rustle mode, a centered modal blocks the
flow until they pick a target playlist:

- **Existing playlist:** searchable dropdown of the user's playlists
  (read via `current_user_playlists`, paginated).
- **New playlist:** "Create new…" toggles to a single name input.
  Created via `user_playlist_create(user, name, public=False)` —
  defaults to private; no description.

On selection, the modal dismisses and the rustling flow begins. The
target is held in component state only; the next Rustle session
re-asks.

### Discovery — Search & Recents

First view inside Rustle mode (after picker dismissal):

- **Search bar** at the top.
  - **Search-as-you-type, debounced ~400 ms.**
  - Calls `sp.search(q, type="playlist", limit=20)`.
- **Recent searches** (below the bar, chip row): the last 5 queries
  the user has run. Tapping a chip re-runs that search.
  - Persisted in Postgres (`recent_searches` table, per user).
  - Rolling window — when a 6th unique query is run, the oldest is
    evicted.
  - User can clear all via an X next to the chip row. No per-chip
    delete.
- **Zero results state:** "No playlists found. Try a different
  search." with the recents chip row shown below for quick pivot.

### Card Stack — Crate-of-Records Aesthetic

All three queues (playlists, tracks, album tracks) use the same
visual model:

- The top card is fully visible, square, centered.
- A few cards behind it peek at a slight forward perspective tilt,
  like records angled toward you in a crate.
- On commit/skip, the top card animates out (off-screen direction
  matches the gesture), the next card slides forward.

#### Card Content

| Card | Content |
|---|---|
| Playlist (level 1) | Cover image + playlist name |
| Track in playlist (level 2) | Album art + track name |
| Track in album drill (level 3) | Album art + track name |

All three views are visually consistent — track name as a single
line directly below the cover/art.

### Gestures

The same gesture vocabulary applies in all three card views.

| Gesture | Meaning |
|---|---|
| Swipe / drag **left or right** | Navigate to next / previous card (no commitment) |
| Swipe **up** | Commit: enter playlist (level 1) · add track to target playlist (level 2 & 3) |
| Swipe **down** | Back one level: album → track queue → playlist queue → search |
| **Tap** the album art | Drill into album (level 2 → level 3 only) |

On desktop, arrow keys mirror the swipes; click-and-drag triggers
the same commit thresholds.

### Audio — Auto-Preview

- When a card snaps into the centered position, audio begins
  automatically.
- **Premium users:** the full track plays via the Spotify Web
  Playback SDK. The SDK requires the `streaming` scope and an
  active web player device, managed by a small JS module.
- **Free users:** Spotify's 30s `preview_url` plays via a standard
  HTML `<audio>` element. If `preview_url` is null, the card is
  shown silently with a small "No preview available" note.
- **Premium fallback:** if Web Playback SDK fails to initialize
  (e.g., offline, ad-blocker), behave like a Free user.
- **iOS Safari constraint:** iOS blocks autoplay without a prior
  user gesture. The first card shown after entering Rustle mode
  displays a one-time "Tap to start" overlay; once tapped, audio
  context is unlocked and subsequent cards autoplay.
- Audio fades out and is replaced on every card transition.

### Selection — Commit Behavior

- Swipe-up on a track card calls
  `playlist_add_items(playlist_id, [track_uri])`.
- **Visual feedback:** the card animates off-screen with a brief
  "Added" stamp overlay on top. No toast. No undo.
- **Add counter chip** appears in a non-blocking corner of the
  screen (e.g., top-right): "+1 added", "+2 added", … Tapping the
  chip is out of scope for v1 (no detail view).
- **Duplicate prevention:** when entering the track queue, the
  target playlist's track URIs are fetched once via
  `playlist_items` and cached client-side. Each card checks against
  the set; if already present, the card shows an "Already added"
  badge in the corner and swipe-up no-ops with a small shake. Each
  successful add updates the cached set.

### Exhaustion / End-of-Queue

| Queue | At end of queue |
|---|---|
| Search results | Auto-load next page transparently (Spotify pagination, `offset += limit`). Hard cap at 100 results. |
| Playlist tracks | Bounce + end-of-queue card: "You've flipped through every track in this playlist. Swipe down to try another playlist." |
| Album tracks | Bounce + end-of-queue card: "End of the record. Swipe down to keep digging." |

### Session End

- **Implicit:** the user navigates away (switches to Stats, logs
  out, closes the tab). No formal end action.
- **Add counter chip** stays visible while in Rustle mode as the
  passive session indicator.
- Because the target picker re-prompts on every Rustle mode entry,
  each session is naturally self-contained.

### Database

Adds one new table to the existing Postgres schema. The
single-user assumption from `stored_token` continues — `user_id` is
denormalized for forward-compatibility but in practice always one
user.

```sql
CREATE TABLE IF NOT EXISTS recent_searches (
    id           SERIAL PRIMARY KEY,
    user_id      TEXT NOT NULL,         -- Spotify user id
    query        TEXT NOT NULL,
    searched_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recent_searches_user_time
    ON recent_searches (user_id, searched_at DESC);
```

- On each new query, insert a row (or update `searched_at` if the
  exact query already exists for this user).
- On read, return the most recent 5 distinct queries.
- On "Clear", delete all rows for this user.
- No periodic cleanup job; user-controlled.

### Tech Stack Additions

| Layer | Choice | Notes |
|---|---|---|
| Gesture handling | Custom JS in `assets/rustle.js` | Uses the Pointer Events API; communicates with Dash via clientside callbacks + hidden `dcc.Store`. No new Python dep. |
| Full-track audio | Spotify Web Playback SDK (CDN script) | Loaded conditionally for Premium users; otherwise the SDK script isn't requested. |
| Card-stack rendering | Plain Dash components + CSS transforms | No new component lib. `perspective`, `rotate3d`, `translate3d` for the crate tilt. |

### Updated Project Structure

```
mccoy/
├── app.py
├── auth.py
├── spotify.py
├── snapshot.py
├── db.py
├── components/
│   ├── header.py
│   ├── artist_grid.py
│   ├── genre_chart.py
│   ├── trends.py
│   └── rustle.py        # NEW: target picker, search bar, card stack
├── assets/
│   ├── style.css
│   └── rustle.js        # NEW: pointer/keyboard gestures,
│                        #      Web Playback SDK setup
├── migrations/
│   ├── 001_initial.sql
│   └── 002_recent_searches.sql   # NEW
├── pyproject.toml
├── Procfile
└── ...
```

### Edge Cases Worth Calling Out

- **Playlist has zero tracks (or only podcasts / local files):**
  the track queue shows the end-of-queue card immediately. Spotify
  may return non-track items (`episode`, local files with null
  URIs); these are filtered out before queueing.
- **Track has no album art:** placeholder grey square (same
  fallback used by the Artists grid for missing artist images).
- **User revokes scopes between sessions:** Rustling fails on first
  API write; user is redirected to `/login` to re-consent. The
  existing token-refresh failure path handles this.
- **User deletes the target playlist mid-session in Spotify:**
  `playlist_add_items` returns 404; we show an error toast and
  reopen the target picker.
- **Network drops during a card transition:** audio stops; the
  next card waits for connectivity. No retry queue.

### Out of Scope (Rustling v1)

- Removing tracks from the target playlist (do that in Spotify).
- Editing recent searches per-item (only "Clear all").
- Persistent rustle session history / dashboard.
- Sharing rustle sessions with another user.
- Custom audio crossfade between cards.
- Showing playlist owner / track count / description on cards.
- Tapping the add counter chip to see the list of adds.
- Mid-session change of the target playlist.
