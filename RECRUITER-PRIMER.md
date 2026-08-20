# mccoy — Recruiter Primer

An actionable brief for turning mccoy into a flagship-grade portfolio piece.
Written for Evan's coding agent to execute this week. Honesty guardrails on:
scrub employer detail, never imply day-job agent use, keep skill claims at
their true level. Every improvement is tagged with effort and the target
roles it strengthens.

---

## What it is

mccoy is a personal Spotify listening dashboard and DJ-style crate-digging
playlist builder ("Rustling"), built entirely in Python with Plotly Dash and
deployed live on Railway at **mccoy.evanappel.me**. It is Evan's best-looking,
already-shipped app: real external-API integration (Spotify OAuth via Spotipy,
plus a Discogs/MusicBrainz artist-network experiment), a weekly Railway cron
that snapshots top artists into Postgres for trend history, and a full
public no-login demo so a recruiter can see the thing work without connecting
their own Spotify account.

## Honest current state

Stronger than the one-line pitch suggests. This is not a toy.

- **Demo mode already exists and works.** `render_page` serves `public_layout()`
  to logged-out visitors: a read-only Stats/Trends demo backed by stored
  snapshots (falling back to deterministic `demo_data.py` on a cold deploy),
  plus an album-first Rustle sandbox on a client-credentials token. The single
  biggest "recruiters won't OAuth" risk is already solved. Verify it still
  renders on the live URL, then lean on it hard.
- **Real engineering discipline.** 342 pytest tests, a `conftest.py` fixture
  layer, GitHub Actions CI, a PRD/TASKS agent workflow, and an About tab that
  already tells the architecture-and-tradeoffs story honestly (dev-mode Spotify
  constraints, app-only token limits, graceful degradation).
- **Multiple shipped features.** Artist grid, genre chart, trends bump chart,
  a rating system, a playlist CLI, and an artist-network graph (`/network`)
  that loads from Postgres with a committed `graph.json` fallback.
- **The soft spots are presentation, not function:**
  - **README is 33 lines** and buries the lede. No live URL, no screenshots,
    no demo callout, no "what this proves" framing. It reads like a private
    dev note, not a portfolio front door.
  - **Dead LinkedIn URL in the product.** `components/about.py` and
    `tests/test_about.py` still hardcode `linkedin.com/in/evan-appel-8885569b`,
    which is dead. The official profile is now
    `linkedin.com/in/evanwebsterappel`. A recruiter clicking that link hits a
    404 on the About tab of a live portfolio piece. Fix first.
  - **No screenshots or Loom** anywhere in the repo. `og-image.png` exists for
    social cards, but there is nothing a README reader or a recruiter skimming
    GitHub can look at without launching the app.
  - **CI under-delivers on its own promise.** `AGENTS.md` says Ruff + Ty; CI
    (`.github/workflows/ci.yml`) runs only `uv run pytest -q`. The green badge
    should mean what the house rules claim.
  - **Local clutter (not committed, but worth a cleanup note):** a 9.3GB
    `releases.xml.gz` and a 135MB `netviz/data/inscope.jsonl` sit in the
    working tree from the Discogs-dump experiment. Both are gitignored, so the
    repo is clean, but they will confuse a future you. Leave a note or delete.

**Bottom line:** the work is done; the *showing* is not. The highest-ROI
moves this week are all about making a recruiter believe, in 30 seconds, what
the code already proves.

## Flagship potential

**Strong supporting piece, one deliberate push away from flagship.**

mccoy will not be the anchor of an application to Upside (Dagster staff data
eng) or Arcadia (dbt-at-scale AE) — those want heavy pipeline/warehouse proof
this app does not carry. But for the **Hex Customer Engineer** role it is
close to flagship: Hex is a data-app product, and mccoy is Evan shipping a
polished, live, API-integrated data app with a working no-login demo — exactly
the "build a compelling data app and onboard someone into it" skill Hex hires
for. It is also the single best **general shipping-proof** artifact in the
portfolio for every forward-deployed and DevRel role, because it is *live*,
*polished*, and *honestly documented*. Do the README + demo-polish + Loom pass
below and mccoy becomes the "yes, he ships and it's real" tab you point every
recruiter to.

---

## Ranked improvements

Ordered by ROI. Each is scoped so a fast agent-native builder ships it in the
stated window. Portfolio house rules apply: `uv`, TDD/pytest, Ruff, Ty, no
hidden or wrapped errors.

