import json
from pathlib import Path

import pytest

from netviz import sources

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def _no_sleep(mocker):
    # Keep the rate-limit throttle from slowing the test suite.
    mocker.patch("netviz.sources.time.sleep")


class TestMbReleasesFor:
    def test_normalizes_releases(self, mocker):
        mocker.patch.object(
            sources.musicbrainzngs,
            "search_artists",
            return_value=_load("mb_search_artists.json"),
        )
        mocker.patch.object(
            sources.musicbrainzngs,
            "browse_releases",
            return_value=_load("mb_browse_releases.json"),
        )
        releases = sources.mb_releases_for("McCoy Tyner")
        assert releases[0] == {
            "mbid": "mbid-real-mccoy",
            "title": "The Real McCoy",
            "year": 1967,
            "label": "Blue Note",
        }
        # 'date' of just "1967" must still parse to a year.
        assert releases[1]["year"] == 1967

    def test_unresolved_name_returns_empty_and_logs(self, mocker, caplog):
        mocker.patch.object(
            sources.musicbrainzngs,
            "search_artists",
            return_value={"artist-list": [], "artist-count": 0},
        )
        browse = mocker.patch.object(sources.musicbrainzngs, "browse_releases")
        with caplog.at_level("INFO"):
            result = sources.mb_releases_for("Nonexistent Person")
        assert result == []
        browse.assert_not_called()
        assert any("Nonexistent Person" in r.message for r in caplog.records)


class TestMbPersonnelFor:
    def test_returns_personnel_with_instrument(self, mocker):
        mocker.patch.object(
            sources.musicbrainzngs,
            "get_release_by_id",
            return_value=_load("mb_release_personnel.json"),
        )
        people = sources.mb_personnel_for("mbid-real-mccoy")
        assert {"mbid": "mbid-mccoy-tyner", "name": "McCoy Tyner",
                "instrument": "piano"} in people
        assert {"mbid": "mbid-joe-henderson", "name": "Joe Henderson",
                "instrument": "tenor saxophone"} in people
        assert len(people) == 3


class TestDiscogsCreditsFor:
    def test_returns_name_role_pairs(self, mocker):
        fake_release = mocker.MagicMock()
        fake_release.data = _load("discogs_release.json")
        fake_client = mocker.MagicMock()
        fake_client.release.return_value = fake_release

        credits = sources.discogs_credits_for(1234567, client=fake_client)
        assert {"name": "Joe Henderson", "role": "Tenor Saxophone"} in credits
        assert {"name": "Ron Carter", "role": "Bass"} in credits
        # The main artist is included too.
        assert any(c["name"] == "McCoy Tyner" for c in credits)

    def test_missing_release_returns_empty_and_logs(self, mocker, caplog):
        fake_client = mocker.MagicMock()
        fake_client.release.side_effect = Exception("404 not found")
        with caplog.at_level("INFO"):
            result = sources.discogs_credits_for(999, client=fake_client)
        assert result == []
        assert any("999" in r.message for r in caplog.records)
