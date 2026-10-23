"""Eval runner for Ask Your Listening (XX-05).

An eval case is a question, a recorded model reply and the expected
outcome over the fixture marts database (tests/evals/). `run_case`
pushes the case through the real `ask()` pipeline: SQL extraction,
the guard, the marts allow-list and read-only execution. By default
the model is a `ReplayClient` that returns the recorded reply, so the
set runs offline in the normal pytest run.

The opt-in live command (XX-06) will reuse `run_case` with a real
client in place of the replay.
"""

import datetime as dt
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import ask
from sql_guard import UnsafeSQLError

log = logging.getLogger(__name__)

EVALS_DIR = Path(__file__).resolve().parent.parent / "tests" / "evals"
CASES_PATH = EVALS_DIR / "cases.json"
FIXTURE_SQL = EVALS_DIR / "fixture_marts.sql"

# Expected error kinds -> the exception `ask()` raises for them.
ERRORS: dict[str, type[Exception]] = {
    "unsafe": UnsafeSQLError,
    "refused": ask.AskError,
}


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    reply: str
    expect: dict[str, Any]
    stop_reason: str = "end_turn"


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    passed: bool
    message: str
    error: str | None = None
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)


def _validate(raw: dict[str, Any]) -> EvalCase:
    case_id = raw.get("id", "?")
    expect = raw.get("expect")
    if not isinstance(expect, dict) or not expect:
        raise ValueError(f"case {case_id}: missing expect")
    if "error" in expect:
        if expect["error"] not in ERRORS:
            raise ValueError(
                f"case {case_id}: unknown error {expect['error']!r}, "
                f"expected one of {sorted(ERRORS)}"
            )
    elif not {"columns", "rows"} <= expect.keys():
        raise ValueError(
            f"case {case_id}: expect needs columns+rows or error"
        )
    return EvalCase(
        id=raw["id"],
        question=raw["question"],
        reply=raw["reply"],
        expect=expect,
        stop_reason=raw.get("stop_reason", "end_turn"),
    )


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    """Load and validate the eval set; ids must be unique."""
    cases = [_validate(raw) for raw in json.loads(path.read_text())["cases"]]
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise ValueError(f"duplicate case id {case.id!r}")
        seen.add(case.id)
    return cases


class ReplayClient:
    """Stands in for `anthropic.Anthropic`, replaying one recorded reply.

    Shaped like the SDK response as far as `ask` reads it:
    `.content[i].type/.text` and `.stop_reason`.
    """

    def __init__(self, case: EvalCase):
        self.case = case
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        block = SimpleNamespace(type="text", text=self.case.reply)
        return SimpleNamespace(
            content=[block], stop_reason=self.case.stop_reason
        )


def normalize(value: Any) -> Any:
    """Make a DB value comparable with JSON: numerics -> float, dates
    and timestamps -> ISO strings."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def run_case(
    case: EvalCase,
    connect: Callable[[], Any],
    client: Any = None,
) -> EvalResult:
    """Run one case through `ask()` and compare with its expectation.

    Guard rejections and refusals become `error` results; anything
    else (DB errors, bugs) propagates.
    """
    client = client if client is not None else ReplayClient(case)
    expected_error = case.expect.get("error")
    try:
        answer = ask.ask(case.question, client=client, connect=connect)
    except tuple(ERRORS.values()) as err:
        kind = next(k for k, e in ERRORS.items() if isinstance(err, e))
        passed = kind == expected_error
        message = (
            f"{case.id}: {kind} as expected"
            if passed
            else f"{case.id}: expected "
            f"{expected_error or 'rows'}, got {kind}: {err}"
        )
        log.info("evals: %s passed=%s", case.id, passed)
        return EvalResult(case.id, passed, message, error=kind)

    columns = list(answer.columns)
    rows = [[normalize(v) for v in row] for row in answer.rows]
    problems = []
    if expected_error:
        problems.append(f"expected {expected_error}, but the SQL ran")
    else:
        if columns != case.expect["columns"]:
            problems.append(
                f"columns {columns} != {case.expect['columns']}"
            )
        if rows != case.expect["rows"]:
            problems.append(f"rows {rows} != {case.expect['rows']}")
    passed = not problems
    message = f"{case.id}: " + ("ok" if passed else "; ".join(problems))
    log.info("evals: %s passed=%s", case.id, passed)
    return EvalResult(
        case.id,
        passed,
        message,
        sql=answer.sql,
        columns=columns,
        rows=rows,
    )
