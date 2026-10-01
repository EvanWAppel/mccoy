"""Group KK — the About tab: engineering narrative + recruiter hooks.

Draft prose (Evan to edit the voice). Content is sourced from the
codebase architecture and the career source doc.
"""
from datetime import datetime, timezone

from dash import html

REPO_URL = "https://github.com/EvanWAppel/mccoy"
PROFILE_URL = "https://github.com/EvanWAppel"
LINKEDIN_URL = "https://www.linkedin.com/in/evanwebsterappel"
EMAIL = "appelew@gmail.com"
RESUME_URL = "/assets/resume.pdf"


def _section(title, children):
    return html.Section(
        className="about__section",
        children=[
            html.H2(title, className="about__h2"),
            *children,
        ],
    )


def _p(text):
    return html.P(text, className="about__p")


def _link(label, href, external=True):
    kw = {"target": "_blank", "rel": "noopener noreferrer"} if external else {}
    return html.A(label, href=href, className="about__link", **kw)


def _links_row():
    return html.Div(
        className="about__links",
        children=[
            _link("View the source on GitHub", REPO_URL),
            _link("Résumé (PDF)", RESUME_URL),
            _link("LinkedIn", LINKEDIN_URL),
            _link("Email", f"mailto:{EMAIL}"),
        ],
    )


def _ago(then: datetime, now: datetime) -> str:
    minutes = int((now - then).total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return f"{hours // 24} days ago"


def pipeline_health(health: dict | None, now: datetime | None = None):
    """Live status of the hourly play-history pipeline.

    Public-safe by construction: run status and dbt counts only — no
    play counts, no error text.
    """
    if not health:
        return html.Div(
            id="pipeline-health", className="about__health",
            children=_p("The hourly pipeline hasn't reported yet."),
        )
    now = now or datetime.now(timezone.utc)
    items = []
    if health.get("last_ingest_status") == "failed":
        items.append(html.Li(
            "Last run failed — it's logged and will retry next hour.",
            className="about__health-warn",
        ))
    if health.get("last_success_at"):
        items.append(html.Li(
            "Last successful ingest: "
            f"{_ago(health['last_success_at'], now)}"
        ))
    items.append(html.Li(
        f"{health['successes_7d']} of {health['runs_7d']} hourly runs "
        "succeeded in the last 7 days"
    ))
    dbt = health.get("dbt")
    if dbt:
        items.append(html.Li(
            f"dbt: {dbt['models_built']} models, "
            f"{dbt['tests_passed']} tests passing"
        ))
    return html.Div(
        id="pipeline-health", className="about__health",
        children=[
            html.H3("Pipeline health (live)", className="about__h3"),
            html.Ul(items, className="about__list"),
        ],
    )


def about_tab(health: dict | None = None):
    return html.Div(
        className="about",
        children=[
            _section("mccoy", [
                _p(
                    "mccoy is a personal Spotify dashboard — and a "
                    "portfolio piece. The live demo on the left is the "
                    "real app running against my own listening data; "
                    "this page is the engineering story behind it."
                ),
                _links_row(),
            ]),
            _section("Architecture", [
                _p(
                    "Built entirely in Python with Plotly Dash, so the "
                    "UI, callbacks, and data layer are one language and "
                    "one deploy. Spotify OAuth runs through Spotipy; the "
                    "session token is signed into a Flask cookie."
                ),
                html.Ul(className="about__list", children=[
                    html.Li(
                        "Two data paths: the live views fetch from "
                        "Spotify per request, while a scheduled job "
                        "keeps a running history in Postgres (see Data "
                        "pipeline below)."
                    ),
                    html.Li(
                        "Public, no-login portfolio mode: logged-out "
                        "visitors get a read-only Demo (Stats from "
                        "stored snapshots) and an album-first Rustle "
                        "sandbox powered by a client-credentials token "
                        "— the same UI, just the logged-out state."
                    ),
                    html.Li(
                        "Rustle's crate-digging gestures are a small "
                        "Pointer Events module talking to Dash through "
                        "clientside callbacks; premium playback uses the "
                        "Spotify Web Playback SDK with a free-preview "
                        "fallback."
                    ),
                    html.Li(
                        "TDD throughout (pytest), Ruff + Ty in CI, and "
                        "a PRD / TASKS workflow that keeps agent-driven "
                        "changes scoped and reviewable."
                    ),
                ]),
            ]),
            _section("Data pipeline", [
                _p(
                    "Two small but real scheduled pipelines feed "
                    "Postgres. A weekly Railway cron snapshots my "
                    "top-artist rankings for the Trends charts. An "
                    "hourly cron pulls my recently-played history "
                    "(Spotify only keeps the last 50 plays, hence "
                    "hourly), loads it incrementally from a watermark "
                    "into a raw table — idempotent, so re-runs never "
                    "duplicate — and then runs dbt to model it into "
                    "staging views and marts: listening sessions, daily "
                    "minutes, an hour-of-week grid, and artist streaks, "
                    "all covered by dbt tests."
                ),
                _p(
                    "It's a single-user personal pipeline, not "
                    "production data engineering — but it's the same "
                    "ingest → model → test shape, honestly scoped. The "
                    "Patterns tab in the demo uses sample data; my real "
                    "listening hours stay private."
                ),
                pipeline_health(health),
            ]),
            _section("Tradeoffs worth calling out", [
                html.Ul(className="about__list", children=[
                    html.Li(
                        "The Spotify app runs in development mode, which "
                        "blocks playlist creation and nulls preview "
                        "URLs — so the owner flow degrades gracefully "
                        "and the public sandbox routes audio through "
                        "Spotify's embed player instead."
                    ),
                    html.Li(
                        "An app-only token can't read playlist tracks "
                        "(401), so the public sandbox is album-first "
                        "rather than mirroring the owner's playlist "
                        "flow — a deliberate adaptation to a hard API "
                        "constraint."
                    ),
                ]),
            ]),
            _section("Why I built it", [
                _p(
                    "I spend my days using AI agents to make data "
                    "reliably accessible and to bring colleagues along "
                    "on the same path. mccoy is where I sharpen that "
                    "practice in the open: a real product, built "
                    "agentically, with the engineering discipline "
                    "— tests, validation, docs — that makes what agents "
                    "build actually durable."
                ),
                _links_row(),
            ]),
        ],
    )
