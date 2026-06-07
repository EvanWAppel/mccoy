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

- [x] **I-01** Create `migrations/001_initial.sql` — `stored_token`, `snapshots`, `artist_entries` tables per PRD schema
- [x] **I-02** Add `psycopg2-binary` to uv dependencies
- [x] **I-03** Implement `db.py`: `get_connection()` from `DATABASE_URL` env var, `init_db()` runs migration SQL
- [x] **I-04** Implement `db.py`: `save_refresh_token(token: str)` — upsert single row in `stored_token`
- [x] **I-05** Implement `db.py`: `get_refresh_token() -> str | None` — read from `stored_token`
- [x] **I-06** Implement `db.py`: `save_snapshot(time_range: str, artists: list[dict]) -> int` — insert snapshot + artist_entries, return snapshot id
- [x] **I-07** Implement `db.py`: `get_snapshots(time_range: str) -> list[dict]` — return all snapshots with their artist entries, ordered by captured_at
  - Note: returns `{snapshot_id, captured_at, artists}` (no `time_range` key, since it's the query param).

---

## Group J — Database & Snapshot Tests (TDD red phase)
> Write before implementing. Depends on: I-01 (schema defined).

- [x] **J-01** Write `tests/test_db.py` — test `save_refresh_token` + `get_refresh_token` roundtrip using mock connection
- [x] **J-02** Write `tests/test_db.py` — test `save_snapshot` executes correct INSERT statements with right args
- [x] **J-03** Write `tests/test_db.py` — test `get_snapshots` returns list of dicts with the documented keys
  - Note: tests assert `snapshot_id`, `captured_at`, `artists` (matches the impl). No `time_range` key.
- [x] **J-04** Write `tests/test_db.py` — test `get_snapshots` returns empty list when no rows exist
- [x] **J-05** Write `tests/test_snapshot.py` — test `run_snapshot()` calls `get_top_artists` for all 3 time ranges
- [x] **J-06** Write `tests/test_snapshot.py` — test `run_snapshot()` calls `save_snapshot` 3 times (once per time range)
- [x] **J-07** Write `tests/test_snapshot.py` — test `run_snapshot()` returns early without error if `get_refresh_token()` returns None

---

## Group K — Snapshot Script Implementation
> Depends on: J-01–J-07 written (red). Make them green.

- [x] **K-01** Implement `snapshot.py`: `run_snapshot()` — read refresh token from DB, get sp client, fetch top 50 artists for each of 3 time ranges, save each snapshot
- [x] **K-02** Save refresh token to DB after OAuth callback via `db.save_refresh_token()`
  - Deviation: wiring lives in `app.py:callback_route` (after `handle_callback`), not inside `auth.handle_callback()`. Functionally equivalent.
- [x] **K-03** Add `if __name__ == "__main__": run_snapshot()` entry point to `snapshot.py`
- [x] **K-04** Run `pytest tests/test_db.py tests/test_snapshot.py` — all green

---

## Group L — Trends Component Tests (TDD red phase)
> Depends on: I-01 (schema known). Can run in parallel with Group K.

- [x] **L-01** Write `tests/test_trends.py` — test `render_bump_chart(snapshots, n)` returns `dcc.Graph` when snapshots has ≥ 2 entries
- [x] **L-02** Write `tests/test_trends.py` — test `render_bump_chart` with < 2 snapshots returns `html.Div` empty state (not a graph)
- [x] **L-03** Write `tests/test_trends.py` — test `render_area_chart(snapshots)` returns `dcc.Graph` when snapshots has ≥ 2 entries
- [x] **L-04** Write `tests/test_trends.py` — test `render_area_chart` with < 2 snapshots returns `html.Div` empty state
- [x] **L-05** Write `tests/test_trends.py` — test bump chart figure has one trace per unique artist in top N
- [x] **L-06** Write `tests/test_trends.py` — test area chart figure has one trace per genre

---

## Group M — Trends Component Implementation
> Depends on: L-01–L-06 written (red). Make them green.

- [x] **M-01** Implement `components/trends.py`: `render_bump_chart(snapshots: list[dict], n: int) -> dcc.Graph | html.Div`
- [x] **M-02** Implement `components/trends.py`: `render_area_chart(snapshots: list[dict]) -> dcc.Graph | html.Div`
- [x] **M-03** Style both charts: dark background, white labels, no gridlines
- [x] **M-04** Run `pytest tests/test_trends.py` — all green

---

## Group N — App Integration
> Depends on: K-04, M-04.

- [x] **N-01** Add "Trends" as third content tab in `app.py` alongside Artists and Genres
- [x] **N-02** Add Dash callback for Trends tab: fetch `get_snapshots("short_term")` from DB, render bump chart + area chart stacked vertically
- [x] **N-03** Add N-artists slider (range 5–50, default 10) above bump chart, wire to callback
- [x] **N-04** Compute next snapshot date (next day, midnight UTC) and pass to empty state message
- [ ] **N-05** Smoke test locally: confirm Trends tab shows empty state before any snapshots, then run `snapshot.py` manually and confirm charts render (NOT YET DONE — needs venv + local Postgres)

---

## Group O — Railway Cron & Postgres Provisioning
> Depends on: N-05 (app works locally). Requires manual Railway dashboard steps.

- [ ] **O-01** Add Railway Postgres add-on in Railway dashboard — `DATABASE_URL` auto-injected
- [ ] **O-02** Run `python -c "from db import init_db; init_db()"` against Railway DB to apply schema (via Railway CLI or one-off command)
- [ ] **O-03** Add Railway Cron service: command `python snapshot.py`, schedule `0 0 * * *` (daily, midnight UTC)
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

---

## Feature: Rustling

Refer to `prd.md` → **Feature: Rustling** for the full spec. Tasks
below are sized to be small, independently committable, and ordered
so the **vertical slice (Group U)** lights up end-to-end as fast as
possible — everything after Group U is polish, parallel-able, or
deferred surface area.

**TDD discipline:** every group with `-tests` in the name is the red
phase; the corresponding `-impl` group makes them green. Don't skip
the red phase.

---

## Group P — Rustling DB Layer
> No dependencies. Start immediately.

- [ ] **P-01** Write `tests/test_db.py` — test `save_recent_search(user_id, query)` inserts a row, and re-inserting the same query updates `searched_at` instead of duplicating
- [ ] **P-02** Write `tests/test_db.py` — test `get_recent_searches(user_id)` returns up to 5 most recent distinct queries, newest first
- [ ] **P-03** Write `tests/test_db.py` — test `get_recent_searches` returns `[]` for an unknown user
- [ ] **P-04** Write `tests/test_db.py` — test `clear_recent_searches(user_id)` deletes all rows for that user only
- [ ] **P-05** Create `migrations/002_recent_searches.sql` per PRD schema (`recent_searches` table + index on `(user_id, searched_at DESC)`)
- [ ] **P-06** Implement `db.save_recent_search(user_id, query)` — upsert; bump `searched_at` if the same query already exists for that user
- [ ] **P-07** Implement `db.get_recent_searches(user_id, limit=5)` — `SELECT DISTINCT query … ORDER BY searched_at DESC LIMIT 5`
- [ ] **P-08** Implement `db.clear_recent_searches(user_id)` — `DELETE FROM recent_searches WHERE user_id = %s`
- [ ] **P-09** Run `pytest tests/test_db.py` — all new tests green

---

## Group Q — Spotify API Helper Tests (TDD red)
> No dependencies. Run in parallel with P.

- [ ] **Q-01** Write `tests/test_spotify.py` — `search_playlists(sp, query, limit=20, offset=0)` returns list of `{id, name, image_url}` from a mocked Spotipy response
- [ ] **Q-02** Write `tests/test_spotify.py` — `search_playlists` returns `[]` on zero-result response
- [ ] **Q-03** Write `tests/test_spotify.py` — `get_playlist_tracks(sp, playlist_id)` returns ordered `[{name, uri, album_id, album_name, album_image_url, preview_url}]` and filters out items with null `track` or `track.uri`
- [ ] **Q-04** Write `tests/test_spotify.py` — `get_album_tracks(sp, album_id)` returns `[{name, uri, track_number, duration_ms, image_url, preview_url}]` in album order
- [ ] **Q-05** Write `tests/test_spotify.py` — `get_user_playlists(sp)` returns `[{id, name}]` for the dropdown, accumulating across pagination
- [ ] **Q-06** Write `tests/test_spotify.py` — `create_playlist(sp, user_id, name)` calls `user_playlist_create(user, name, public=False)` and returns the new playlist's `id`
- [ ] **Q-07** Write `tests/test_spotify.py` — `add_track_to_playlist(sp, playlist_id, track_uri)` calls `playlist_add_items(playlist_id, [track_uri])`
- [ ] **Q-08** Write `tests/test_spotify.py` — `get_playlist_track_uris(sp, playlist_id)` returns a `set[str]` of every track URI in the playlist, paginated
- [ ] **Q-09** Write `tests/test_spotify.py` — `get_user_product(sp)` returns the string `"premium"`, `"free"`, or `"open"` from `current_user()['product']`

---

## Group R — Spotify API Helper Implementation
> Depends on: Q-01–Q-09 written (red).

- [ ] **R-01** Implement `spotify.search_playlists(sp, query, limit=20, offset=0)`
- [ ] **R-02** Implement `spotify.get_playlist_tracks(sp, playlist_id)` — filters out `episode` items, local files, and any item where `track is None` or `track.uri is None`
- [ ] **R-03** Implement `spotify.get_album_tracks(sp, album_id)`
- [ ] **R-04** Implement `spotify.get_user_playlists(sp)` — paginate via `sp.current_user_playlists(limit=50, offset=…)` until exhausted
- [ ] **R-05** Implement `spotify.create_playlist(sp, user_id, name)` — `public=False`
- [ ] **R-06** Implement `spotify.add_track_to_playlist(sp, playlist_id, track_uri)`
- [ ] **R-07** Implement `spotify.get_playlist_track_uris(sp, playlist_id)` — accumulate URIs across pagination, return as `set`
- [ ] **R-08** Implement `spotify.get_user_product(sp)`
- [ ] **R-09** Run `pytest tests/test_spotify.py` — all new tests green

---

## Group S — Auth Scope Update
> No dependencies. Run in parallel with P / Q / R.

- [ ] **S-01** Update `auth.py` SCOPES to include `playlist-read-private`, `playlist-modify-private`, `playlist-modify-public`, `streaming`, `user-read-private` (keep `user-top-read`)
- [ ] **S-02** Update `tests/test_auth.py` — assert `get_auth_url()` contains each new scope
- [ ] **S-03** Run `pytest tests/test_auth.py` — green
- [ ] **S-04** Note in README that the next login forces a Spotify re-consent prompt

---

## Group T — Rustling Component Tests (TDD red)
> No dependencies. Run in parallel with P / Q / R / S.

- [ ] **T-01** Write `tests/test_rustle.py` — `mode_switcher()` returns `dcc.Tabs` with values `stats` and `rustle`
- [ ] **T-02** Write `tests/test_rustle.py` — `target_picker(playlists)` returns `html.Div` containing a dropdown of playlist names plus a "Create new…" option
- [ ] **T-03** Write `tests/test_rustle.py` — `target_picker` with `playlists=[]` still renders the "Create new…" option
- [ ] **T-04** Write `tests/test_rustle.py` — `search_bar()` returns a `dcc.Input` with `id="rustle-search"`
- [ ] **T-05** Write `tests/test_rustle.py` — `recents_chips(queries)` returns a row containing up to 5 chip components, each labeled with the query string
- [ ] **T-06** Write `tests/test_rustle.py` — `recents_chips([])` returns an empty container (no chips, no clear button)
- [ ] **T-07** Write `tests/test_rustle.py` — `playlist_card(playlist)` returns a Div containing the cover image and the playlist name
- [ ] **T-08** Write `tests/test_rustle.py` — `track_card(track)` returns a Div containing the album art and the track name
- [ ] **T-09** Write `tests/test_rustle.py` — `track_card(track, already_added=True)` includes an "Already added" badge
- [ ] **T-10** Write `tests/test_rustle.py` — `end_of_queue_card(message)` returns a Div with the message text
- [ ] **T-11** Write `tests/test_rustle.py` — `added_stamp_overlay()` returns a Div with class `added-stamp`
- [ ] **T-12** Write `tests/test_rustle.py` — `add_counter_chip(n)` returns a Div with text `"+N added"`

---

## Group U — Vertical Slice (Minimum Working Rustling)
> Depends on: P-09, R-09, S-03, enough of T to support impl. **Highest priority** — get this end-to-end first.

This slice deliberately omits: crate-stack perspective (single card only), audio, recents persistence, dedupe, album drill, counter chip, end-of-queue, create-new playlist, iOS unlock, mobile-responsive polish, gesture JS (use temporary buttons instead). All of those are layered on later in V–FF.

- [ ] **U-01** Implement `components/rustle.py` skeleton: `mode_switcher`, `target_picker`, `search_bar`, `playlist_card`, `track_card`
- [ ] **U-02** Wire `mode_switcher` into `app.py` above the existing time-window tabs; hide the time-window + content tabs when mode = `rustle`
- [ ] **U-03** Add `dcc.Store(id="rustle-target")` (target playlist id) and `dcc.Store(id="rustle-user-id")` (Spotify user id) to the layout
- [ ] **U-04** Add a Dash callback: on Rustle mode entry, if `rustle-target` is empty, fetch `get_user_playlists(sp)` and render `target_picker`
- [ ] **U-05** Add a Dash callback: target picker selection writes the playlist id to `rustle-target` Store and clears the picker view
- [ ] **U-06** Render `search_bar` once a target is set
- [ ] **U-07** Add a Dash callback (debounce=True on the Input): on search input change, call `search_playlists`, store results in `dcc.Store(id="rustle-playlist-queue")`, reset `dcc.Store(id="rustle-playlist-index")` to 0
- [ ] **U-08** Add a Dash callback: render the playlist card at `rustle-playlist-queue[rustle-playlist-index]` (no stack, no perspective yet — single card)
- [ ] **U-09** Add temporary `[← Prev] [Enter →] [Next]` buttons under the playlist card as a stand-in for L/R/up gestures
- [ ] **U-10** Wire Prev/Next to decrement/increment `rustle-playlist-index`; clamp at queue bounds
- [ ] **U-11** Wire Enter to call `get_playlist_tracks(playlist_id)`, store in `dcc.Store(id="rustle-track-queue")`, reset `rustle-track-index`, hide the playlist card view and show the track card view
- [ ] **U-12** Add a Dash callback: render the current track card from the track queue
- [ ] **U-13** Add temporary `[← Prev] [+ Add] [Next] [↩ Back]` buttons under the track card
- [ ] **U-14** Wire `+ Add` to call `add_track_to_playlist(rustle-target, track_uri)`; no feedback yet beyond the existing Spotify response
- [ ] **U-15** Wire `↩ Back` to return to the playlist card view
- [ ] **U-16** Local smoke test: log in (re-consent triggered by Group S), switch to Rustle mode, pick a target playlist, type a search, page through results, enter a playlist, add a track, verify the track now appears in the target playlist in the real Spotify app

---

## Group V — Crate-of-Records Visual Polish
> Depends on: U-16. Run in parallel with W, X, Z, AA, BB, CC, DD, EE, FF.

- [ ] **V-01** Add `.rustle-stack` container styles in `assets/style.css`: `perspective: 1200px`, fixed aspect-ratio for cards
- [ ] **V-02** Render the top 4 entries of the active queue inside `.rustle-stack`: top card centered, next three peeking behind with progressive `translateY`, `scale(0.95)…(0.85)`, and small forward tilt via `rotateX`
- [ ] **V-03** Add a CSS class `.rustle-card--exiting` that translates the top card off-screen in the gesture direction and fades it out over ~240 ms
- [ ] **V-04** Add a CSS class for the next-card slide-up-to-top transition (~240 ms)
- [ ] **V-05** Manual visual check on desktop Chrome
- [ ] **V-06** Manual visual check on mobile Safari

---

## Group W — Gesture Input (touch / keyboard / drag)
> Depends on: U-16. Run in parallel with V, X.

- [ ] **W-01** Create `assets/rustle.js` — Pointer Events listener on a `data-rustle-card-area="true"` element
- [ ] **W-02** Compute drag distance + dominant axis; ≥80 px commits a gesture (L / R / Up / Down)
- [ ] **W-03** Communicate the resolved gesture to Dash via a clientside callback writing to `dcc.Store(id="rustle-gesture")` with shape `{direction, ts}`
- [ ] **W-04** Bind `keydown`: ArrowLeft/Right = L/R, ArrowUp = Up, ArrowDown = Down, Enter = Up
- [ ] **W-05** Click-and-drag on desktop mirrors touch (same Pointer Events path)
- [ ] **W-06** Replace temporary buttons from Group U with server callbacks listening to `rustle-gesture`: L/R = index ±1, Up = commit (enter playlist / add track), Down = back one level
- [ ] **W-07** Handle Down in track view → back to playlist queue; Down in playlist queue → clear search (returns to recents)
- [ ] **W-08** Manual smoke test: swipe on phone, arrow keys on desktop, drag on desktop — verify behaviors match Group U vertical slice

---

## Group X — Audio: Free `preview_url` Path
> Depends on: U-16. Run in parallel with V, W.

- [ ] **X-01** Add a single `<audio id="rustle-audio">` element in the layout (managed clientside)
- [ ] **X-02** Add a clientside callback: when the current card changes, set `audio.src = preview_url` and call `audio.play()`
- [ ] **X-03** Fade audio volume to 0 over ~200 ms before each card transition (clientside)
- [ ] **X-04** If `preview_url` is null, show a small "No preview available" pill on the card and skip the play call
- [ ] **X-05** Add a one-time "Tap to start" overlay on the very first card after Rustle entry; tapping it primes the `<audio>` element (iOS audio unlock)
- [ ] **X-06** Persist "unlocked" state in a `dcc.Store(id="rustle-audio-unlocked")` for the session (so the overlay shows once per Rustle entry, not per card)
- [ ] **X-07** Write `tests/test_rustle.py` — `track_card(track_without_preview)` includes the "No preview available" indicator
- [ ] **X-08** Manual smoke test in iOS Safari (or DevTools mobile emulator with Safari iOS UA)

---

## Group Y — Audio: Premium Web Playback SDK
> Depends on: X (Free fallback must exist before SDK fallback is wired).

- [ ] **Y-01** Add a Dash callback: on Rustle mode entry, call `get_user_product(sp)` and write to `dcc.Store(id="rustle-product")`
- [ ] **Y-02** If product == `premium`, inject the Spotify Web Playback SDK `<script>` tag into the document (clientside conditional)
- [ ] **Y-03** In `assets/rustle.js`, initialize a `Spotify.Player` once the SDK is ready; capture `device_id` and write it to `dcc.Store(id="rustle-device-id")`
- [ ] **Y-04** Add a server callback: on track-card change, if Premium + `device_id` present, call `sp.start_playback(device_id, uris=[track_uri])` server-side instead of using `preview_url`
- [ ] **Y-05** If SDK init fails or times out (>5 s), log the error and fall back to the Group X `preview_url` path silently
- [ ] **Y-06** Add `tests/test_spotify.py` — `get_user_product` mocked responses for premium / free / open
- [ ] **Y-07** Manual smoke test as a Premium account and as a Free account

---

## Group Z — Selection: Dedupe, Counter, Animations
> Depends on: U-16. Run in parallel with V, W, X.

- [ ] **Z-01** Add a callback: on entering a playlist's track queue, call `get_playlist_track_uris(rustle-target)` and write to `dcc.Store(id="rustle-target-uris")`
- [ ] **Z-02** Render the "Already added" badge on `track_card` when `track.uri ∈ rustle-target-uris` (component already supports this from Group T)
- [ ] **Z-03** When the commit gesture fires on an already-added track, no-op and add a CSS shake class for ~200 ms
- [ ] **Z-04** Implement the `added_stamp_overlay()` animation: scale-in + fade-out over ~600 ms via CSS keyframes
- [ ] **Z-05** On successful add: show the stamp overlay on top of the card, wait ~400 ms, then animate the card off-screen (reuse `.rustle-card--exiting`)
- [ ] **Z-06** Implement `add_counter_chip(n)` styling: fixed-position top-right, Spotify-green pill
- [ ] **Z-07** Add a `dcc.Store(id="rustle-add-count")` initialized to 0; increment on each successful add via callback
- [ ] **Z-08** Append the new URI to `rustle-target-uris` after each successful add so subsequent cards see the updated dedupe set
- [ ] **Z-09** Write `tests/test_rustle.py` — counter chip renders `"+N added"` for `n > 0`, and is hidden for `n == 0`

---

## Group AA — Album Drill
> Depends on: U-16, R-03 (`get_album_tracks`).

- [ ] **AA-01** Add a tap handler to the album art region of `track_card`: tap → emit a `tap-art` action via `rustle-gesture` Store
- [ ] **AA-02** Add a callback: on `tap-art`, call `get_album_tracks(track.album_id)`, store in `dcc.Store(id="rustle-album-queue")`, reset `rustle-album-index`, switch view to the album drill
- [ ] **AA-03** Reuse `track_card` for album drill cards (same shape)
- [ ] **AA-04** Wire Down gesture from album view → return to the playlist track queue at the same index it was left
- [ ] **AA-05** Show the "End of the record. Swipe down to keep digging." card after the last album track
- [ ] **AA-06** Write `tests/test_rustle.py` — album drill navigation: entering an album sets the album queue; Down clears it

---

## Group BB — Recent Searches Persistence
> Depends on: P-09 (DB impl), U-16.

- [ ] **BB-01** Implement `components/rustle.py:recents_chips(queries)` per the Group T tests
- [ ] **BB-02** Render the chip row directly below `search_bar` when the search input is empty
- [ ] **BB-03** Add a callback: on search submit (debounced fire), call `db.save_recent_search(user_id, query)`
- [ ] **BB-04** Add a callback: on Rustle mode entry, call `db.get_recent_searches(user_id)` and render the chips
- [ ] **BB-05** Wire chip click → write the chip's query into the search input value, which re-fires the search callback
- [ ] **BB-06** Add a small `Clear` button next to the chip row → calls `db.clear_recent_searches(user_id)` and refreshes the chips
- [ ] **BB-07** Write `tests/test_rustle.py` — chips render correctly for 0, 1, 5 queries; clear button shown only when chips > 0

---

## Group CC — Create-new Playlist Flow
> Depends on: U-16, R-05 (`create_playlist`).

- [ ] **CC-01** Add a "Create new…" entry to the picker dropdown (already covered in Group T-02)
- [ ] **CC-02** On selection, swap the dropdown UI for a single name input + Create button
- [ ] **CC-03** On Create click, call `spotify.create_playlist(sp, user_id, name)` and use the returned `id` as `rustle-target`
- [ ] **CC-04** Render the picker view's loading state while the create call is in flight
- [ ] **CC-05** Write `tests/test_rustle.py` — picker toggles between dropdown and create-input modes correctly

---

## Group DD — Exhaustion / End-of-Queue
> Depends on: U-16.

- [ ] **DD-01** Implement search pagination: when `rustle-playlist-index` reaches the end of `rustle-playlist-queue`, call `search_playlists` with `offset += len(queue)` and append results
- [ ] **DD-02** Cap total search results at 100; once reached, render the end-of-queue card instead of paginating further
- [ ] **DD-03** Implement the playlist-track end-of-queue card: "You've flipped through every track in this playlist. Swipe down to try another."
- [ ] **DD-04** Implement the album-track end-of-queue card (AA-05 covers this; cross-reference)
- [ ] **DD-05** Swipe Down on any end-of-queue card → return to the previous queue
- [ ] **DD-06** Write `tests/test_rustle.py` — `end_of_queue_card` renders the right message per context
- [ ] **DD-07** Write `tests/test_spotify.py` — pagination math: searching with `limit=20, offset=40` calls the API with the right args

---

## Group EE — Edge Cases & Error Handling
> Depends on: U-16. Mostly parallel-able.

- [ ] **EE-01** Zero search results state: render "No playlists found. Try a different search." and surface recents chips below
- [ ] **EE-02** Filter non-track items in `get_playlist_tracks` (covered by R-02 test) — guarantee: queue never includes podcasts, local files, or null tracks
- [ ] **EE-03** Missing album art: render grey square placeholder on `track_card` and `playlist_card` (reuse the existing artist-grid fallback pattern)
- [ ] **EE-04** Wrap every Rustle-side Spotify call in `try / except SpotifyException`; on 401, redirect to `/login` (re-consent)
- [ ] **EE-05** On 404 from `add_track_to_playlist` (target deleted in Spotify mid-session): show a non-blocking error toast, clear `rustle-target` Store, reopen the picker
- [ ] **EE-06** Network drop: catch network-level exceptions on the gesture callback path, log via the standard logger, render a small "Offline — retrying" pill
- [ ] **EE-07** Write `tests/test_rustle.py` — edge-case rendering: zero results, missing art, deleted target

---

## Group FF — Responsive Layout (mobile-first)
> Depends on: U-16. Fully parallel.

- [ ] **FF-01** Add mobile-first CSS for Rustle mode: cards take full container width on viewports < 480 px
- [ ] **FF-02** Constrain Rustle mode to `max-width: 480px; margin: 0 auto;` on desktop so the crate stack stays card-shaped
- [ ] **FF-03** Mode switcher: confirm pill tabs render legibly on both viewports
- [ ] **FF-04** Target-picker modal: full-screen on mobile, centered modal (max-width: 420 px) on desktop
- [ ] **FF-05** Manual visual check on iPhone Safari + desktop Chrome at 1440 px wide

---

## Group GG — Railway Deployment for Rustling
> Depends on: U, V, W, X, Z (core feature complete). Y / AA / BB / CC / DD / EE / FF can land before or after GG.

- [ ] **GG-01** Apply `migrations/002_recent_searches.sql` to the Railway Postgres (same flow as the Trends `init_db` step: enable public networking, run from local, disable public networking)
- [ ] **GG-02** Update the Spotify Developer app's allowed scopes if scope allowlisting is enabled (no redirect URI changes)
- [ ] **GG-03** Merge to `main` → Railway auto-deploys web + cron services
- [ ] **GG-04** Production smoke test: log in (re-consent prompt appears), switch to Rustle, pick a playlist, swipe through a search, commit a track
- [ ] **GG-05** Confirm the committed track appears in the target playlist when opened in the Spotify app on a different device
- [ ] **GG-06** Confirm recent searches persist across logout / login

---

## Rustling Dependency Graph

```
P (db) ─────────────────────────────┐
                                    ▼
Q (api tests) ──► R (api impl) ──┬─► U (vertical slice) ──┬─► V (crate visual)
                                 │                        ├─► W (gestures)
S (auth scopes) ─────────────────┤                        ├─► X (audio free) ──► Y (audio premium)
                                 │                        ├─► Z (dedupe/counter)
T (component tests) ─────────────┘                        ├─► AA (album drill)
                                                          ├─► BB (recents) ◄── P
                                                          ├─► CC (create new)
                                                          ├─► DD (exhaustion)
                                                          ├─► EE (edge cases)
                                                          └─► FF (responsive)
                                                                     │
                                                                     ▼
                                                                   GG (railway)
```

**Critical path to a working demo:** P + Q → R, S, T → U.

**Parallelism plan:** P, Q, S, T all kick off on day 1; one agent each. As soon as Q is done, a fifth agent picks up R. U is single-agent and serial (it's the integration moment). After U-16 turns green, V / W / X / Z / AA / BB / CC / DD / EE / FF can fan out to up to ten agents, each owning one group.