### 1. Fix the dead LinkedIn URL (and any other stale contact) — effort: hours
**Unlocks:** Hex, Sourcegraph, Sierra, Talkdesk, Sendbird, dbt Labs,
LangChain (every role — a 404 on a live portfolio piece is a credibility leak).

The About tab links to a dead LinkedIn profile. This is the one outright bug a
recruiter will actually hit.

- Update `LINKEDIN_URL` in `components/about.py` to
  `https://www.linkedin.com/in/evanwebsterappel`.
- Update the assertion in `tests/test_about.py` to match (RECL: change the
  test to the new truth, watch it fail against old code if you like, then fix
  the source).
- While in `about.py`, confirm `REPO_URL`, `EMAIL`, and `RESUME_URL` resolve.
  **Acceptance:** every link in the About tab returns 200 on the live site;
  `uv run pytest tests/test_about.py` green.

### 2. Rewrite the README to lead with the shipping + demo + API story — effort: hours
**Unlocks:** Hex (data-app framing), plus general shipping proof for
Sourcegraph, Sierra, Talkdesk, Sendbird, dbt Labs, LangChain.

The README is the front door for anyone who finds the repo before the live
site. Make the first screen sell it.

- Open with a one-line hook and the **live link** up top:
  "A live Spotify listening dashboard and crate-digging tool, in Python on
  Dash, deployed on Railway — try the no-login demo at mccoy.evanappel.me."
- Add a **Demo** section that explicitly says *no Spotify login required* and
  names what the demo shows (Stats, Trends, album-first Rustle sandbox). This
  is the line that converts a skeptical recruiter.
- Add a short **What this demonstrates** list, honest and role-relevant:
  external-API integration (Spotify OAuth + client-credentials), a scheduled
  ingest-to-Postgres pipeline, graceful degradation under real API
  constraints, one-language full-stack (Dash), 342 tests + CI.
- Keep local-dev instructions but move them below the pitch.
- Embed the screenshots from task 3.
  **Acceptance:** a reader who never runs the code understands what mccoy is,
  can click through to a working demo, and can see it without an account.

### 3. Add screenshots to the repo and README — effort: hours
**Unlocks:** Hex, plus general shipping proof for all forward-deployed/DevRel
roles.

There is nothing visual in the repo today. Recruiters skim; give them
something to see.

- Capture 3–4 clean screenshots of the **live demo** (logged-out state so
  there is no private data): the Stats artist grid, the Trends bump chart, the
  Rustle sandbox, and the `/network` graph.
- Commit them under `assets/screenshots/` (or `docs/`) and embed in the
  README. Keep file sizes reasonable so the repo stays light.
- Prefer the demo/public views so the screenshots double as proof the no-login
  path works.
  **Acceptance:** README renders with images on GitHub; images show the
  logged-out demo, not private listening data.

### 4. Record a 60–90s Loom walkthrough — effort: hours
**Unlocks:** Hex (onboard-a-user-into-a-data-app skill is the literal job),
Sourcegraph / Sierra / Talkdesk / Sendbird (forward-deployed: can you demo a
product to a stranger?), dbt Labs / LangChain (DevRel: can you talk about your
work on camera?).

For every forward-deployed and DevRel target, "can you walk someone through a
product" *is* the evaluated skill. A Loom is a working sample of it.

- Script it as a customer onboarding: land on the no-login demo, show Stats,
  explain the weekly-snapshot trend history in one sentence, do one Rustle
  gesture, close on the architecture in ten words.
- Do not log in on camera (keeps private data out; also proves the demo path).
- Link it at the top of the README and in the About tab.
  **Acceptance:** an unlisted Loom link live in README + About; under 90s;
  narrates the demo path with no login.

### 5. Harden the public demo's cold-start and add a demo smoke test — effort: weekend
**Unlocks:** Hex (a demo that is reliably up is the whole pitch), general
shipping proof.

The demo is the load-bearing recruiter surface. Make it impossible for a
recruiter to hit a blank or broken page.

- Add a pytest that renders `public_layout()` and asserts the demo populates
  from `demo_data.py` when the DB is empty (cold-deploy path) and from
  snapshots when present. Some of this is likely covered by
  `test_demo_data.py` / `test_app.py` — extend, do not duplicate; DRY via
  `conftest.py` fixtures.
