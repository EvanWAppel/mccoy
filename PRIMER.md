# mccoy — Primer

## Next session — 2026-10-24 weekend

**Goal.** mccoy is a Plotly Dash app for Spotify listening stats and
"Rustling", a crate-digging playlist builder. It is live on Railway at
https://mccoy.evanappel.me. It is Evan's flagship recruiter-facing
portfolio piece, and logged-out visitors get a public demo.

**Current state (main @ f9e268c, 2026-10-22).**
- Groups VV (Six Degrees, PR #48), WW (play-history pipeline + dbt,
  PRs #49–#51) and YY-01..05 (public read-only API, PR #52) are merged.
- Still open in the Recruiter Expansion (`TASKS.md` from line 801):
  XX (Ask Your Listening), YY-06/07, ZZ (rec quality), AAA (analysis).
- Open PRs: only Dependabot bumps (#40, #41, #44, #45, #46). Leave them
  alone. No feature PR is in flight.
- Tests on main: `uv run pytest -q` gives **490 passed, 33 skipped**
  (51s). `uv run ruff check .` is clean. The 33 skips are the Postgres
  tests (raw_plays + dbt), which need `TEST_DATABASE_URL`. CI sets that
  with `REQUIRE_PG_TESTS=1`. Local `postgres`/`initdb` binaries exist,
  so you can run them against a throwaway cluster under `/tmp`. Never
  point them at Railway.

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

### Autonomous tasks, in order
Branch from `main`. Each one finishes as an open PR, never merged. The
done-condition for every task also includes `uv run pytest -q` green
and `uv run ruff check .` clean.

1. **TASKS hygiene.** VV-11 and YY-07 were reviewed and merged (#48,
   #52), so tick them. Done when `TASKS.md` matches git history.
2. **XX-02, SQL guard** (branch `ask-your-listening`). Add tests and
   an implementation of `sql_guard`. It accepts one `SELECT` (CTEs
   allowed) and rejects DML, DDL and multi-statement input. Use a real
   parser (`uv add sqlglot`), not regex. Done when
   `uv run pytest tests/test_sql_guard.py` is green.
3. **XX-03 + XX-04 (offline only).** Build `ask(question)` with
   schema-aware prompt construction. The SQL goes through the guard,
   and the model client is injected and **mocked** in tests. Running
   `uv add anthropic` is fine, but make **no live call** and read no
   key. Log the prompt, the SQL and the row count. Done when
   `uv run pytest tests/test_ask.py` is green.
4. **XX-05, offline evals.** Build `tests/evals/` over a fixture DB
   with recorded model outputs. It runs in the normal pytest run.
5. **XX-01, migration draft.** Write `migrations/007_*.sql` for a
   read-only role limited to `marts`, with a statement timeout and a
   row cap. Test it against a local throwaway Postgres only. **If the
   role or login design is unclear** (LOGIN role with its own password
   vs `SET ROLE` from the app connection), stop and put the question
   in BLOCKED.md. The migration is never applied to Railway.
6. **AAA-01.** Write `scripts/export_marts.py`, which exports marts to
   a small parquet snapshot. Test it against a fixture DB or fixture
   frames. Done when its test is green.
7. **AAA-02.** Write the code and section structure of
   `analysis/listening.ipynb` against **fixture data only**. Evan
   writes the narrative (AAA-03).
8. **ZZ-01, audit only.** "Card shown" events are not stored today:
   there is no table and no logging in `migrations/` or `app.py`.
   Write that finding up in `DECISIONS.md` *(draft)*. Adding the
   migration needs Evan's confirmation, which is in BLOCKED.md.

### Do NOT do
- No deploys, no Railway changes, no merges (including Dependabot), no
  pushes to `main`. Don't publish or send anything.
- Don't run any migration against Railway Postgres (UU-04, PP-08, any
  007). Evan does those.
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
