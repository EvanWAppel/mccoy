"""Ask Your Listening, owner UI (XX-07).

A question box, then the answer: a one-line summary, the SQL behind a
disclosure, the rows as a table, and a bar chart when the result is a
label/number pair. Owner-only; app.run_ask does the gating.

Everything here renders model and database output as plain Dash text
children. No Markdown, no raw HTML: a cell or SQL string that looks
like markup stays a string.

Errors use the fixed copy below. The exception detail goes to the
server log only, never into the page.
"""

import logging
from decimal import Decimal

import plotly.graph_objects as go
from dash import dcc, html

from ask import ROW_LIMIT, AskResult
from components.trends import CHART_LAYOUT

logger = logging.getLogger(__name__)

# Server-side cap on question length (the box's maxLength is only a
# hint to the browser). Bounds prompt size and so per-call spend.
MAX_QUESTION_CHARS = 500
# A bar chart past this many bars stops being readable.
MAX_CHART_ROWS = 50

ASK_PRIVATE = "Ask is private to the site owner."
ASK_OFF = (
    "Live answers are switched off until the Anthropic API-key "
    "guardrail is cleared."
)
ASK_TOO_LONG = (
    f"Keep the question under {MAX_QUESTION_CHARS} characters."
)
ASK_UNSAFE = (
    "That question produced a query McCoy won't run. Only read-only "
    "queries over the listening marts are allowed."
)
ASK_UNUSABLE = "Couldn't turn that question into a query. Try rewording."
ASK_FAILED = "The query didn't run. The details are in the server log."

_MUTED = {"color": "#6e6b63", "fontSize": "0.85rem", "margin": "8px 0"}


def ask_panel() -> html.Div:
    """The owner's question box, submit button and result area."""
    return html.Div(id="ask-panel", className="ask", children=[
        html.H3("Ask your listening", className="patterns-h"),
        html.P(
            "Ask a question in plain English. Claude writes one "
            "read-only SQL query over the listening marts, and the "
            "app runs it.",
            style=_MUTED,
        ),
        html.Div(className="ask-form", children=[
            dcc.Input(
                id="ask-question",
                type="text",
                placeholder="What did I play most on Sunday nights?",
                maxLength=MAX_QUESTION_CHARS,
                debounce=False,
                n_submit=0,
                className="ask-input",
            ),
            html.Button(
                "Ask", id="ask-submit", n_clicks=0, className="ask-btn"
            ),
        ]),
        dcc.Loading(
            type="circle",
            color="#c4452b",
            children=html.Div(id="ask-result", className="ask-result"),
        ),
    ])


def ask_private_notice() -> html.P:
    return render_message(ASK_PRIVATE)


def render_message(text: str) -> html.P:
    """A fixed notice or error line (never exception text)."""
    return html.P(text, className="ask-message", style=_MUTED)


def _cell(value) -> str:
    return "" if value is None else str(value)


def summarize(result: AskResult) -> str:
    """One plain line describing the result."""
    if not result.rows:
        return "No rows matched."
    if len(result.columns) == 1 and len(result.rows) == 1:
        return f"{result.columns[0]}: {_cell(result.rows[0][0])}"
    noun = "row" if result.row_count == 1 else "rows"
    line = f"{result.row_count} {noun}."
    if result.truncated:
        line += f" Showing the first {ROW_LIMIT}; more matched."
    return line


def _is_number(value) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(
        value, bool
    )


def chart_for(result: AskResult) -> dcc.Graph | None:
    """A bar chart for label/number pairs, else None."""
    rows = result.rows
    if len(result.columns) != 2 or not 2 <= len(rows) <= MAX_CHART_ROWS:
        return None
    if not all(_is_number(r[1]) for r in rows):
        return None
    fig = go.Figure(go.Bar(
        x=[_cell(r[0]) for r in rows],
        y=[float(r[1]) for r in rows],
        marker_color="#c4452b",
    ))
    fig.update_layout(**CHART_LAYOUT, height=260)
    fig.update_xaxes(title_text=result.columns[0])
    fig.update_yaxes(title_text=result.columns[1])
    return dcc.Graph(
        id="ask-chart", figure=fig, config={"displayModeBar": False}
    )


def _table(result: AskResult) -> html.Table:
    return html.Table(id="ask-table", className="ask-table", children=[
        html.Thead(html.Tr([html.Th(c) for c in result.columns])),
        html.Tbody([
            html.Tr([html.Td(_cell(v)) for v in row])
            for row in result.rows
        ]),
    ])


def render_answer(result: AskResult) -> html.Div:
    """Summary, SQL disclosure, table and (maybe) chart."""
    children = [html.P(summarize(result), id="ask-summary",
                       className="ask-summary")]
    chart = chart_for(result)
    if chart is not None:
        children.append(chart)
    if result.rows:
        children.append(_table(result))
    children.append(html.Details(id="ask-sql", className="ask-sql",
                                 children=[
        html.Summary("Show the SQL"),
        html.Pre(html.Code(result.sql)),
    ]))
    return html.Div(id="ask-answer", children=children)
