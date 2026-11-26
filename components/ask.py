"""Ask Your Listening panels (XX-07 owner, XX-08 public).

`render_answer` takes the JSON shape from `ask.result_dict` (also what
the public cache stores): a headline for a single value, otherwise a
table, plus a bar chart when the result is label + number, and the SQL
in a disclosure.
"""

import logging
from typing import Any

import plotly.graph_objects as go
from dash import dcc, html

from ask import ROW_LIMIT
from components.trends import CHART_LAYOUT

logger = logging.getLogger(__name__)

SHOWN_ROWS = 50
_MUTED = {"color": "#6e6b63", "fontSize": "0.85rem", "margin": "8px 0"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _chart(result: dict[str, Any]) -> dcc.Graph | None:
    """Bar chart for label + number results with 2+ rows."""
    columns, rows = result["columns"], result["rows"]
    if len(columns) != 2 or len(rows) < 2:
        return None
    if not all(_is_number(r[1]) for r in rows):
        return None
    shown = rows[:SHOWN_ROWS]
    fig = go.Figure(go.Bar(
        x=[str(r[0]) for r in shown],
        y=[r[1] for r in shown],
        marker_color="#c4452b",
        hovertemplate="%{x}: %{y}<extra></extra>",
    ))
    fig.update_layout(**CHART_LAYOUT, height=240)
    fig.update_yaxes(title_text=columns[1])
    return dcc.Graph(id="ask-chart", figure=fig,
                     config={"displayModeBar": False})


def _table(result: dict[str, Any]) -> html.Table:
    return html.Table(
        className="ask-table",
        children=[
            html.Thead(html.Tr([html.Th(c) for c in result["columns"]])),
            html.Tbody([
                html.Tr([html.Td(str(v)) for v in row])
                for row in result["rows"][:SHOWN_ROWS]
            ]),
        ],
    )


def render_answer(result: dict[str, Any]) -> html.Div:
    rows = result["rows"]
    parts: list[Any] = []
    if not rows:
        parts.append(html.P("The query ran but returned no rows.",
                            style=_MUTED))
    elif len(rows) == 1 and len(result["columns"]) == 1:
        parts.append(html.Div([
            html.Strong(str(rows[0][0])),
            html.Span(result["columns"][0]),
        ], className="ask-headline"))
    else:
        chart = _chart(result)
        if chart is not None:
            parts.append(chart)
        parts.append(_table(result))
        if len(rows) > SHOWN_ROWS:
            parts.append(html.P(
                f"Showing the first {SHOWN_ROWS} of {len(rows)} rows.",
                style=_MUTED,
            ))
    if result.get("truncated"):
        parts.append(html.P(
            f"Results are capped at {ROW_LIMIT} rows; there were more.",
            style=_MUTED,
        ))
    parts.append(html.Details(
        className="ask-sql",
        children=[html.Summary("SQL"), html.Pre(result["sql"])],
    ))
    return html.Div(parts, className="ask-answer")


def render_ask_message(title: str, detail: str) -> html.Div:
    """A blocked / failed question: what happened, in the owner's view."""
    return html.Div(
        className="ask-message",
        children=[html.Strong(title), html.P(detail, style=_MUTED)],
    )


def ask_owner_panel() -> html.Div:
    return html.Div(
        className="ask-panel",
        children=[
            html.P(
                "Ask a question about your listening. Claude writes one "
                "read-only SQL query over the dbt marts; it runs as a "
                "read-only role with a 5-second timeout.",
                style=_MUTED,
            ),
            html.Div(
                className="ask-form",
                children=[
                    dcc.Input(
                        id="ask-question",
                        type="text",
                        debounce=False,
                        placeholder="What did I play most on Sunday "
                        "nights?",
                        className="ask-input",
                    ),
                    html.Button("Ask", id="ask-submit", n_clicks=0,
                                className="ask-button"),
                ],
            ),
            dcc.Loading(
                type="circle", color="#c4452b",
                children=html.Div(id="ask-result"),
            ),
        ],
    )


def ask_public_panel(entries: list[dict[str, Any]]) -> html.Div:
    return html.Div(
        className="ask-panel",
        children=[
            html.P(
                "Ask Your Listening: Claude turns a question into one "
                "read-only SQL query over the dbt marts. Live questions "
                "are owner-only; these curated answers run over sample "
                "data.",
                style=_MUTED,
            ),
            *[
                html.Section(
                    className="ask-cached",
                    children=[html.H4(e["question"]), render_answer(e)],
                )
                for e in entries
            ],
        ],
    )
