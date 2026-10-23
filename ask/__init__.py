"""Ask Your Listening (XX-03/XX-04): natural-language question -> SQL.

`ask(question)` sends a schema-aware system prompt plus the question
to Claude, pulls the SQL out of the reply, checks it, then runs it
read-only and returns the rows.

Layers of defence, outermost first:
1. `sql_guard.check_sql`: exactly one read-only SELECT (parser-based).
2. `check_marts_only`: every table is a known `marts.*` dbt model.
3. Execution in a `READ ONLY` transaction with a local statement
   timeout, a row cap via `fetchmany`, and an unconditional rollback.
4. The connection itself comes from `ASK_DATABASE_URL`, which is meant
   to log in as the read-only `marts` role from XX-01. It never falls
   back to the app's `DATABASE_URL`.

The model client and the connection factory are injectable so tests
run offline with fakes. Logs carry the prompt, SQL and row count,
never keys or connection strings.
"""

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psycopg2
import sqlglot
from sqlglot import exp

from sql_guard import DIALECT, UnsafeSQLError, check_sql

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("ASK_MODEL", "claude-opus-5")
MAX_TOKENS = 4096
ROW_LIMIT = 500
STATEMENT_TIMEOUT_MS = 5000
SCHEMA = "marts"

# The dbt marts the model may query: table -> [(column, meaning)].
# tests/test_ask.py checks this against analytics/models/marts/*.sql.
MARTS_SCHEMA: dict[str, list[tuple[str, str]]] = {
    "fct_plays": [
        ("play_id", "text, unique id of one play"),
        ("played_at", "timestamptz, when the play started (UTC)"),
        ("played_at_local", "timestamp, played_at in local time"),
        ("track_id", "text, Spotify track id"),
        ("track_name", "text"),
        ("duration_ms", "int, track length in milliseconds"),
        ("album_name", "text"),
        ("primary_artist_id", "text, Spotify id of the first artist"),
        ("primary_artist_name", "text"),
        ("session_id", "bigint, listening session (30 min gap rule)"),
    ],
    "fct_listening_sessions": [
        ("session_id", "bigint, joins fct_plays.session_id"),
        ("started_at", "timestamptz"),
        ("ended_at", "timestamptz"),
        ("plays", "bigint, plays in the session"),
        ("minutes", "numeric, summed track minutes"),
        ("distinct_artists", "bigint"),
    ],
    "mart_daily_listening": [
        ("listen_date", "date, local calendar day"),
        ("plays", "bigint"),
        ("minutes", "numeric"),
        ("distinct_artists", "bigint"),
    ],
    "mart_hour_of_week": [
        ("iso_dow", "int, local ISO day of week, 1 = Monday"),
        ("hour", "int, local hour of day 0-23"),
        ("plays", "bigint"),
        ("minutes", "numeric"),
    ],
    "mart_artist_streaks": [
        ("artist_id", "text, Spotify artist id"),
        ("artist_name", "text"),
        ("streak_start", "date, first local day of the run"),
        ("streak_end", "date, last local day of the run"),
        ("streak_days", "bigint, consecutive days played"),
    ],
}


class AskError(RuntimeError):
    """The model did not return usable SQL."""


@dataclass(frozen=True)
class AskResult:
    question: str
    sql: str
    columns: list[str]
    rows: list[tuple]
    row_count: int
    truncated: bool


def build_system_prompt() -> str:
    """System prompt describing the marts schema and the SQL rules."""
    lines = [
        "You translate questions about one person's Spotify listening "
        "history into a single PostgreSQL query.",
        "",
        "Rules:",
        "- Reply with exactly one SELECT statement (CTEs allowed) in a "
        "```sql fenced block and nothing else.",
        f"- Query only the tables below, always schema-qualified as "
        f"{SCHEMA}.<table>.",
        "- Never modify data. No INSERT, UPDATE, DELETE, DDL or SET.",
        f"- Results are capped at {ROW_LIMIT} rows; aggregate and add "
        "ORDER BY / LIMIT where it helps.",
        "- Use the *_local columns for day-of-week, hour and date questions.",
        "",
        "Tables:",
    ]
    for table, columns in MARTS_SCHEMA.items():
        lines.append(f"{SCHEMA}.{table}")
        lines.extend(f"  - {col}: {meaning}" for col, meaning in columns)
    return "\n".join(lines)


