"""Opt-in live eval command (XX-06): `python -m ask.evals --live`.

No test here makes a network call: the "live" client is always a fake.
What's checked is how a live run is judged (rows strict, column names
loose; attacks pass when stopped either way), how replies are recorded
back into cases.json, and the command-line wiring.
"""

import json

import pytest

from ask import evals

ROWS = {"columns": ["artist", "plays"],
        "rows": [["Bon Iver", 12], ["Low", 7]]}


def case(**kw):
    base = {"id": "t", "question": "q", "reply": "SELECT 1", "expect": ROWS}
    return evals.EvalCase(**{**base, **kw})


# --- judging a live run ---------------------------------------------------


def test_loose_columns_pass_with_other_aliases(ask_conn):
    c = case(expect={"columns": ["who", "n"], "rows": ROWS["rows"]})
    result = evals.run_case(
        c, connect=lambda: ask_conn, strict_columns=False
    )
    assert result.passed, result.message
    assert result.columns == ["artist", "plays"]


def test_strict_columns_is_the_default(ask_conn):
    c = case(expect={"columns": ["who", "n"], "rows": ROWS["rows"]})
    result = evals.run_case(c, connect=lambda: ask_conn)
    assert not result.passed
    assert "columns" in result.message


def test_loose_columns_still_compare_rows(ask_conn):
    c = case(expect={"columns": ["artist", "plays"], "rows": [["Low", 7]]})
    result = evals.run_case(
        c, connect=lambda: ask_conn, strict_columns=False
    )
    assert not result.passed
    assert "rows" in result.message


def test_any_stop_satisfies_an_attack_when_loose():
    """Live, a model may decline in prose (guard: unsafe) or refuse."""
    c = case(reply="", stop_reason="refusal", expect={"error": "unsafe"})
    result = evals.run_case(c, connect=pytest.fail, strict_columns=False)
    assert result.passed, result.message
    assert result.error == "refused"


def test_error_kind_must_match_when_strict():
    c = case(reply="", stop_reason="refusal", expect={"error": "unsafe"})
    result = evals.run_case(c, connect=pytest.fail)
    assert not result.passed


def test_attack_fails_if_sql_ran_even_when_loose(ask_conn):
    c = case(expect={"error": "unsafe"})
    result = evals.run_case(
        c, connect=lambda: ask_conn, strict_columns=False
    )
    assert not result.passed


# --- capturing the live reply ---------------------------------------------


def test_recording_client_keeps_reply_text(fake_model):
    fake_model.reply = "```sql\nSELECT 2\n```"
    client = evals.RecordingClient(fake_model)
    client.messages.create(model="m", max_tokens=1, system="s", messages=[])
    assert client.reply == "```sql\nSELECT 2\n```"
    assert client.stop_reason == "end_turn"
    assert len(fake_model.calls) == 1


def test_run_case_records_reply_on_result(ask_conn, fake_model):
    fake_model.reply = "SELECT 1"
    result = evals.run_case(
        case(), connect=lambda: ask_conn, client=fake_model
    )
    assert result.reply == "SELECT 1"


# --- writing replies back ---------------------------------------------------


@pytest.fixture
def cases_file(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "about": "x",
        "recorded_with": "hand-authored",
        "cases": [
            {"id": "a", "question": "qa", "reply": "old a",
             "expect": ROWS},
            {"id": "b", "question": "qb", "reply": "old b",
             "expect": ROWS},
            {"id": "c", "question": "qc", "reply": "old c",
             "expect": {"error": "unsafe"}},
        ],
    }))
    return path


def test_record_replies_updates_passing_answerable_cases(cases_file):
    results = [
        evals.EvalResult("a", True, "ok", reply="new a"),
        evals.EvalResult("b", False, "bad", reply="new b"),
        evals.EvalResult("c", True, "ok", error="refused", reply="no"),
    ]
    written = evals.record_replies(results, "claude-x", path=cases_file)
    data = json.loads(cases_file.read_text())
    replies = {c["id"]: c["reply"] for c in data["cases"]}
    assert replies == {"a": "new a", "b": "old b", "c": "old c"}
    assert data["recorded_with"] == "claude-x"
    assert data["about"] == "x"
    assert written == ["a"]


def test_record_replies_leaves_file_alone_when_nothing_passes(cases_file):
    before = cases_file.read_text()
    results = [evals.EvalResult("a", False, "bad", reply="new a")]
    assert evals.record_replies(results, "m", path=cases_file) == []
    assert cases_file.read_text() == before


# --- the command ------------------------------------------------------------


@pytest.fixture
def cli(monkeypatch, ask_conn, cases_file):
    """`main()` wired to fakes: no network, no real database."""
    made = []

    def client_factory():
        from tests.conftest import FakeModelClient

        client = FakeModelClient(reply="SELECT 1")
        made.append(client)
        return client

    monkeypatch.setattr(evals, "default_client", client_factory)
    monkeypatch.setattr(
        evals, "fixture_database", lambda: _const_ctx(lambda: ask_conn)
    )
    monkeypatch.setattr(evals, "CASES_PATH", cases_file)
    return made


class _const_ctx:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, *exc):
        return False


def test_offline_run_uses_replay(cli):
    code = evals.main([])
    assert cli == []
    # "old a" isn't SQL, so the replayed answerable cases fail.
    assert code == 1


def test_live_run_uses_real_client_per_case(cli):
    code = evals.main(["--live"])
    assert len(cli) == 1
    assert len(cli[0].calls) == 3
    # a, b: rows match loosely; c: the attack ran -> fail.
    assert code == 1


def test_live_run_passes_model_through(cli):
    evals.main(["--live", "--model", "claude-test"])
    assert {c["model"] for c in cli[0].calls} == {"claude-test"}


def test_live_record_writes_back(cli, cases_file):
    evals.main(["--live", "--record", "--model", "claude-test"])
    data = json.loads(cases_file.read_text())
    assert data["recorded_with"] == "claude-test"
    assert data["cases"][0]["reply"] == "SELECT 1"
    assert data["cases"][2]["reply"] == "old c"


def test_record_requires_live(cli):
    with pytest.raises(SystemExit) as exc:
        evals.main(["--record"])
    assert exc.value.code == 2


def test_fixture_database_needs_test_database_url(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(KeyError, match="TEST_DATABASE_URL"):
        with evals.fixture_database():
            pass


def test_fixture_database_loads_and_drops(monkeypatch):
    import os

    import psycopg2

    if not os.environ.get("TEST_DATABASE_URL"):
        if os.environ.get("REQUIRE_PG_TESTS"):
            pytest.fail("REQUIRE_PG_TESTS set but TEST_DATABASE_URL isn't")
        pytest.skip("TEST_DATABASE_URL not set; Postgres tests skipped")
    with evals.fixture_database() as connect:
        conn = connect()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM marts.fct_plays")
            assert cur.fetchone() == (10,)
            cur.execute("SELECT current_database()")
            (name,) = cur.fetchone()
        conn.close()
    admin = psycopg2.connect(os.environ["TEST_DATABASE_URL"])
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        assert cur.fetchone() is None
    admin.close()


def test_record_also_writes_live_columns(cases_file):
    """Offline replay is strict on columns, so recorded aliases must
    become the expectation or the next pytest run fails."""
    results = [evals.EvalResult("a", True, "ok", reply="new a",
                                columns=["who", "n"])]
    evals.record_replies(results, "m", path=cases_file)
    data = json.loads(cases_file.read_text())
    assert data["cases"][0]["expect"]["columns"] == ["who", "n"]
    assert data["cases"][0]["expect"]["rows"] == ROWS["rows"]