- Add a tiny liveness check (a script or a test that hits the live URL and
  asserts 200 + a known demo string) you can run before sending an
  application, so you never link a recruiter to a cold or crashed instance.
- Confirm the client-credentials Rustle sandbox degrades cleanly if the
  Spotify token call fails (no stack trace to the user; a friendly empty
  state). Honor the house rule: do not hide errors from logs, but do not leak
  them to the recruiter's screen either.
  **Acceptance:** new tests green; a documented one-command pre-send liveness
  check; the demo renders something meaningful even with an empty DB and a
  failed token call.

### 6. Make CI enforce what AGENTS.md promises (Ruff + Ty) — effort: hours
**Unlocks:** Sourcegraph (dev-tooling adoption + code-quality credibility),
dbt Labs / LangChain (DevRel audiences read your CI), general engineering
credibility for all.

The house rules say Ruff + Ty; CI runs only pytest. Close the gap so the green
check is honest.

- Add `uv run ruff check .` and `uv run ty check` (or the project's Ty
  invocation) as CI steps in `.github/workflows/ci.yml`, before or after the
  pytest step.
- Fix whatever they surface. Keep line length < 80 per `CLAUDE.md`.
- Add a CI status badge to the README so the discipline is visible.
  **Acceptance:** CI runs lint + typecheck + tests and is green; badge in
  README.

### 7. Add a short "Data pipeline" note to the About tab / README — effort: hours
**Unlocks:** Hex (semantic/warehouse-adjacent framing), Deepgram (product/usage
analytics + ingest-to-warehouse story), light support for Arcadia / Upside.

mccoy quietly has a scheduled ingest into Postgres — the exact "usage/event
snapshots into a warehouse" shape several data roles want. Say so plainly.

- In the About tab (and README) add one tight paragraph: a weekly Railway cron
  snapshots top-artist rankings into Postgres; the Trends charts and public
  demo read that history; it is idempotent per week. Frame it as a small but
  real scheduled-ingest pipeline, not more than it is.
- Do **not** overstate scale or call it production data engineering. It is a
  personal weekly cron; claim exactly that.
  **Acceptance:** the pipeline story is discoverable without reading code;
  claims stay at true scale.

### 8. Clean up the Discogs-dump experiment footprint — effort: hours
**Unlocks:** general repo hygiene (indirect credibility for Sourcegraph, dbt
Labs, LangChain reviewers who will actually read the repo).

The 9.3GB `releases.xml.gz` and 135MB `inscope.jsonl` are gitignored, so the
public repo is clean — good. But the `/network` feature ships a committed
`graph.json` fallback, and the ingest pipeline (`netviz/dumps.py`) references
dumps a cloner cannot obtain.

- Add a short `netviz/README.md` (or a section) explaining the graph is built
  from a Discogs dump locally and the committed `graph.json` is the shipped
  artifact, so a reader is not confused by a pipeline that needs a 9GB file
  they do not have.
- Optionally delete the local 9.3GB/135MB extracts to reclaim disk.
  **Acceptance:** a fresh cloner understands the network feature works from
  `graph.json` alone; no dead-end "download this 9GB file" trap.

---

## Do this first — one-week mini-plan

The order is chosen so the two things a recruiter actually touches (the live
demo and the repo front door) are fixed first, and the deeper hardening
follows.

1. **Day 1 (30 min):** Fix the dead LinkedIn URL and its test (task 1). Ship
   it. This is the one live bug; do not let it sit.
2. **Day 1–2:** Capture the 3–4 logged-out demo screenshots (task 3), then
   rewrite the README to lead with the live link, the no-login demo, and the
   "what this proves" list, embedding the screenshots (task 2). By end of day 2
   the repo front door sells the piece.
3. **Day 2–3:** Record the 60–90s Loom onboarding walkthrough on the demo path
   (task 4); link it in README + About. Now you have a working sample of the
   forward-deployed/DevRel skill itself.
4. **Day 3–4 (weekend block):** Harden the demo cold-start and add the
   liveness check + demo smoke tests (task 5), so you can safely link the demo
   in every application without babysitting it.
5. **If time remains:** wire Ruff + Ty into CI with a badge (task 6), add the
   data-pipeline note (task 7), and drop the `netviz/README.md` (task 8).

After step 3 you can already point every recruiter at mccoy with confidence.
Steps 4–5 make it a piece you never have to worry about breaking mid-search.
