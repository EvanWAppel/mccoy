"""Eval runner for Ask Your Listening (XX-05).

An eval case is a question, a recorded model reply and the expected
outcome over the fixture marts database (tests/evals/). `run_case`
pushes the case through the real `ask()` pipeline: SQL extraction,
the guard, the marts allow-list and read-only execution. By default
the model is a `ReplayClient` that returns the recorded reply, so the
set runs offline in the normal pytest run.

The opt-in live command (XX-06) reuses `run_case` with a real client:

    uv run python -m ask.evals                  # offline replay
    uv run python -m ask.evals --live           # real model, reports
    uv run python -m ask.evals --live --record  # ...and re-records

A live run needs ANTHROPIC_API_KEY and TEST_DATABASE_URL (the fixture
marts are loaded into a throwaway database there and dropped after).
It judges rows strictly but column names loosely, since the model
picks its own aliases, and counts an attack as passed if it was
stopped either way (guard or refusal). `--record` writes the live
replies of passing answerable cases back into cases.json.
"""

import argparse
import datetime as dt
import json
import logging
import os
import sys
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg2
from psycopg2.extensions import make_dsn

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
    reply: str | None = None


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


class RecordingClient:
    """Wraps a model client and keeps the last reply's text, so a live
    run can write it back into cases.json."""

    def __init__(self, inner: Any):
        self.inner = inner
        self.reply: str | None = None
        self.stop_reason: str | None = None
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        response = self.inner.messages.create(**kwargs)
        self.stop_reason = response.stop_reason
        self.reply = "".join(
            b.text for b in response.content if b.type == "text"
        )
        return response


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
    *,
    strict_columns: bool = True,
    model: str | None = None,
) -> EvalResult:
    """Run one case through `ask()` and compare with its expectation.

    Guard rejections and refusals become `error` results; anything
    else (DB errors, bugs) propagates. With `strict_columns=False`
    (live runs) column names aren't compared, and an expected error is
    met by either kind of stop.
    """
    recorder = RecordingClient(
        client if client is not None else ReplayClient(case)
    )
    expected_error = case.expect.get("error")
    try:
        answer = ask.ask(
            case.question, client=recorder, connect=connect, model=model
        )
    except tuple(ERRORS.values()) as err:
        kind = next(k for k, e in ERRORS.items() if isinstance(err, e))
        if strict_columns:
            passed = kind == expected_error
        else:
            passed = expected_error is not None
        message = (
            f"{case.id}: {kind} as expected"
            if passed
            else f"{case.id}: expected "
            f"{expected_error or 'rows'}, got {kind}: {err}"
        )
        log.info("evals: %s passed=%s", case.id, passed)
        return EvalResult(
            case.id, passed, message, error=kind, reply=recorder.reply
        )

    columns = list(answer.columns)
    rows = [[normalize(v) for v in row] for row in answer.rows]
    problems = []
    if expected_error:
        problems.append(f"expected {expected_error}, but the SQL ran")
    else:
        if strict_columns and columns != case.expect["columns"]:
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
        reply=recorder.reply,
    )


def record_replies(
    results: list[EvalResult], model: str, path: Path = CASES_PATH
) -> list[str]:
    """Write the replies of passing answerable cases back to `path`.

    Attack and refusal cases keep their hand-authored replies: they
    exist to exercise the guard, whatever a live model says. Returns
    the ids written; the file is untouched if there are none.
    """
    data = json.loads(path.read_text())
    passing = {
        r.case_id: r.reply
        for r in results
        if r.passed and r.error is None and r.reply is not None
    }
    written = []
    for raw in data["cases"]:
        if raw["id"] in passing and "error" not in raw["expect"]:
            raw["reply"] = passing[raw["id"]]
            written.append(raw["id"])
    if written:
        data["recorded_with"] = model
        path.write_text(json.dumps(data, indent=2) + "\n")
    log.info("evals: recorded %d replies with %s", len(written), model)
    return written


def default_client() -> Any:
    """The real Anthropic client (needs ANTHROPIC_API_KEY)."""
    return ask.default_client()


@contextmanager
def fixture_database() -> Iterator[Callable[[], Any]]:
    """Load the fixture marts into a throwaway database on
    TEST_DATABASE_URL; yield a connection factory; drop it after."""
    base = os.environ["TEST_DATABASE_URL"]
    name = f"mccoy_evals_{uuid.uuid4().hex[:8]}"
    admin = psycopg2.connect(base)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    dsn = make_dsn(base, dbname=name)
    log.info("evals: fixture database %s", name)
    try:
        conn = psycopg2.connect(dsn)
        with conn, conn.cursor() as cur:
            cur.execute(FIXTURE_SQL.read_text())
        conn.close()
        yield lambda: psycopg2.connect(dsn)
    finally:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.close()


def main(argv: list[str] | None = None) -> int:
    """Run the eval set; exit status 0 only if every case passed."""
    parser = argparse.ArgumentParser(
        prog="python -m ask.evals",
        description="Run the Ask Your Listening eval set.",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="call the real model instead of replaying recorded replies",
    )
    parser.add_argument(
        "--record", action="store_true",
        help="with --live: write passing replies back to cases.json",
    )
    parser.add_argument("--model", default=ask.DEFAULT_MODEL)
    args = parser.parse_args(argv)
    if args.record and not args.live:
        parser.error("--record needs --live")

    cases = load_cases(CASES_PATH)
    client = default_client() if args.live else None
    with fixture_database() as connect:
        results = [
            run_case(
                case,
                connect,
                client=client,
                strict_columns=not args.live,
                model=args.model,
            )
            for case in cases
        ]
    for result in results:
        print(("PASS " if result.passed else "FAIL ") + result.message)
    passed = sum(r.passed for r in results)
    mode = f"live ({args.model})" if args.live else "replay"
    print(f"{passed}/{len(results)} passed, {mode}")
    if args.record:
        written = record_replies(results, args.model, path=CASES_PATH)
        print(f"recorded {len(written)} replies into {CASES_PATH}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
