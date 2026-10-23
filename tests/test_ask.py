"""Tests for `ask(question)` (XX-03): schema-aware prompt, SQL guard,
read-only execution. The model client is a fake (see conftest); no
test makes a network call or reads an API key.
"""

import logging
import re
from pathlib import Path

import pytest

import ask
from sql_guard import UnsafeSQLError

MARTS_DIR = Path(__file__).parent.parent / "analytics/models/marts"


def executed(cursor):
    return [c.args[0] for c in cursor.execute.call_args_list]


# --- prompt -----------------------------------------------------------


def test_prompt_lists_every_mart_and_its_columns():
    prompt = ask.build_system_prompt()
    for table, columns in ask.MARTS_SCHEMA.items():
        assert f"marts.{table}" in prompt
        for column, _ in columns:
            assert column in prompt


def test_schema_covers_every_dbt_mart():
    models = {p.stem for p in MARTS_DIR.glob("*.sql")}
    assert set(ask.MARTS_SCHEMA) == models


@pytest.mark.parametrize("table", sorted(ask.MARTS_SCHEMA))
def test_schema_columns_exist_in_dbt_model(table):
    """Drift guard: every documented column is produced by the model."""
    sql = (MARTS_DIR / f"{table}.sql").read_text()
    for column, _ in ask.MARTS_SCHEMA[table]:
        assert re.search(rf"\b{column}\b", sql), (table, column)


def test_prompt_states_read_only_rules():
    prompt = ask.build_system_prompt().lower()
    assert "select" in prompt
    assert "postgres" in prompt
    assert "marts." in prompt


def test_ask_sends_schema_prompt_and_question(fake_model, ask_conn):
    ask.ask(
        "Who did I play most?", client=fake_model, connect=lambda: ask_conn
    )
    (call,) = fake_model.calls
    assert call["system"] == ask.build_system_prompt()
    assert call["messages"] == [
        {"role": "user", "content": "Who did I play most?"}
    ]
    assert call["model"] == ask.DEFAULT_MODEL
    assert call["max_tokens"] > 0


def test_model_overridable(fake_model, ask_conn):
    ask.ask(
        "q", client=fake_model, connect=lambda: ask_conn, model="claude-test"
    )
    assert fake_model.calls[0]["model"] == "claude-test"


# --- extracting SQL from the reply ----------------------------------


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("SELECT 1", "SELECT 1"),
        ("  SELECT 1;\n", "SELECT 1;"),
        ("```sql\nSELECT 1\n```", "SELECT 1"),
        ("Here you go:\n```SQL\nSELECT 2\n```\nDone.", "SELECT 2"),
        ("```\nSELECT 3\n```", "SELECT 3"),
    ],
)
def test_extract_sql(reply, expected):
    assert ask.extract_sql(reply) == expected


# --- guard ------------------------------------------------------------


def test_unsafe_sql_never_reaches_db(fake_model, ask_conn, mock_cursor):
    fake_model.reply = "DELETE FROM marts.fct_plays"
    connect_calls = []

    def connect():
        connect_calls.append(1)
        return ask_conn

    with pytest.raises(UnsafeSQLError):
        ask.ask("wipe it", client=fake_model, connect=connect)
    assert connect_calls == []
    mock_cursor.execute.assert_not_called()


def test_multi_statement_rejected(fake_model, ask_conn):
    fake_model.reply = "SELECT 1; DROP TABLE marts.fct_plays"
    with pytest.raises(UnsafeSQLError):
        ask.ask("q", client=fake_model, connect=lambda: ask_conn)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM raw_plays",
        "SELECT * FROM public.stored_token",
        "SELECT * FROM staging.stg_plays",
        "SELECT * FROM marts.not_a_mart",
        "SELECT * FROM pg_catalog.pg_roles",
        # A CTE name only covers its own query scope: the outer
        # `stored_token` here is the real table, not the inner CTE.
        "SELECT * FROM stored_token, (WITH stored_token AS (SELECT 1) "
        "SELECT * FROM stored_token) s",
        # A CTE is not visible to the CTEs defined before it.
        "WITH a AS (SELECT * FROM stored_token), "
        "stored_token AS (SELECT 1) SELECT * FROM a",
    ],
)
def test_tables_outside_marts_rejected(sql):
    with pytest.raises(UnsafeSQLError):
        ask.check_marts_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM marts.fct_plays",
        "WITH t AS (SELECT * FROM marts.fct_plays) SELECT * FROM t",
        "SELECT a.* FROM marts.fct_plays a "
        "JOIN marts.fct_listening_sessions s USING (session_id)",
        "SELECT 1",
        "WITH a AS (SELECT * FROM marts.fct_plays), "
        "b AS (SELECT * FROM a) SELECT * FROM b",
        "WITH t AS (SELECT 1 AS x) SELECT x FROM t UNION SELECT x FROM t",
        "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL "
        "SELECT n + 1 FROM r WHERE n < 3) SELECT * FROM r",
        "SELECT * FROM (WITH t AS (SELECT * FROM marts.fct_plays) "
        "SELECT * FROM t) s",
    ],
)
def test_marts_tables_and_ctes_accepted(sql):
    ask.check_marts_only(sql)


