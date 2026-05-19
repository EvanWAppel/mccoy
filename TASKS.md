# mccoy — Task List

Tasks are grouped so that **Group A** (infra/scaffold) and **Group B** (tests) can begin immediately and in parallel. Downstream groups depend on their predecessors as noted.

Legend: `[x]` done · `[ ]` pending · `[~]` in progress

---

## Group A — Project Scaffold & Infra
> No dependencies. Start immediately.

- [x] **A-01** Initialize uv project: `uv init mccoy`, set Python ≥ 3.11 in `pyproject.toml`
- [x] **A-02** Add core dependencies via uv: `dash`, `spotipy`, `flask`, `gunicorn`, `python-dotenv`
- [x] **A-03** Add dev dependencies: `pytest`, `pytest-mock`, `responses` (HTTP mocking)
- [x] **A-04** Create `.env.example` with all four required env vars (`SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`, `FLASK_SECRET_KEY`)
- [x] **A-05** Create `Procfile` with Railway start command: `web: gunicorn app:server --bind 0.0.0.0:$PORT`
- [x] **A-06** Create `.gitignore` (Python, `.env`, `__pycache__`, `.venv`)
- [x] **A-07** Create empty module stubs: `auth.py`, `spotify.py`, `components/__init__.py`, `components/header.py`, `components/artist_grid.py`, `components/genre_chart.py`
- [x] **A-08** Create `assets/style.css` with Spotify dark theme CSS variables and base styles
- [x] **A-09** Initialize git repo, create initial commit, push to GitHub

---

## Group B — Test Scaffolding
> Depends on: A-01, A-03. Write all tests before implementation (TDD red phase).

- [x] **B-01** Create `tests/conftest.py` — shared fixtures: mock Spotify artist response, mock profile response, mock session
- [x] **B-02** Write `tests/test_spotify.py` — test `get_top_artists(sp, time_range)` returns list of 10 dicts with keys `name`, `image_url`, `rank`, `genres`
- [x] **B-03** Write `tests/test_spotify.py` — test `get_user_profile(sp)` returns dict with `display_name` and `avatar_url`
- [x] **B-04** Write `tests/test_spotify.py` — test `aggregate_genres(artists)` returns sorted list of `{genre, count}` dicts, top 20 max
- [x] **B-05** Write `tests/test_spotify.py` — test `aggregate_genres` handles artists with empty genre lists
- [x] **B-06** Write `tests/test_auth.py` — test `get_auth_url()` returns a valid Spotify authorization URL string
- [x] **B-07** Write `tests/test_auth.py` — test `get_sp_from_session(session)` returns None when session has no token
- [x] **B-08** Write `tests/test_auth.py` — test `get_sp_from_session(session)` returns a Spotipy client when session has a valid token dict
- [x] **B-09** Write `tests/test_components.py` — test `render_artist_card(artist, rank)` returns a Dash component (not None, is a `html.Div`)
- [x] **B-10** Write `tests/test_components.py` — test `render_genre_chart(genres)` returns a `dcc.Graph` component
- [x] **B-11** Write `tests/test_components.py` — test `render_genre_chart` with empty genre list returns a `dcc.Graph` with no-data message

---

## Group C — Core Logic Implementation
> Depends on: B-01–B-08 written (red). Implement to make tests green.

- [x] **C-01** Implement `spotify.get_top_artists(sp, time_range)` — calls `sp.current_user_top_artists`, maps response to `{name, image_url, rank, genres}`
- [x] **C-02** Implement `spotify.get_user_profile(sp)` — calls `sp.current_user()`, returns `{display_name, avatar_url}`
- [x] **C-03** Implement `spotify.aggregate_genres(artists)` — flattens genres from all artists, counts occurrences, returns top 20 sorted by count desc
- [x] **C-04** Implement `auth.get_auth_url()` — builds Spotipy `SpotifyOAuth` with env vars and returns `get_authorize_url()`
- [x] **C-05** Implement `auth.handle_callback(code)` — exchanges auth code for token dict using Spotipy OAuth manager
- [x] **C-06** Implement `auth.get_sp_from_session(session)` — reads token from Flask session, returns authenticated `spotipy.Spotify` client or `None`
- [x] **C-07** Run `pytest tests/test_spotify.py tests/test_auth.py` — all tests must pass (green phase)

---

## Group D — Component Implementation
> Depends on: B-09–B-11 written (red), C-01–C-03 done.

- [x] **D-01** Implement `components/artist_grid.render_artist_card(artist, rank)` — `html.Div` with background image (artist photo), rank badge, artist name overlay
- [x] **D-02** Implement `components/artist_grid.render_grid(artists)` — 5-column CSS grid of 10 artist cards
- [x] **D-03** Implement `components/genre_chart.render_genre_chart(genres)` — horizontal Plotly bar chart, Spotify green bars, dark background, top 20 genres
- [x] **D-04** Implement `components/header.render_header(profile)` — avatar image + display name on left, Logout button on right, dark header bar
- [x] **D-05** Run `pytest tests/test_components.py` — all tests must pass (green phase)

---

## Group E — Vertical Slice (Minimal Working App)
> Depends on: C-07, D-05. **Highest priority — get this running first.**

- [x] **E-01** Create `app.py` with Dash app instance, expose `server = app.server` for gunicorn
- [x] **E-02** Add Flask route `GET /login` — redirects to Spotify OAuth URL
- [x] **E-03** Add Flask route `GET /callback` — exchanges code for token, stores in session, redirects to `/`
- [x] **E-04** Add Flask route `GET /logout` — clears session, redirects to `/login`
- [x] **E-05** Implement Dash layout: if not authenticated render login page (centered "Connect Spotify" button); if authenticated render full app shell (header + time window tabs + content tabs placeholder)
- [x] **E-06** Implement Dash callback: on time window tab change or page load, fetch top artists for selected window and store in `dcc.Store`
- [x] **E-07** Implement Dash callback: render artist grid from `dcc.Store` data, show `dcc.Loading` spinner during fetch
- [x] **E-08** Implement Dash callback: render genre bar chart from `dcc.Store` data
- [x] **E-09** Smoke test locally: `uv run python app.py`, complete full OAuth flow, confirm artists + genres render

---

## Group F — Styling
> Depends on: E-09 (app renders). Can run in parallel with Group G.

- [x] **F-01** Apply `#121212` body background, `#FFFFFF` base text color in `assets/style.css`
- [x] **F-02** Style artist cards: square aspect ratio, photo fills card, name + rank overlay pinned to bottom, semi-transparent gradient background
- [x] **F-03** Style time window tabs: pill-style tabs, active tab uses `#1DB954` green
- [x] **F-04** Style content tabs: match Spotify tab styling, subtle underline indicator
- [x] **F-05** Style genre chart: dark plot background (`#1E1E1E`), `#1DB954` bars, white axis labels, no gridlines
- [x] **F-06** Style header: `#1E1E1E` background, avatar as small circle, logout button as ghost button
- [x] **F-07** Style login page: centered vertically, Spotify green "Connect with Spotify" button, dark background

---

## Group G — Railway Deployment
> Depends on: E-09. Can run in parallel with Group F.

- [x] **G-01** Create Railway account and new project linked to GitHub repo
- [x] **G-02** Set all four environment variables in Railway dashboard (`SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`, `FLASK_SECRET_KEY`)
- [x] **G-03** Add Railway production redirect URI to Spotify Developer app settings
- [x] **G-04** Trigger first deploy, confirm Railway build succeeds and app is reachable
- [x] **G-05** Complete OAuth flow on Railway URL end-to-end — confirm no errors in Railway logs

---

## Group H — Hardening & Edge Cases
> Depends on: G-05 (deployed and working).

- [x] **H-01** Handle Spotipy `SpotifyException` in `get_top_artists` — return empty list, log error
- [x] **H-02** Handle missing artist image gracefully — fall back to a placeholder grey square
- [x] **H-03** Handle artist with zero genres — exclude from genre aggregation without crashing
- [x] **H-04** Add session expiry handling — if Spotipy refresh fails, redirect to `/login`
- [x] **H-05** Write integration test: simulate full data flow from mock Spotify response → `aggregate_genres` → `render_genre_chart` output contains expected genre labels
- [x] **H-06** Confirm app works across all three time windows (manual smoke test)

---

## Dependency Graph

```
A (scaffold) ──┬──► B (tests) ──► C (logic) ──► E (vertical slice) ──► G (deploy)
               │                                                         │
               └──────────────────► D (components) ──────────────────────┤
                                                                          ▼
                                                                   F (styling)
                                                                   H (hardening)
```

**Critical path to first working demo:** A → B → C → D → E → G

---

## Feature: Listening Trends Over Time

---

## Group I — Database Layer
> No dependencies. Start immediately alongside Group J.

- [ ] **I-01** Create `migrations/001_initial.sql` — `stored_token`, `snapshots`, `artist_entries` tables per PRD schema
- [ ] **I-02** Add `psycopg2-binary` to uv dependencies
- [ ] **I-03** Implement `db.py`: `get_connection()` from `DATABASE_URL` env var, `init_db()` runs migration SQL
- [ ] **I-04** Implement `db.py`: `save_refresh_token(token: str)` — upsert single row in `stored_token`
- [ ] **I-05** Implement `db.py`: `get_refresh_token() -> str | None` — read from `stored_token`
- [ ] **I-06** Implement `db.py`: `save_snapshot(time_range: str, artists: list[dict]) -> int` — insert snapshot + artist_entries, return snapshot id
- [ ] **I-07** Implement `db.py`: `get_snapshots(time_range: str) -> list[dict]` — return all snapshots with their artist entries, ordered by captured_at

---

## Group J — Database & Snapshot Tests (TDD red phase)
> Write before implementing. Depends on: I-01 (schema defined).

