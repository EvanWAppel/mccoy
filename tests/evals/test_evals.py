"""Offline eval set for Ask Your Listening (XX-05).

Recorded model replies (cases.json) are replayed through the real
`ask()` pipeline: SQL extraction, the guard, the marts allow-list and
read-only execution against a fixture Postgres database
(fixture_marts.sql). No network call, no API key.

The checks that need no database (case-file shape, fixture/schema
drift, guard verdicts, the runner itself) always run. The end-to-end
cases need TEST_DATABASE_URL like the other Postgres tests; CI sets it.
"""

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp

import ask
from ask import evals
from sql_guard import DIALECT, UnsafeSQLError, check_sql

HERE = Path(__file__).parent
CASES = evals.load_cases()
ANSWERABLE = [c for c in CASES if "rows" in c.expect]
UNSAFE = [c for c in CASES if c.expect.get("error") == "unsafe"]


def ids(cases):
    return [c.id for c in cases]


# --- the case file ------------------------------------------------------


def test_default_paths_are_in_tests_evals():
    assert evals.CASES_PATH == HERE / "cases.json"
    assert evals.FIXTURE_SQL == HERE / "fixture_marts.sql"


def test_case_ids_unique():
    assert len(ids(CASES)) == len(set(ids(CASES)))


def test_set_covers_answers_and_attacks():
    assert len(ANSWERABLE) >= 6
    assert len(UNSAFE) >= 3
    assert any(c.expect.get("error") == "refused" for c in CASES)


def test_every_mart_is_exercised():
    used = set()
    for case in ANSWERABLE:
        tree = sqlglot.parse_one(ask.extract_sql(case.reply), read=DIALECT)
        used |= {t.name for t in tree.find_all(exp.Table) if t.db}
    assert used == set(ask.MARTS_SCHEMA)


@pytest.mark.parametrize(
    "bad, match",
    [
        ({"id": "x", "question": "q", "reply": "r"}, "expect"),
        (
            {"id": "x", "question": "q", "reply": "r", "expect": {}},
            "expect",
        ),
        (
            {
                "id": "x",
                "question": "q",
                "reply": "r",
                "expect": {"error": "nope"},
            },
            "error",
        ),
    ],
)
def test_load_cases_rejects_malformed(tmp_path, bad, match):
    path = tmp_path / "cases.json"
    path.write_text(evals.json.dumps({"cases": [bad]}))
    with pytest.raises(ValueError, match=match):
        evals.load_cases(path)


def test_load_cases_rejects_duplicate_ids(tmp_path):
    case = {"id": "x", "question": "q", "reply": "r", "expect": {
        "error": "unsafe"}}
    path = tmp_path / "cases.json"
    path.write_text(evals.json.dumps({"cases": [case, case]}))
    with pytest.raises(ValueError, match="duplicate"):
        evals.load_cases(path)


# --- fixture database stays in step with the marts ------------------------


def test_fixture_tables_match_marts_schema():
    statements = sqlglot.parse(evals.FIXTURE_SQL.read_text(), read=DIALECT)
    tables = {}
    for stmt in statements:
        if isinstance(stmt, exp.Create) and stmt.kind == "TABLE":
            schema = stmt.this
            assert schema.this.db == "marts"
            tables[schema.this.name] = [
                c.name for c in schema.expressions
                if isinstance(c, exp.ColumnDef)
            ]
    expected = {
        table: [col for col, _ in cols]
        for table, cols in ask.MARTS_SCHEMA.items()
    }
    assert tables == expected


# --- guard verdicts (no database) -----------------------------------------


@pytest.mark.parametrize("case", ANSWERABLE, ids=ids(ANSWERABLE))
def test_answerable_replies_pass_guard(case):
    sql = check_sql(ask.extract_sql(case.reply))
    ask.check_marts_only(sql)


@pytest.mark.parametrize("case", UNSAFE, ids=ids(UNSAFE))
def test_unsafe_replies_never_reach_db(case):
    result = evals.run_case(case, connect=pytest.fail)
    assert result.passed, result.message
    assert result.error == "unsafe"


