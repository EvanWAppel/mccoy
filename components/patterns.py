"""Listening Patterns: hour-of-week heatmap, daily minutes, streaks.

Fed by the dbt marts (owner view) or demo_data.demo_patterns() (public
view, which is always demo data by Evan's choice).
"""

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
from dash import dcc, html

from components.trends import CHART_LAYOUT

logger = logging.getLogger(__name__)

# Must match vars.listening_tz in analytics/dbt_project.yml (a test
# enforces this) so "today" lines up with the marts' local dates.
LISTENING_TZ = "America/Los_Angeles"

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MUTED = {"color": "#6e6b63", "fontSize": "0.85rem", "margin": "8px 0"}


def day_streaks(days, today: date) -> tuple[int, int]:
    """(current, longest) runs of consecutive listening days.

    A run ending yesterday still counts as current (today isn't over).
    """
    unique = sorted(set(days))
    if not unique:
        return 0, 0
    longest = run = 1
    for prev, cur in zip(unique, unique[1:]):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        longest = max(longest, run)
    current = 0
    if unique[-1] >= today - timedelta(days=1):
        current = 1
        for prev, cur in zip(reversed(unique[:-1]), reversed(unique)):
            if cur - prev != timedelta(days=1):
                break
            current += 1
    return current, longest


def _heatmap(hour_of_week: list[dict]) -> dcc.Graph:
    z = [[0] * 24 for _ in range(7)]
    for row in hour_of_week:
        z[row["iso_dow"] - 1][row["hour"]] = row["plays"]
    fig = go.Figure(go.Heatmap(
        z=z,
        x=[f"{h:02d}" for h in range(24)],
        y=_DAYS,
        colorscale=[[0, "#eeeadf"], [1, "#c4452b"]],
        hovertemplate="%{y} %{x}:00 — %{z} plays<extra></extra>",
        showscale=False,
        xgap=2, ygap=2,
    ))
    fig.update_layout(**CHART_LAYOUT, height=280)
    fig.update_yaxes(autorange="reversed")
    return dcc.Graph(id="patterns-heatmap", figure=fig,
                     config={"displayModeBar": False})


def _daily(daily: list[dict]) -> dcc.Graph:
    recent = daily[-30:]
    fig = go.Figure(go.Bar(
        x=[d["listen_date"] for d in recent],
        y=[d["minutes"] for d in recent],
        marker_color="#c4452b",
        hovertemplate="%{x|%b %d}: %{y:.0f} min<extra></extra>",
    ))
    fig.update_layout(**CHART_LAYOUT, height=220)
    fig.update_yaxes(title_text="minutes")
    return dcc.Graph(id="patterns-daily", figure=fig,
                     config={"displayModeBar": False})


def _stat(label: str, value: str) -> html.Div:
    return html.Div(className="patterns-stat", children=[
        html.Div(value, className="patterns-stat-value"),
        html.Div(label, className="patterns-stat-label"),
    ])


def render_patterns(data: dict, is_demo: bool, today=None) -> html.Div:
    hour_of_week = data.get("hour_of_week") or []
    daily = data.get("daily") or []
    streaks = data.get("streaks") or []
    caption = (
        [html.P("Sample data — the owner's real listening patterns "
                "are private.", style=_MUTED)]
        if is_demo else []
    )
    if not (hour_of_week or daily or streaks):
        return html.Div(caption + [html.P(
            "No play history yet — the hourly pipeline fills this in.",
            style=_MUTED,
        )])

    today = today or datetime.now(ZoneInfo(LISTENING_TZ)).date()
    current, longest = day_streaks(
        [d["listen_date"] for d in daily], today
    )
    stats = [
        _stat("day listening streak", f"{current}"),
        _stat("longest streak", f"{longest} days"),
    ]
    if streaks:
        top = streaks[0]
        stats.append(_stat(
            "longest artist run",
            f"{top['artist_name']} · {top['streak_days']} days",
        ))
    return html.Div(className="patterns", children=caption + [
        html.Div(stats, className="patterns-stats"),
        html.H3("When I listen", className="patterns-h"),
        _heatmap(hour_of_week),
        html.H3("Minutes per day, last 30 days", className="patterns-h"),
        _daily(daily),
    ])
