import pytest


MOCK_ARTISTS_RAW = {
    "items": [
        {
            "name": f"Artist {i}",
            "genres": ["indie rock", "alternative"] if i % 2 == 0 else ["pop", "dance pop"],
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
        "image_url": f"https://example.com/img{i}.jpg",
        "rank": i,
        "genres": ["indie rock", "alternative"] if i % 2 == 0 else ["pop", "dance pop"],
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
    return {
        "access_token": "fake_access_token",
        "refresh_token": "fake_refresh_token",
        "token_type": "Bearer",
        "expires_at": 9999999999,
        "scope": "user-top-read",
    }
