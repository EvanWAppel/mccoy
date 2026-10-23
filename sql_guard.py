"""SQL guard for Ask Your Listening (XX-02).

Model-written SQL passes through `check_sql` before it reaches the
database. The guard parses the text with sqlglot (Postgres dialect)
rather than pattern-matching it, and accepts exactly one read-only
query: a SELECT, optionally with CTEs or set operations (UNION etc.).

Everything else is rejected: DML, DDL, session or transaction control,
multiple statements, `SELECT ... INTO`, row locks (`FOR UPDATE`) and
data-modifying CTEs. This is defence in depth; the read-only `marts`
role with a statement timeout and row cap (XX-01) is the backstop.
"""

import logging
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

log = logging.getLogger(__name__)

DIALECT = "postgres"

# Top-level statement types that are read-only queries.
_ALLOWED_ROOTS = (exp.Select, exp.SetOperation)

# Node types that must not appear anywhere in the tree, including
# inside CTEs and subqueries. `Command` is sqlglot's fallback for
# syntax it does not model, so unknown statements are denied too.
_DENIED_NODES = (
    exp.DML,
    exp.DDL,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Grant,
    exp.Revoke,
    exp.Into,
    exp.Lock,
    exp.Pragma,
    exp.Use,
    exp.Kill,
    exp.Analyze,
    exp.LoadData,
    exp.Cache,
    exp.Uncache,
    exp.Refresh,
    exp.Comment,
)

# Postgres functions a SELECT can call to escape the guard: run SQL
# text (query_to_xml), dump other tables (table_to_xml), touch the
# server or files (pg_*, lo_*, dblink) or change session settings
# (set_config). Matched on the lower-cased function name.
_DENIED_FUNCTIONS = re.compile(
    r"^(pg_|lo_|dblink)|_to_xml|^set_config$|^current_setting$"
)


class UnsafeSQLError(ValueError):
    """Raised when SQL is not a single read-only SELECT."""


def check_sql(sql: str) -> str:
    """Return `sql` stripped of whitespace and a trailing `;` if safe.

    Raises UnsafeSQLError unless `sql` is exactly one SELECT statement
    (CTEs and set operations allowed) with no writes, locks or
    session changes anywhere in it. The returned text is the caller's
    original SQL, not a re-rendering, so what runs is what was checked.
    """
    if not isinstance(sql, str):
        raise UnsafeSQLError(f"SQL must be a string, got {type(sql)!r}")

    try:
        parsed = sqlglot.parse(sql, read=DIALECT)
    except SqlglotError as err:
        log.warning("sql_guard: parse failed: %s", err)
        raise UnsafeSQLError(f"SQL could not be parsed: {err}") from err

    statements = [s for s in parsed if s is not None]
    if len(statements) != 1:
        log.warning("sql_guard: rejected %d statements", len(statements))
        raise UnsafeSQLError(
            f"expected a single statement, got {len(statements)}"
        )

    (tree,) = statements
    if not isinstance(tree, _ALLOWED_ROOTS):
        log.warning("sql_guard: rejected root %s", type(tree).__name__)
        raise UnsafeSQLError(
            f"only SELECT is allowed, got {type(tree).__name__}"
        )

    for node in tree.walk():
        if isinstance(node, _DENIED_NODES):
            log.warning(
                "sql_guard: rejected %s inside SELECT",
                type(node).__name__,
            )
            raise UnsafeSQLError(
                "only read-only SELECT is allowed; found "
                f"{type(node).__name__}"
            )
        if isinstance(node, exp.Func):
            name = _func_name(node)
            if _DENIED_FUNCTIONS.search(name):
                log.warning("sql_guard: rejected function %s", name)
                raise UnsafeSQLError(f"function {name}() is not allowed")

    cleaned = sql.strip().rstrip(";").strip()
    log.info("sql_guard: accepted SELECT (%d chars)", len(cleaned))
    return cleaned


def _func_name(node: exp.Func) -> str:
    """Lower-cased SQL name of a function call node."""
    if isinstance(node, exp.Anonymous):
        return node.name.lower()
    return node.sql_name().lower()
