"""XX-01: the read-only `mccoy_ask` role (manual migration 007).

007 lives in `migrations/manual/` so the hourly `db.init_db()` never
applies it; Evan runs it by hand on Railway, then gives the role a
password and sets ASK_DATABASE_URL (BLOCKED.md). The Postgres tests
need TEST_DATABASE_URL, like the pipeline tests.
"""

import re
import secrets

import psycopg2
import pytest
from psycopg2 import errorcodes
from psycopg2.extensions import make_dsn

import ask
import db
from db import MIGRATIONS_DIR
from tests.conftest import throwaway_db

ROLE_SQL = MIGRATIONS_DIR / "manual" / "007_ask_readonly_role.sql"
FIXTURE_MARTS = MIGRATIONS_DIR.parent / "tests" / "evals" / "fixture_marts.sql"


# --- init_db never auto-applies manual migrations ---------------------


def _executed_sql(mock_cursor):
    return [c.args[0] for c in mock_cursor.execute.call_args_list]


def test_init_db_skips_manual_dir(
    tmp_path, monkeypatch, mocker, mock_conn, mock_cursor
):
    (tmp_path / "001_a.sql").write_text("-- top level")
    (tmp_path / "manual").mkdir()
    (tmp_path / "manual" / "007_b.sql").write_text("-- manual only")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path)
    mocker.patch("db.get_connection", return_value=mock_conn)
    db.init_db()
    assert _executed_sql(mock_cursor) == ["-- top level"]


def test_init_db_never_runs_the_role_migration(mocker, mock_conn, mock_cursor):
    mocker.patch("db.get_connection", return_value=mock_conn)
    db.init_db()
    executed = _executed_sql(mock_cursor)
    assert executed  # the real top-level migrations ran
    assert ROLE_SQL.read_text() not in executed
    assert not any("mccoy_ask" in sql for sql in executed)


# --- the migration file itself ----------------------------------------


def test_role_migration_is_manual_not_top_level():
    assert ROLE_SQL.exists()
    assert not list(MIGRATIONS_DIR.glob("007*.sql"))


def test_role_migration_holds_no_secret():
    sql = ROLE_SQL.read_text()
    assert not re.search(r"PASSWORD\s+'", sql, re.IGNORECASE)
    assert re.search(r"\bNOLOGIN\b", sql)


def test_role_migration_timeout_matches_ask():
    sql = ROLE_SQL.read_text()
    assert ask.STATEMENT_TIMEOUT_MS == 5000
    assert "statement_timeout = '5s'" in sql


# --- ASK_DATABASE_URL wiring ------------------------------------------


def test_connect_readonly_uses_ask_database_url(monkeypatch, mocker):
    monkeypatch.setenv("ASK_DATABASE_URL", "postgres://mccoy_ask@h/db")
    monkeypatch.setenv("DATABASE_URL", "postgres://app@h/db")
    connect = mocker.patch("ask.psycopg2.connect")
    assert ask.connect_readonly() is connect.return_value
    connect.assert_called_once_with("postgres://mccoy_ask@h/db")


# --- against real Postgres --------------------------------------------


@pytest.fixture(scope="module")
def role_db():
    """Migrated DB + fixture marts + 007 (run twice: idempotent).

    Gives mccoy_ask a throwaway password for the test, and takes LOGIN
    away again afterwards (roles are cluster-wide).
    """
    scripts = [
        *sorted(MIGRATIONS_DIR.glob("*.sql")),
        FIXTURE_MARTS,
        ROLE_SQL,
        ROLE_SQL,
    ]
    with throwaway_db(scripts) as dsn:
        password = secrets.token_hex(16)
        admin = psycopg2.connect(dsn)
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute("ALTER ROLE mccoy_ask LOGIN PASSWORD %s", (password,))
            # A mart rebuilt by dbt after 007 ran (new table object).
            cur.execute("CREATE TABLE marts.mart_new AS SELECT 1 AS x")
        try:
            yield dsn, make_dsn(dsn, user="mccoy_ask", password=password)
        finally:
            with admin.cursor() as cur:
                cur.execute("ALTER ROLE mccoy_ask NOLOGIN PASSWORD NULL")
            admin.close()


def _as_ask(role_db, sql):
    conn = psycopg2.connect(role_db[1])
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.rollback()
        conn.close()


def test_role_reads_marts(role_db):
    rows = _as_ask(role_db, "SELECT count(*) FROM marts.fct_plays")
    assert rows[0][0] == 10


def test_role_reads_marts_rebuilt_later(role_db):
    assert _as_ask(role_db, "SELECT x FROM marts.mart_new") == [(1,)]


def test_role_cannot_read_app_tables(role_db):
    with pytest.raises(psycopg2.Error) as err:
        _as_ask(role_db, "SELECT * FROM stored_token")
    assert err.value.pgcode == errorcodes.INSUFFICIENT_PRIVILEGE


def test_role_cannot_write_marts(role_db):
    with pytest.raises(psycopg2.Error) as err:
        _as_ask(role_db, "DELETE FROM marts.fct_plays")
    assert err.value.pgcode == errorcodes.READ_ONLY_SQL_TRANSACTION


def test_role_has_5s_statement_timeout(role_db):
    assert _as_ask(role_db, "SHOW statement_timeout") == [("5s",)]


def test_role_is_not_privileged(role_db):
    rows = _as_ask(
        role_db,
        "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls"
        " FROM pg_roles WHERE rolname = current_user",
    )
    assert rows == [(False, False, False, False)]


def test_ask_runs_through_the_role(role_db):
    conn = psycopg2.connect(role_db[1])
    cols, rows, truncated = ask.run_readonly(
        conn, "SELECT play_id FROM marts.fct_plays ORDER BY 1", row_limit=3
    )
    assert cols == ["play_id"]
    assert len(rows) == 3
    assert truncated
