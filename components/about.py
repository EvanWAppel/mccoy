"""Group KK — the About tab: engineering narrative + recruiter hooks.

Draft prose (Evan to edit the voice). Content is sourced from the
codebase architecture and the career source doc.
"""
from dash import html

REPO_URL = "https://github.com/EvanWAppel/mccoy"
PROFILE_URL = "https://github.com/EvanWAppel"
LINKEDIN_URL = "https://www.linkedin.com/in/evan-appel-8885569b/"
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


def about_tab():
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
                        "Spotify per request, while a weekly Railway "
                        "cron snapshots top artists into Postgres so the "
                        "Trends charts (and this public demo) have "
                        "history to draw on."
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