_FENCE = re.compile(r"```(?:sql)?\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql(reply: str) -> str:
    """The SQL in the first fenced block, or the whole reply if none."""
    match = _FENCE.search(reply)
    return (match.group(1) if match else reply).strip()


def check_marts_only(sql: str) -> None:
    """Raise UnsafeSQLError unless every table is a known mart.

    Unqualified names are allowed only when they name a CTE defined in
    the same query.
    """
    tree = sqlglot.parse_one(sql, read=DIALECT)
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        schema = table.db.lower()
        if not schema and not table.catalog and name in _visible_ctes(table):
            continue
        if table.catalog or schema != SCHEMA or name not in MARTS_SCHEMA:
            log.warning("ask: rejected table %s", table.sql(DIALECT))
            raise UnsafeSQLError(
                f"only {SCHEMA}.* marts may be queried, got "
                f"{table.sql(DIALECT)}"
            )


def _with_clause(node: exp.Expression) -> exp.With | None:
    return node.args.get("with_") or node.args.get("with")


def _visible_ctes(table: exp.Table) -> set[str]:
    """CTE names Postgres would resolve `table` against.

    A CTE is visible inside the query that defines it and its nested
    subqueries, but not outside it, and a CTE body sees only the CTEs
    defined before it (plus itself under WITH RECURSIVE).
    """
    names: set[str] = set()
    child: exp.Expression = table
    node = table.parent
    while node is not None:
        if isinstance(node, exp.With):
            ctes = node.expressions
            idx = next(i for i, c in enumerate(ctes) if c is child)
            stop = idx + 1 if node.args.get("recursive") else idx
            names |= {c.alias_or_name.lower() for c in ctes[:stop]}
        else:
            with_ = _with_clause(node)
            if with_ is not None and with_ is not child:
                names |= {c.alias_or_name.lower() for c in with_.expressions}
        child, node = node, node.parent
    return names


def connect_readonly():
    """Connect with the read-only `marts` role (XX-01).

    Requires ASK_DATABASE_URL; deliberately no fallback to the app's
    read-write DATABASE_URL.
    """
    return psycopg2.connect(os.environ["ASK_DATABASE_URL"])


def default_client():
    """A real Anthropic client. Only built outside tests."""
    import anthropic

    return anthropic.Anthropic()


def _reply_text(response: Any) -> str:
    if response.stop_reason == "refusal":
        raise AskError("model declined the question")
    texts = [b.text for b in response.content if b.type == "text"]
    if not texts:
        raise AskError("model reply had no text")
    return "".join(texts)


def run_readonly(
    conn,
    sql: str,
    *,
    row_limit: int = ROW_LIMIT,
    timeout_ms: int = STATEMENT_TIMEOUT_MS,
) -> tuple[list[str], list[tuple], bool]:
    """Run `sql` in a read-only transaction; always roll back + close.

    Returns (columns, rows, truncated). At most `row_limit` rows are
    returned; one extra is fetched to know whether more existed.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
            cur.execute(sql)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchmany(row_limit + 1)
    finally:
        conn.rollback()
        conn.close()
    truncated = len(rows) > row_limit
    return columns, list(rows[:row_limit]), truncated


def ask(
    question: str,
    *,
    client: Any = None,
    connect: Callable[[], Any] | None = None,
    model: str | None = None,
    row_limit: int = ROW_LIMIT,
) -> AskResult:
    """Answer `question` with SQL over the marts.

    Raises UnsafeSQLError if the model's SQL fails a check (nothing is
    executed), AskError if the reply is unusable. DB errors propagate.
    """
    client = client if client is not None else default_client()
    connect = connect if connect is not None else connect_readonly
    model = model or DEFAULT_MODEL
    system = build_system_prompt()
    log.info("ask: question=%r model=%s", question, model)
    log.info("ask: prompt=%r", system + "\n\nQ: " + question)

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": question}],
    )
    raw_sql = extract_sql(_reply_text(response))
    log.info("ask: sql=%r", raw_sql)

    sql = check_sql(raw_sql)
    check_marts_only(sql)

    columns, rows, truncated = run_readonly(
        connect(), sql, row_limit=row_limit
    )
    log.info("ask: row_count=%d truncated=%s", len(rows), truncated)
    return AskResult(
        question=question,
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )
