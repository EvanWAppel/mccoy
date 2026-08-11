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


class TestRetry:
    def test_retries_then_succeeds(self, mocker):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise json.JSONDecodeError("bad", "doc", 0)
            return "ok"

        assert sources._retry(flaky) == "ok"
        assert calls["n"] == 3

    def test_non_ratelimit_errors_propagate(self, mocker):
        def boom():
            raise IndexError("no results")

        with pytest.raises(IndexError):
            sources._retry(boom)


class TestDiscogsPersonnelFor:
    def _client(self, mocker):
        fake_release = mocker.MagicMock()
        fake_release.data = _load("discogs_release.json")
        fake_client = mocker.MagicMock()
        fake_client.release.return_value = fake_release
        return fake_client

    def test_returns_performing_musicians(self, mocker):
        result = sources.discogs_personnel_for(
            1234567, client=self._client(mocker)
        )
        names = {p["name"] for p in result["personnel"]}
        assert "Joe Henderson" in names
        assert "Ron Carter" in names
        assert "McCoy Tyner" in names  # main artist included

    def test_captures_styles_from_full_release(self, mocker):
        result = sources.discogs_personnel_for(
            1234567, client=self._client(mocker)
        )
        assert result["styles"] == ["Post Bop", "Modal"]

    def test_carries_discogs_id_and_instrument(self, mocker):
        result = sources.discogs_personnel_for(
            1234567, client=self._client(mocker)
        )
        joe = next(
            p for p in result["personnel"] if p["name"] == "Joe Henderson"
        )
        assert joe["discogs_id"] == "200"
        assert joe["instrument"] == "Tenor Saxophone"

    def test_filters_out_non_performers(self, mocker):
        result = sources.discogs_personnel_for(
            1234567, client=self._client(mocker)
        )
        names = {p["name"] for p in result["personnel"]}
        # Engineer + designer must be dropped.
        assert "Rudy Van Gelder" not in names
        assert "Reid Miles" not in names

    def test_missing_release_returns_empty_and_logs(self, mocker, caplog):
        fake_client = mocker.MagicMock()
        fake_client.release.side_effect = Exception("404 not found")
        with caplog.at_level("INFO"):
            result = sources.discogs_personnel_for(999, client=fake_client)
        assert result == {"styles": None, "personnel": []}
        assert any("999" in r.message for r in caplog.records)


class TestDiscogsReleasesFor:
    def _client(self, mocker, release_items):
        artist = mocker.MagicMock()
        artist.releases = release_items
        fake_client = mocker.MagicMock()
        fake_client.search.return_value = [artist]
        return fake_client

    def _item(self, mocker, data):
        it = mocker.MagicMock()
        it.data = data
        return it

    def test_normalizes_releases_and_skips_masters(self, mocker):
        items = [
            self._item(mocker, {"id": 111, "title": "The Real McCoy",
                                "year": 1967, "type": "release",
                                "label": "Blue Note"}),
            self._item(mocker, {"id": 222, "title": "A Master Entry",
                                "year": 1968, "type": "master"}),
            self._item(mocker, {"id": 333, "title": "Tender Moments",
                                "year": 1968, "type": "release"}),
        ]
        client = self._client(mocker, items)
        releases = sources.discogs_releases_for("McCoy Tyner", client=client)
        titles = [r["title"] for r in releases]
        assert titles == ["The Real McCoy", "Tender Moments"]
        assert releases[0]["discogs_id"] == "111"

    def test_paging_error_returns_partial(self, mocker):
        # A transient Discogs error mid-paging must yield what we have,
        # not crash the crawl.
        good = self._item(mocker, {"id": 111, "title": "Good",
                                   "year": 1967, "type": "release"})

        class Boom(list):
            def __iter__(self):
                yield good
                raise ValueError("rate-limit HTML, not JSON")

        artist = mocker.MagicMock()
        artist.releases = Boom()
        client = mocker.MagicMock()
        client.search.return_value = [artist]

        releases = sources.discogs_releases_for("McCoy Tyner", client=client)
        assert [r["title"] for r in releases] == ["Good"]

    def test_respects_limit(self, mocker):
        items = [
            self._item(mocker, {"id": i, "title": f"R{i}", "year": 1960,
                                "type": "release"})
            for i in range(10)
        ]
        client = self._client(mocker, items)
        releases = sources.discogs_releases_for(
            "Somebody", client=client, limit=3
        )
        assert len(releases) == 3

    def test_unresolved_artist_returns_empty_and_logs(self, mocker, caplog):
        fake_client = mocker.MagicMock()
        fake_client.search.return_value = []
        with caplog.at_level("INFO"):
            result = sources.discogs_releases_for("Ghost", client=fake_client)
        assert result == []
        assert any("Ghost" in r.message for r in caplog.records)
