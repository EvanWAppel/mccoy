"""Tests for the Ask Your Listening SQL guard (XX-02).

The guard is the first line of defence for model-written SQL: it must
accept exactly one read-only SELECT (CTEs allowed) and reject anything
else. The read-only `marts` role (XX-01) is the second line.
"""

import pytest

from sql_guard import UnsafeSQLError, check_sql

ACCEPTED = [
    "SELECT 1",
    "select artist, count(*) from marts.fct_plays group by artist",
    "SELECT * FROM marts.fct_plays LIMIT 10;",
    "  SELECT 1 ;  ",
    "WITH t AS (SELECT artist FROM marts.fct_plays) SELECT * FROM t",
    "WITH a AS (SELECT 1 AS x), b AS (SELECT x FROM a) SELECT x FROM b",
    "SELECT 1 UNION ALL SELECT 2",
    "SELECT x FROM (SELECT 1 AS x) sub WHERE x IN (SELECT 1)",
    "SELECT date_trunc('week', played_at) w, count(*)\n"
    "FROM marts.fct_plays -- weekly plays\nGROUP BY 1 ORDER BY 1",
    # Keywords inside string literals are data, not statements.
    "SELECT 'DROP TABLE x; DELETE FROM y' AS s",
]

REJECTED = [
    # DML
    "INSERT INTO marts.fct_plays VALUES (1)",
    "UPDATE marts.fct_plays SET artist = 'x'",
    "DELETE FROM marts.fct_plays",
    "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN DELETE",
    "COPY marts.fct_plays TO '/tmp/out.csv'",
    # DDL
    "DROP TABLE marts.fct_plays",
    "CREATE TABLE x (id int)",
    "ALTER TABLE marts.fct_plays ADD COLUMN y int",
    "TRUNCATE marts.fct_plays",
    "GRANT ALL ON marts.fct_plays TO public",
    # Session / transaction control
    "SET statement_timeout = 0",
    "SET ROLE postgres",
    "BEGIN",
    "COMMIT",
    # Multi-statement
    "SELECT 1; SELECT 2",
    "SELECT 1; DROP TABLE marts.fct_plays",
    "SELECT 1; DELETE FROM marts.fct_plays;",
    # SELECT-shaped writes and locks
    "SELECT * INTO new_table FROM marts.fct_plays",
    "SELECT * FROM marts.fct_plays FOR UPDATE",
    # Data-modifying CTEs
    "WITH d AS (DELETE FROM marts.fct_plays RETURNING *) SELECT * FROM d",
    "WITH u AS (UPDATE t SET x = 1 RETURNING *) SELECT 1",
    "WITH i AS (INSERT INTO t VALUES (1) RETURNING *) SELECT 1",
    # Functions that run SQL text, read other tables or the server,
    # or change session settings from inside a SELECT
    "SELECT query_to_xml('select * from stored_token', true, true, '')",
    "SELECT table_to_xml('stored_token', true, true, '')",
    "SELECT database_to_xml(true, true, '')",
    "SELECT set_config('statement_timeout', '0', false)",
    "SELECT current_setting('data_directory')",
    "SELECT pg_sleep(60)",
    "SELECT PG_READ_FILE('/etc/passwd')",
    "SELECT lo_import('/etc/passwd')",
    "SELECT * FROM dblink('host=x', 'select 1') AS t(a int)",
    # Not SQL at all / empty
    "",
    "   ",
    ";",
    "-- just a comment",
    "this is not sql (",
]


@pytest.mark.parametrize("sql", ACCEPTED)
def test_accepts_single_select(sql):
    assert check_sql(sql) == sql.strip().rstrip(";").strip()


@pytest.mark.parametrize("sql", REJECTED)
def test_rejects_non_select(sql):
    with pytest.raises(UnsafeSQLError):
        check_sql(sql)


def test_rejects_non_string():
    with pytest.raises(UnsafeSQLError):
        check_sql(None)  # type: ignore[arg-type]


def test_error_says_why():
    with pytest.raises(UnsafeSQLError, match="single statement"):
        check_sql("SELECT 1; SELECT 2")
    with pytest.raises(UnsafeSQLError, match="SELECT"):
        check_sql("DELETE FROM t")


def test_unsafe_sql_error_is_value_error():
    # Callers can catch it as a plain ValueError.
    assert issubclass(UnsafeSQLError, ValueError)
