# DECISIONS

Append-only log of decisions with a real trade-off. Agent drafts; Evan
confirms. Entries marked *(draft)* await confirmation.

## 2026-09-27 — Recruiter expansion scope and order (confirmed)
Chose to build six features in order: Six Degrees → Play-History
Pipeline → Ask Your Listening → Public API → Rec Quality → Analysis.
Six Degrees first because it needs no new infra or credentials.

## 2026-09-27 — Pipeline: dbt-core + Postgres (confirmed)
Chose dbt-core on the existing Postgres, run from a Railway cron.
Rejected Dagster + dbt (stronger signal for Dagster roles, but a heavier
always-on service to host) and plain SQL views (least signal).

## 2026-09-27 — LLM access: owner-live, public-cached (confirmed)
Live Claude calls only for the logged-in owner; visitors see curated
pre-computed answers. Rejected public-live-with-cap (spend exposure +
guardrail overhead) and owner-only (invisible to recruiters).

## 2026-09-27 — API in the Dash Flask server (confirmed)
Chose `/api/v1/*` on the existing server with a hand-written OpenAPI
spec. Rejected a separate FastAPI service (auto-docs, but a second
deploy to keep in sync).

## 2026-09-27 — Analysis in Jupyter, then Hex (confirmed)
Notebook in repo first (agent can build it end to end); Evan ports to
Hex for the Hex CE role.

## 2026-09-27 — Rec quality: keep rate and 4+ rate, separately (confirmed)

## 2026-09-27 — Six Degrees path semantics *(draft)*
Fewest hops (BFS), ties broken by strongest chain (max min-weight, then
max total weight); search the full graph, not the filtered view. Pure
Python, no networkx. Rejected weighted-shortest-path as the default
(less intuitive "degrees") and adding networkx (unneeded at ~240 nodes;
revisit if centrality/communities land in v2).

## 2026-09-30 — Public Patterns is demo-only; Patterns is a sub-tab (confirmed)
Logged-out visitors see synthetic listening patterns labeled as sample
data; real hour-of-week/daily data is owner-only. Rejected real data
(reveals listening hours) and coarsened real data.

## 2026-09-30 — Pipeline health shows no play counts *(draft)*
The public About panel shows run status, last success, 7-day success
rate, and dbt model/test counts — not "rows in the last 24h" from the
PRD, which would reveal listening volume. Follows the demo-only call
above.

## 2026-09-30 — Real-Postgres integration tests *(draft)*
Upsert idempotency and dbt models are tested against a throwaway
database (TEST_DATABASE_URL; CI runs a postgres:17 service and fails
rather than skips). Rejected mocking the cursor for these: mocks can't
prove ON CONFLICT or SQL model semantics.

## 2026-09-30 — dbt is a runtime dependency *(draft)*
dbt-core/dbt-postgres are main deps so the Railway cron can run them,
at the cost of a larger web image. Rejected a separate cron-only
dependency group (Railway builds both services from one lockfile).

## 2026-09-30 — Local-time bucketing and freshness *(draft)*
Days/hours are bucketed in `listening_tz` = America/Los_Angeles (dbt var,
mirrored in components/patterns.py with a test keeping them in sync).
Staleness is surfaced by the About health panel ("last successful
ingest", failed/stuck-run warnings), not a dbt source-freshness check:
nothing would run `dbt source freshness` meaningfully right after a
successful ingest, so that config was removed rather than left as an
unexecuted claim (review finding, 2026-09-30).

## 2026-09-30 — Review fixes on the pipeline branch *(draft)*
- **Owner gate:** only the Spotify account in `OWNER_SPOTIFY_ID` may
  save the cron's refresh token or see real Patterns; fails closed when
  unset. Rejected leaving "any logged-in user = owner" (allowlisted
  users could overwrite the token and mix their plays into raw_plays).
- **Late plays:** always fetch the latest 50 and let the idempotent
  insert absorb overlap, instead of `after=watermark`, so late-synced
  plays within the last 50 are kept. Costs a few redundant rows per run.
- **Left as-is:** friendly messages on DB outages (logged at warning,
  matches Trends) and `dbt_env` dropping extra DSN params (fine on
  Railway's internal network).
