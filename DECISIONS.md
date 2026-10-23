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

## 2026-10-01 — Second-round review fixes *(draft)*
- **Stuck runs:** count every `running` row older than 2h in the 7-day
  window (ingest and dbt), and exclude only fresh in-flight runs from
  the success rate. Rejected latest-row-only detection: an hourly
  crash makes each new orphan the "latest", hiding all of them.
- **Owner token save raises:** a failed save at owner login now errors
  instead of logging a warning, since the cron silently keeps a stale
  token otherwise. Cost: local owner login needs a reachable DB.

## 2026-10-17 — Public API details *(draft)*
- **Hour-of-week is sample data.** `/api/v1/listening/hour-of-week`
  always returns the demo heatmap (`source: "demo"`), following the
  confirmed "Public Patterns is demo-only" call. Rejected serving real
  hours through the API (the PRD lists the endpoint but predates that
  decision).
- **Trends fall back like the chart.** Fewer than two live snapshots
  (or a DB error) returns demo snapshots, flagged `source: "demo"`.
- **Rate limit in process memory.** 60 requests/minute per client IP,
  sliding window, per gunicorn worker; the client IP is the last
  `X-Forwarded-For` hop (Railway's proxy), since earlier hops are
  client-supplied. Rejected Redis/flask-limiter (another service or
  dependency for a personal project).
- **Docs page renders the spec server-side** instead of Swagger UI or
  Redoc from a CDN: no third-party script on the site.


## 2026-10-22 — `ask()` shape *(draft)*
- **`ask` is a package** (`ask/__init__.py`) so XX-06's
  `python -m ask.evals --live` can live beside it.
- **Separate connection, no fallback.** `ask` connects with
  `ASK_DATABASE_URL` (meant for the XX-01 read-only `marts` role) and
  never falls back to the app's read-write `DATABASE_URL`. If XX-01
  settles on `SET ROLE` from the app connection instead of a LOGIN
  role, only `ask.connect_readonly` changes.
- **Belt and braces at execution:** `SET TRANSACTION READ ONLY`,
  `SET LOCAL statement_timeout` (5 s), `fetchmany(row cap + 1)` (500
  rows) and an unconditional rollback, regardless of the role.
- **Marts allow-list on top of the guard.** Every table must be a
  known `marts.<model>` (CTE names excepted); `MARTS_SCHEMA` is tested
  against the dbt model SQL so the prompt can't drift from the marts.
- **Model** `claude-opus-5` by default, overridable with `ASK_MODEL`
  or the `model=` argument. Plain `messages.create`; no server-side
  fallbacks beta yet (a refusal raises `AskError`). Revisit with the
  live key (XX-06).


## 2026-10-22 — Offline evals (XX-05) *(draft)*
- **Hand-built fixture marts, not dbt.** `tests/evals/fixture_marts.sql`
  creates `marts.*` tables directly with ten plays over three sessions,
  in its own throwaway database (so it never collides with the
  dbt-built marts in the pipeline tests). A test keeps its columns
  identical to `ask.MARTS_SCHEMA`. Rejected building it via dbt: slower,
  and the expected answers are easier to check by hand this way.
- **Real Postgres, same gate as the pipeline tests.** End-to-end cases
  need `TEST_DATABASE_URL` (CI sets it with `REQUIRE_PG_TESTS=1`);
  locally they skip. The no-database checks (case file shape, guard
  verdicts, fixture/schema drift, the runner) always run. Rejected
  SQLite/DuckDB: the model writes Postgres SQL (`extract(isodow ...)`).
- **"Recorded" replies are hand-authored for now.** No live call is
  allowed until the key guardrail clears, so `cases.json` carries
  `"recorded_with": "hand-authored"`. XX-06 re-records them from the
  real model with the same runner (`ask.evals.run_case(client=...)`).
- **Attacks are evals too.** Cases with `expect: {error: unsafe}`
  (DELETE, stacked DROP, non-marts tables) and `{error: refused}` must
  be stopped before any DB connection.


## 2026-10-22 — Marts parquet export (AAA-01) *(draft)*
- **One zstd parquet file per mart** under `analysis/data/`, columns
  and order taken from `ask.MARTS_SCHEMA` (one source of truth for the
  marts' shape), rows ordered by every column so re-exports diff
  cleanly. Arrow types come from the Postgres types named there;
  `numeric` (minutes) becomes `float64` for pandas/Hex.
- **`analysis/data/` is gitignored.** It is real listening data; the
  notebook (AAA-02) is built on fixture data and Evan runs it on the
  real snapshot (AAA-03).
- **`pyarrow` is a dev dependency**, not a runtime one: the export is
  an analysis tool run locally (`uv run python -m
  scripts.export_marts`), so the Railway image doesn't carry it.
- **Read-only session on `DATABASE_URL`.** No separate role; the
  export runs `set_session(readonly=True)` before its SELECTs.


## 2026-10-22 — Listening notebook on fixture data (AAA-02) *(draft)*
- **Data code lives in `analysis/metrics.py`, not in cells.** Each
  metric is a pure pandas function, unit-tested in
  `tests/test_analysis.py`; the notebook only loads, draws (Plotly) and
  narrates, so the logic survives the Hex port (AAA-04).
- **`SOURCE = "fixture"` is the committed default.** The fixture is
  synthetic (`analysis/fixture.py`: seeded, made-up artists, 70 days,
  aggregates derived from `fct_plays` the way the dbt marts do) and is
  written through the AAA-01 parquet schema, so fixture and real runs
  share one load path. Evan flips it to `"snapshot"` for AAA-03; fixture
  mode prints a "not real listening" banner.
- **Committed without outputs**, and every section carries a
  `TODO(Evan)` narrative slot: the agent wrote no findings.
- **`pandas` is a dev dependency** (like `pyarrow`): analysis only, not
  in the Railway image. The test runs every code cell end to end on
  the fixture with `fig.show()` stubbed, so no Jupyter dependency.
