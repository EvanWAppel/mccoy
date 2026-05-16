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

- [ ] **G-01** Create Railway account and new project linked to GitHub repo
- [ ] **G-02** Set all four environment variables in Railway dashboard (`SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`, `FLASK_SECRET_KEY`)
- [ ] **G-03** Add Railway production redirect URI to Spotify Developer app settings
- [ ] **G-04** Trigger first deploy, confirm Railway build succeeds and app is reachable
- [ ] **G-05** Complete OAuth flow on Railway URL end-to-end — confirm no errors in Railway logs

---

## Group H — Hardening & Edge Cases
> Depends on: G-05 (deployed and working).

- [ ] **H-01** Handle Spotipy `SpotifyException` in `get_top_artists` — return empty list, log error
- [ ] **H-02** Handle missing artist image gracefully — fall back to a placeholder grey square
- [ ] **H-03** Handle artist with zero genres — exclude from genre aggregation without crashing
- [ ] **H-04** Add session expiry handling — if Spotipy refresh fails, redirect to `/login`
- [ ] **H-05** Write integration test: simulate full data flow from mock Spotify response → `aggregate_genres` → `render_genre_chart` output contains expected genre labels
- [ ] **H-06** Confirm app works across all three time windows (manual smoke test)

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