def test_non_marts_table_never_reaches_db(fake_model, mock_cursor):
    fake_model.reply = "SELECT refresh_token FROM stored_token"
    with pytest.raises(UnsafeSQLError):
        ask.ask(
            "token?", client=fake_model, connect=pytest.fail
        )  # must not be called
    mock_cursor.execute.assert_not_called()


def test_refusal_raises(fake_model, ask_conn):
    fake_model.stop_reason = "refusal"
    with pytest.raises(ask.AskError):
        ask.ask("q", client=fake_model, connect=lambda: ask_conn)


# --- read-only execution ----------------------------------------------


def test_runs_in_read_only_transaction_with_timeout(
    fake_model, ask_conn, mock_cursor
):
    fake_model.reply = "SELECT 1"
    ask.ask("q", client=fake_model, connect=lambda: ask_conn)
    stmts = executed(mock_cursor)
    assert stmts[0] == "SET TRANSACTION READ ONLY"
    assert stmts[1].startswith("SET LOCAL statement_timeout")
    assert stmts[-1] == "SELECT 1"
    ask_conn.rollback.assert_called_once()
    ask_conn.commit.assert_not_called()
    ask_conn.close.assert_called_once()


def test_returns_columns_rows_and_count(fake_model, ask_conn):
    fake_model.reply = (
        "SELECT primary_artist_name AS artist, count(*) AS plays "
        "FROM marts.fct_plays GROUP BY 1 ORDER BY 2 DESC"
    )
    result = ask.ask(
        "top artists", client=fake_model, connect=lambda: ask_conn
    )
    assert result.question == "top artists"
    assert result.sql == fake_model.reply
    assert result.columns == ["artist", "plays"]
    assert result.rows == [("Bon Iver", 12), ("Low", 7)]
    assert result.row_count == 2
    assert result.truncated is False


def test_row_cap_truncates(fake_model, ask_conn, mock_cursor):
    mock_cursor.fetchmany.return_value = [(i,) for i in range(4)]
    mock_cursor.description = [("n",)]
    result = ask.ask(
        "q", client=fake_model, connect=lambda: ask_conn, row_limit=3
    )
    mock_cursor.fetchmany.assert_called_once_with(4)
    assert result.row_count == 3
    assert result.truncated is True


def test_db_error_propagates_and_closes(fake_model, ask_conn, mock_cursor):
    mock_cursor.execute.side_effect = [None, None, RuntimeError("boom")]
    with pytest.raises(RuntimeError, match="boom"):
        ask.ask("q", client=fake_model, connect=lambda: ask_conn)
    ask_conn.rollback.assert_called_once()
    ask_conn.close.assert_called_once()


# --- logging ----------------------------------------------------------


def test_logs_prompt_sql_and_row_count(fake_model, ask_conn, caplog):
    caplog.set_level(logging.INFO, logger="ask")
    ask.ask(
        "Who did I play most?", client=fake_model, connect=lambda: ask_conn
    )
    text = caplog.text
    assert "Who did I play most?" in text
    assert "marts.fct_plays" in text  # schema-aware prompt is logged
    assert "SELECT 1" in text
    assert "row_count=2" in text


def test_logs_no_secrets(fake_model, ask_conn, caplog, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-log")
    monkeypatch.setenv("ASK_DATABASE_URL", "postgres://u:hunter2@h/db")
    caplog.set_level(logging.DEBUG)
    ask.ask("q", client=fake_model, connect=lambda: ask_conn)
    assert "sk-ant-should-not-log" not in caplog.text
    assert "hunter2" not in caplog.text


# --- defaults ---------------------------------------------------------


def test_default_connect_requires_ask_database_url(monkeypatch):
    monkeypatch.delenv("ASK_DATABASE_URL", raising=False)
    with pytest.raises(KeyError):
        ask.connect_readonly()


def test_default_connect_does_not_fall_back_to_app_db(monkeypatch, mocker):
    monkeypatch.delenv("ASK_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://app")
    connect = mocker.patch("ask.psycopg2.connect")
    with pytest.raises(KeyError):
        ask.connect_readonly()
    connect.assert_not_called()
