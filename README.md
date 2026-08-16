# mccoy

**A live Spotify listening dashboard and DJ-style crate-digging tool —
built entirely in Python on Plotly Dash, deployed on Railway.**

👉 **Try the no-login demo: [mccoy.evanappel.me](https://mccoy.evanappel.me)**
— no Spotify account required.

---

## Demo (no login required)

The live site serves a full public demo to logged-out visitors, so you
can see the app work without connecting your own Spotify account:

- **Stats** — an artist grid and genre breakdown, backed by real stored
  listening snapshots (with deterministic sample data as a cold-start
  fallback).
- **Trends** — a bump chart of how top artists move week over week.
- **Rustle sandbox** — an album-first, crate-digging card stack you can
  swipe through, powered by a Spotify client-credentials token (saving
  tracks is owner-only).
- **Network** — a musician collaboration graph (`/network`) rendered
  with dash-cytoscape.

Logging in with Spotify (owner only) unlocks the live personalized
dashboard and the full Rustle playlist builder with write access.

## What this demonstrates

- **Real external-API integration** — Spotify OAuth via Spotipy for the
  owner, plus a client-credentials token for the no-login demo, with
  graceful degradation under real dev-mode API constraints.
- **A scheduled ingest pipeline** — a weekly Railway cron snapshots
  top-artist rankings into Postgres; the Trends charts and public demo
  read that history. Idempotent per week. Small but real, not more than
  that.
- **One-language full-stack** — UI, callbacks, gesture handling, data
  layer, and background jobs all in Python on Dash.
- **Engineering discipline** — 340+ pytest tests with a shared
  `conftest.py` fixture layer, GitHub Actions CI, and a PRD/TASKS-driven
  workflow.
- **An honest About tab** — architecture and tradeoffs written up in the
  app itself, including where Spotify's dev-mode limits shaped the
  design.

## Screenshots

<!-- Task 3: capture 3–4 logged-out demo views (Stats grid, Trends bump
chart, Rustle sandbox, /network graph) into docs/screenshots/ and embed
them here. Use the public/demo views only, so no private listening data
is shown. -->

_Coming soon — see the [live demo](https://mccoy.evanappel.me) in the
meantime._

## Features

- Top-artists grid and aggregated genre chart across three time windows
- Week-over-week Trends bump chart from stored snapshots
- **Rustling** — a swipe/gesture crate-digging playlist builder
  (touch, mouse-drag, and keyboard), with Premium full-track playback
  and a free-tier preview path
- A song rating system
- A Discogs/MusicBrainz musician collaboration graph at `/network`,
  loaded from Postgres with a committed `graph.json` fallback
- A public, no-login portfolio mode for the whole thing

## Tech

Python · Plotly Dash · Spotipy (Spotify Web API) · Flask ·
Postgres · dash-cytoscape · gunicorn · Railway (web + weekly cron) ·
GitHub Actions · pytest.

## Local development

```bash
uv sync
cp .env.example .env  # then fill in Spotify credentials
uv run python app.py
```

House rules (see `CLAUDE.md` / `AGENTS.md`): `uv` for everything, TDD
with pytest, Ruff + Ty, no hidden or wrapped errors. See `prd.md` for
the full product spec and `TASKS.md` for implementation progress.

## Re-consent on next login

The Rustling feature requires additional Spotify OAuth scopes beyond
what the original dashboard used. The next time you log in (locally or
in production), Spotify will prompt you to re-consent and grant the new
permissions. This is a one-time prompt per account.

Current scope set (`auth.SCOPE`):

- `user-top-read`
- `playlist-read-private`
- `playlist-modify-private`
- `playlist-modify-public`
- `streaming`
- `user-read-private`