- [ ] **J-01** Write `tests/test_db.py` — test `save_refresh_token` + `get_refresh_token` roundtrip using mock connection
- [ ] **J-02** Write `tests/test_db.py` — test `save_snapshot` executes correct INSERT statements with right args
- [ ] **J-03** Write `tests/test_db.py` — test `get_snapshots` returns list of dicts with `captured_at`, `time_range`, `artists` keys
- [ ] **J-04** Write `tests/test_db.py` — test `get_snapshots` returns empty list when no rows exist
- [ ] **J-05** Write `tests/test_snapshot.py` — test `run_snapshot()` calls `get_top_artists` for all 3 time ranges
- [ ] **J-06** Write `tests/test_snapshot.py` — test `run_snapshot()` calls `save_snapshot` 3 times (once per time range)
- [ ] **J-07** Write `tests/test_snapshot.py` — test `run_snapshot()` returns early without error if `get_refresh_token()` returns None

---

## Group K — Snapshot Script Implementation
> Depends on: J-01–J-07 written (red). Make them green.

- [ ] **K-01** Implement `snapshot.py`: `run_snapshot()` — read refresh token from DB, get sp client, fetch top 50 artists for each of 3 time ranges, save each snapshot
- [ ] **K-02** Update `auth.py`: `handle_callback()` — after exchanging code, save refresh token to DB via `db.save_refresh_token()`
- [ ] **K-03** Add `if __name__ == "__main__": run_snapshot()` entry point to `snapshot.py`
- [ ] **K-04** Run `pytest tests/test_db.py tests/test_snapshot.py` — all green

---

## Group L — Trends Component Tests (TDD red phase)
> Depends on: I-01 (schema known). Can run in parallel with Group K.

- [ ] **L-01** Write `tests/test_trends.py` — test `render_bump_chart(snapshots, n)` returns `dcc.Graph` when snapshots has ≥ 2 entries
- [ ] **L-02** Write `tests/test_trends.py` — test `render_bump_chart` with < 2 snapshots returns `html.Div` empty state (not a graph)
- [ ] **L-03** Write `tests/test_trends.py` — test `render_area_chart(snapshots)` returns `dcc.Graph` when snapshots has ≥ 2 entries
- [ ] **L-04** Write `tests/test_trends.py` — test `render_area_chart` with < 2 snapshots returns `html.Div` empty state
- [ ] **L-05** Write `tests/test_trends.py` — test bump chart figure has one trace per unique artist in top N
- [ ] **L-06** Write `tests/test_trends.py` — test area chart figure has one trace per genre

---

## Group M — Trends Component Implementation
> Depends on: L-01–L-06 written (red). Make them green.

- [ ] **M-01** Implement `components/trends.py`: `render_bump_chart(snapshots: list[dict], n: int) -> dcc.Graph | html.Div`
- [ ] **M-02** Implement `components/trends.py`: `render_area_chart(snapshots: list[dict]) -> dcc.Graph | html.Div`
- [ ] **M-03** Style both charts: dark background, Spotify green accents, white labels, no gridlines
- [ ] **M-04** Run `pytest tests/test_trends.py` — all green

---

## Group N — App Integration
> Depends on: K-04, M-04.

- [ ] **N-01** Add "Trends" as third content tab in `app.py` alongside Artists and Genres
- [ ] **N-02** Add Dash callback for Trends tab: fetch `get_snapshots("short_term")` from DB, render bump chart + area chart stacked vertically
- [ ] **N-03** Add N-artists slider (range 5–50, default 10) above bump chart, wire to callback
- [ ] **N-04** Compute next snapshot date (next Sunday midnight UTC) and pass to empty state message
- [ ] **N-05** Smoke test locally: confirm Trends tab shows empty state before any snapshots, then run `snapshot.py` manually and confirm charts render

---

## Group O — Railway Cron & Postgres Provisioning
> Depends on: N-05 (app works locally). Requires manual Railway dashboard steps.

- [ ] **O-01** Add Railway Postgres add-on in Railway dashboard — `DATABASE_URL` auto-injected
- [ ] **O-02** Run `python -c "from db import init_db; init_db()"` against Railway DB to apply schema (via Railway CLI or one-off command)
- [ ] **O-03** Add Railway Cron service: command `python snapshot.py`, schedule `0 0 * * 0` (Sundays midnight UTC)
- [ ] **O-04** Push latest code to GitHub → Railway auto-deploys app + provisions cron
- [ ] **O-05** Log into the deployed app to trigger refresh token save, confirm `stored_token` row exists in DB
- [ ] **O-06** Manually trigger cron job once in Railway dashboard, verify snapshot rows appear in DB
- [ ] **O-07** Confirm Trends tab shows empty state message with correct next-snapshot date

---

## Trends Dependency Graph

```
I (db layer) ──┬──► J (db tests) ──► K (snapshot impl) ──► N (app integration) ──► O (railway)
               │                                              ▲
               └──► L (trends tests) ──► M (trends components)
```

**Critical path:** I → J → K → N → O (with L → M running in parallel with K)
