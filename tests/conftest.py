import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import psycopg2
import pytest
from psycopg2.extensions import make_dsn

from db import MIGRATIONS_DIR


@pytest.fixture
def owner_env(monkeypatch):
    """Configure the site owner's Spotify id (owner identity gate)."""
    monkeypatch.setenv("OWNER_SPOTIFY_ID", "owner_id")
    return "owner_id"


@pytest.fixture
def listening_artists():
    return [
        {"name": "Radiohead", "rank": 1, "genres": ["rock", "art rock"]},
        {"name": "Bon Iver", "rank": 2, "genres": ["art rock"]},
        {"name": "Miles Davis", "rank": 3, "genres": []},
    ]


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: s
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def mock_cursor(mock_conn):
    return mock_conn.cursor.return_value


MOCK_ARTISTS_RAW = {
    "items": [
        {
            "id": f"spotify_artist_{i}",
            "name": f"Artist {i}",
            "genres": (
                ["indie rock", "alternative"]
                if i % 2 == 0
                else ["pop", "dance pop"]
            ),
            "images": [{"url": f"https://example.com/img{i}.jpg"}],
        }
        for i in range(1, 11)
    ]
}

MOCK_PROFILE_RAW = {
    "display_name": "Evan Appel",
    "images": [{"url": "https://example.com/avatar.jpg"}],
}

MOCK_ARTISTS = [
    {
        "name": f"Artist {i}",
        "artist_id": f"spotify_artist_{i}",
        "image_url": f"https://example.com/img{i}.jpg",
        "rank": i,
        "genres": (
            ["indie rock", "alternative"]
            if i % 2 == 0
            else ["pop", "dance pop"]
        ),
    }
    for i in range(1, 11)
]


@pytest.fixture
def mock_sp(mocker):
    sp = mocker.MagicMock()
    sp.current_user_top_artists.return_value = MOCK_ARTISTS_RAW
    sp.current_user.return_value = MOCK_PROFILE_RAW
    return sp


@pytest.fixture
def mock_token():
    # Scope must cover auth.SCOPE so get_sp_from_session doesn't clear
    # the session as insufficient. Imported lazily so importing this
    # fixture doesn't require Spotify env vars at collection time.
    from auth import SCOPE

    return {
        "access_token": "fake_access_token",
        "refresh_token": "fake_refresh_token",
        "token_type": "Bearer",
        "expires_at": 9999999999,
        "scope": SCOPE,
    }


@pytest.fixture
def stale_scope_token():
    return {
        "access_token": "fake_access_token",
        "refresh_token": "fake_refresh_token",
        "token_type": "Bearer",
        "expires_at": 9999999999,
        "scope": "user-top-read",
    }


def _walk_components(component):
    """Yield every Dash component in a tree (depth-first)."""
    if component is None or isinstance(component, (str, int, float)):
        return
    if isinstance(component, (list, tuple)):
        for child in component:
            yield from _walk_components(child)
        return
    yield component
    yield from _walk_components(getattr(component, "children", None))


@pytest.fixture
def component_ids():
    """Function: set of every component id in a Dash tree."""
    def collect(tree):
        return {
            c.id for c in _walk_components(tree)
            if getattr(c, "id", None)
        }
    return collect


@pytest.fixture
def component_text():
    """Function: all string children in a Dash tree, space-joined."""
    def collect(tree):
        parts = [tree] if isinstance(tree, str) else []
        for c in _walk_components(tree):
            kids = getattr(c, "children", None)
            kids = kids if isinstance(kids, (list, tuple)) else [kids]
            parts.extend(k for k in kids if isinstance(k, (str, int)))
        return " ".join(str(p) for p in parts)
    return collect


# --- Postgres integration fixtures (play-history pipeline) ---------------
# Tests that need real SQL semantics (upserts, dbt models) run against a
# throwaway database created on the server named by TEST_DATABASE_URL.
# Without it they skip with a stated reason; CI provides a Postgres
# service so they always run there.

RECENTLY_PLAYED = Path(__file__).parent / "fixtures" / "recently_played.json"


@pytest.fixture
def recently_played():
    """Hand-built recently-played payload: 5 plays + 1 local file."""
    return json.loads(RECENTLY_PLAYED.read_text())


@contextmanager
def throwaway_db(scripts):
    """Create a database on TEST_DATABASE_URL, run `scripts`, drop it."""
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        if os.environ.get("REQUIRE_PG_TESTS"):
            pytest.fail("REQUIRE_PG_TESTS set but TEST_DATABASE_URL isn't")
        pytest.skip("TEST_DATABASE_URL not set; Postgres tests skipped")
    name = f"mccoy_test_{uuid.uuid4().hex[:8]}"
    admin = psycopg2.connect(base)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    dsn = make_dsn(base, dbname=name)
    conn = psycopg2.connect(dsn)
    with conn, conn.cursor() as cur:
        for path in scripts:
            cur.execute(path.read_text())
    conn.close()
    try:
        yield dsn
    finally:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.close()


@pytest.fixture(scope="session")
def pg_dsn():
    with throwaway_db(sorted(MIGRATIONS_DIR.glob("*.sql"))) as dsn:
        yield dsn


@pytest.fixture
def pg_db(pg_dsn, monkeypatch):
    """A migrated, emptied database; DATABASE_URL points at it."""
    monkeypatch.setenv("DATABASE_URL", pg_dsn)
    conn = psycopg2.connect(pg_dsn)
    with conn, conn.cursor() as cur:
        cur.execute("TRUNCATE raw_plays, pipeline_runs RESTART IDENTITY")
    conn.close()
    return pg_dsn


# --- Ask Your Listening (XX-03) ------------------------------------------
# The model client is always a fake in tests: no network, no API key.


class FakeModelClient:
    """Stands in for `anthropic.Anthropic`; records every request.

    Exposes `messages.create(**kwargs)` returning an object with
    `.content[0].text` and `.stop_reason`, which is all `ask` uses.
    """

    def __init__(self, reply="SELECT 1", stop_reason="end_turn"):
        self.reply = reply
        self.stop_reason = stop_reason
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = MagicMock(type="text", text=self.reply)
        return MagicMock(content=[block], stop_reason=self.stop_reason)


@pytest.fixture
def fake_model():
    return FakeModelClient()


@pytest.fixture
def ask_conn(mock_conn, mock_cursor):
    """A mock DB connection whose query returns two rows."""
    mock_cursor.description = [("artist",), ("plays",)]
    mock_cursor.fetchmany.return_value = [("Bon Iver", 12), ("Low", 7)]
    return mock_conn


# --- Ask Your Listening offline evals (XX-05) ----------------------------


@pytest.fixture(scope="session")
def eval_db_connect():
    """Connection factory for the eval fixture marts database.

    The marts live in their own throwaway database (not `pg_dsn`) so
    they never collide with the dbt-built marts in the pipeline tests.
    """
    from ask.evals import FIXTURE_SQL

    with throwaway_db([FIXTURE_SQL]) as dsn:
        yield lambda: psycopg2.connect(dsn)
