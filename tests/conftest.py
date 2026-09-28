from unittest.mock import MagicMock

import pytest


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
