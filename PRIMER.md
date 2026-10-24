# mccoy — Primer

## Next session — 2026-10-24 weekend

**Goal.** mccoy is a Plotly Dash app for Spotify listening stats and
"Rustling", a crate-digging playlist builder. It is live on Railway at
https://mccoy.evanappel.me. It is Evan's flagship recruiter-facing
portfolio piece, and logged-out visitors get a public demo.

**Current state (main @ 4451ffd, 2026-10-23).**
- Groups VV (Six Degrees, PR #48), WW (play-history pipeline + dbt,
  PRs #49–#51) and YY-01..05 + YY-07 (public read-only API, PR #52)
  are merged.
- The weekend run merged PR #53 (TASKS hygiene, XX-02..05, AAA-01/02,
  the ZZ-01 audit, and a SQL-guard fix for CTE-scope and function
  bypasses) and PR #54 (XX-01, `migrations/manual/007_ask_readonly_role.sql`).
  The Dependabot bumps #40, #41, #44, #45, #46 are merged too.
- Still open in the Recruiter Expansion (`TASKS.md` from line 801):
  XX-06..09 (live evals, owner/public UI, review), YY-06 (needs the
  live URL), ZZ-01's migration + ZZ-02..04 (wait on Evan's
  `rustle_events` approval), AAA-03/04 (Evan's narrative + Hex).
- Open PRs: none.
- Tests on main: `uv run pytest -q` gives **662 passed, 55 skipped**
  (about 1m47s, measured 2026-10-23 on 4451ffd). `uv run ruff check .`
  is clean. The skips are the Postgres tests (raw_plays + dbt), which
  need `TEST_DATABASE_URL`. CI sets that with `REQUIRE_PG_TESTS=1`.
  Local `postgres`/`initdb` binaries exist, so you can run them against
  a throwaway cluster under `/tmp`. Never point them at Railway.

### House rules (from `claude.md` / `AGENTS.md`)
- **Prime Directive: if anything is unclear, stop and ask Evan.**
  Working unattended, that means you skip the task and add a line to
  `BLOCKED.md`. Do not guess.
- TDD with pytest: write a red test first. Fixtures go in
  `tests/conftest.py`.
- Use uv. Run code with `uv run python`. Add deps with `uv add` or
  `uv add --dev`, never by editing `pyproject.toml`.
- Keep lines under 80 characters. Lint with Ruff. Ty is advisory. Use
  prek for pre-commit.
- Use `logging`. Don't hide or wrap errors.
- One branch per group, cut from `main`. Get an independent review
  before the PR. **Evan merges.** Record design calls in
  `DECISIONS.md` and mark them *(draft)*.

### Autonomous tasks
None queued. All eight weekend tasks are merged: TASKS hygiene,
XX-02 (`sql_guard.py`, sqlglot), XX-03/04 (`ask/__init__.py`, mocked
client), XX-05 (`ask/evals.py`, `tests/evals/`), AAA-01
(`scripts/export_marts.py`), AAA-02 (`analysis/listening.ipynb`) and the
ZZ-01 audit (`DECISIONS.md`) in PR #53; XX-01 (manual migration 007)
in PR #54. Every remaining open task in `TASKS.md` is gated by an item
in `BLOCKED.md` (the Anthropic key guardrail, applying 007 +
`ASK_DATABASE_URL`, the `rustle_events` approval) or needs the live URL.
Check `TASKS.md` and `BLOCKED.md`, and ask Evan before starting
anything new.

### Do NOT do
- No deploys, no Railway changes, no merges (including Dependabot), no
  pushes to `main`. Don't publish or send anything.
- Don't run any migration against Railway Postgres (UU-04, PP-08,
  `migrations/manual/007_ask_readonly_role.sql`). Evan does those.
- **No live Anthropic calls.** That means XX-06 live evals and live use
  of XX-07/08. They wait for the API-key guardrail checklist in
  BLOCKED.md.
- Skip anything that needs the live URL or a browser: YY-06 notebook
  against the live API, MM-05/OO-* smoke tests, NN-02/04, GG-06, O-03/06,
  screenshots and the Loom.
- ZZ-01's migration, ZZ-02/03 (they need card-shown data), AAA-03/04
  (Evan writes the narrative and ports it to Hex).
- Don't use browser automation. Never read `.env`. This repo has no
  git-crypt paths.