def test_refusal_case_never_reaches_db():
    (case,) = [c for c in CASES if c.expect.get("error") == "refused"]
    result = evals.run_case(case, connect=pytest.fail)
    assert result.passed, result.message


# --- the runner -----------------------------------------------------------


def test_replay_client_returns_recorded_reply():
    case = CASES[0]
    client = evals.ReplayClient(case)
    response = client.messages.create(
        model="m", max_tokens=1, system="s", messages=[]
    )
    assert response.content[0].type == "text"
    assert response.content[0].text == case.reply
    assert response.stop_reason == "end_turn"
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("16.70"), 16.7),
        (dt.date(2026, 10, 20), "2026-10-20"),
        (dt.datetime(2026, 10, 20, 21, 30), "2026-10-20T21:30:00"),
        (4, 4),
        ("Low", "Low"),
        (None, None),
    ],
)
def test_normalize(value, expected):
    assert evals.normalize(value) == expected


def test_run_case_passes_on_matching_rows(ask_conn):
    case = evals.EvalCase(
        id="t",
        question="q",
        reply="SELECT 1",
        expect={"columns": ["artist", "plays"],
                "rows": [["Bon Iver", 12], ["Low", 7]]},
    )
    result = evals.run_case(case, connect=lambda: ask_conn)
    assert result.passed, result.message


def test_run_case_reports_wrong_rows(ask_conn):
    case = evals.EvalCase(
        id="t",
        question="q",
        reply="SELECT 1",
        expect={"columns": ["artist", "plays"], "rows": [["Low", 7]]},
    )
    result = evals.run_case(case, connect=lambda: ask_conn)
    assert not result.passed
    assert "rows" in result.message


def test_run_case_reports_unexpected_rejection():
    case = evals.EvalCase(
        id="t",
        question="q",
        reply="DROP TABLE marts.fct_plays",
        expect={"columns": ["n"], "rows": [[1]]},
    )
    result = evals.run_case(case, connect=pytest.fail)
    assert not result.passed
    assert result.error == "unsafe"


def test_run_case_reports_missed_attack(ask_conn):
    case = evals.EvalCase(
        id="t", question="q", reply="SELECT 1", expect={"error": "unsafe"}
    )
    result = evals.run_case(case, connect=lambda: ask_conn)
    assert not result.passed


def test_run_case_uses_injected_client(ask_conn, fake_model):
    """XX-06 passes a live client here instead of the replay."""
    case = evals.EvalCase(
        id="t",
        question="Who?",
        reply="ignored",
        expect={"columns": ["artist", "plays"],
                "rows": [["Bon Iver", 12], ["Low", 7]]},
    )
    result = evals.run_case(
        case, connect=lambda: ask_conn, client=fake_model
    )
    assert result.passed, result.message
    assert fake_model.calls[0]["messages"][0]["content"] == "Who?"


def test_db_errors_propagate(ask_conn, mock_cursor):
    mock_cursor.execute.side_effect = [None, None, RuntimeError("boom")]
    case = evals.EvalCase(
        id="t", question="q", reply="SELECT 1",
        expect={"columns": ["n"], "rows": [[1]]},
    )
    with pytest.raises(RuntimeError, match="boom"):
        evals.run_case(case, connect=lambda: ask_conn)


# --- end to end over the fixture database ---------------------------------


@pytest.mark.parametrize("case", CASES, ids=ids(CASES))
def test_eval_case(case, eval_db_connect):
    result = evals.run_case(case, connect=eval_db_connect)
    assert result.passed, result.message


def test_fixture_db_untouched_after_evals(eval_db_connect):
    conn = eval_db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM marts.fct_plays")
            assert cur.fetchone() == (10,)
    finally:
        conn.close()


def test_unsafe_error_type_is_guard_error():
    """`error: unsafe` means sql_guard/marts check said no."""
    assert evals.ERRORS["unsafe"] is UnsafeSQLError
    assert evals.ERRORS["refused"] is ask.AskError
