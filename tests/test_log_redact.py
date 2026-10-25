"""XX-09: secrets are redacted from logged exceptions.

`redact` scrubs passwords and API keys from text; `format_exception`
renders a traceback (type, frames, message, chained exceptions) with
only the secrets replaced. Nothing else is hidden or rewrapped.
"""

import psycopg2
import pytest

from log_redact import MASK, format_exception, redact


class TestRedact:
    @pytest.mark.parametrize(
        "text, secret",
        [
            ("postgresql://mccoy_ask:hunter2@db.internal:5432/x", "hunter2"),
            ("postgres://u:p%40ss@h/db", "p%40ss"),
            ("postgresql:/user:hunter2@localhost/db", "hunter2"),
            ('after "postgresql:/user:hunter2@localhost/db" in', "hunter2"),
            ("redis://:only-pass@cache:6379", "only-pass"),
            ("host=db password=hunter2 dbname=x", "hunter2"),
            ("host=db password = hunter2 dbname=x", "hunter2"),
            ("host=db password='hunter 2' dbname=x", "hunter 2"),
            ("PASSWORD=hunter2", "hunter2"),
            ("key sk-ant-api03-AbC_d-ef123 rejected", "AbC_d-ef123"),
        ],
    )
    def test_secret_is_removed(self, text, secret):
        out = redact(text)
        assert secret not in out
        assert MASK in out

    def test_url_keeps_user_host_and_db(self):
        out = redact("postgresql://mccoy_ask:hunter2@db.internal:5432/x")
        assert out == f"postgresql://mccoy_ask:{MASK}@db.internal:5432/x"

    def test_keyvalue_keeps_other_keys(self):
        out = redact("host=db password=hunter2 dbname=x")
        assert out == f"host=db password={MASK} dbname=x"

    @pytest.mark.parametrize(
        "text",
        [
            "permission denied for table stored_token",
            "postgresql://db.internal:5432/x",  # no userinfo password
            "user@example.com",
            "at 12:30 the job failed",
        ],
    )
    def test_text_without_secrets_is_unchanged(self, text):
        assert redact(text) == text


def _raise_chained():
    try:
        raise ValueError("inner password=hunter2")
    except ValueError as inner:
        raise RuntimeError(
            "outer postgresql://u:hunter3@h/db"
        ) from inner


class TestFormatException:
    def test_keeps_type_frames_and_message(self):
        with pytest.raises(RuntimeError) as info:
            _raise_chained()
        out = format_exception(info.value)
        assert "Traceback (most recent call last)" in out
        assert "RuntimeError: outer postgresql://u:" in out
        assert "_raise_chained" in out  # the frame survives
        assert "@h/db" in out

    def test_redacts_the_chained_exception_too(self):
        with pytest.raises(RuntimeError) as info:
            _raise_chained()
        out = format_exception(info.value)
        assert "ValueError: inner password=" in out
        assert "direct cause" in out
        assert "hunter2" not in out
        assert "hunter3" not in out

    def test_psycopg2_malformed_dsn(self):
        """Codex's XX-09 reproduction: libpq quotes the whole DSN."""
        with pytest.raises(psycopg2.ProgrammingError) as info:
            psycopg2.connect("postgresql:/user:hunter2@localhost/db")
        assert "hunter2" in str(info.value)  # the leak being fixed
        out = format_exception(info.value)
        assert "ProgrammingError" in out
        assert "invalid dsn" in out
        assert "hunter2" not in out

    def test_does_not_mutate_the_exception(self):
        err = RuntimeError("password=hunter2")
        format_exception(err)
        assert str(err) == "password=hunter2"
