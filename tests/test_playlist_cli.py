import json

import pytest

import playlist_cli
from playlist_cli import Match, Track


def _search_response(name, artist, album, uri="spotify:track:abc"):
    return {
        "tracks": {
            "items": [
                {
                    "uri": uri,
                    "name": name,
                    "artists": [{"name": artist}],
                    "album": {"name": album},
                }
            ]
        }
    }


@pytest.fixture
def tracklist_file(tmp_path):
    data = {
        "name": "Test Mix",
        "description": "A test tracklist",
        "tracks": [
            {"artist": "Lee Morgan", "title": "Ceora", "album": "Cornbread"},
            {"artist": "Hank Mobley", "title": "Soul Station"},
        ],
    }
    path = tmp_path / "mix.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


class TestLoadTracklist:
    def test_parses_name_description_and_tracks(self, tracklist_file):
        name, description, tracks = playlist_cli.load_tracklist(
            tracklist_file
        )
        assert name == "Test Mix"
        assert description == "A test tracklist"
        assert [t.title for t in tracks] == ["Ceora", "Soul Station"]

    def test_album_is_optional(self, tracklist_file):
        _, _, tracks = playlist_cli.load_tracklist(tracklist_file)
        assert tracks[0].album == "Cornbread"
        assert tracks[1].album is None

    def test_description_defaults_to_empty(self, tmp_path):
        path = tmp_path / "min.json"
        path.write_text(
            json.dumps({"name": "N", "tracks": []}), encoding="utf-8"
        )
        _, description, tracks = playlist_cli.load_tracklist(str(path))
        assert description == ""
        assert tracks == []


class TestFirstTrack:
    def test_returns_first_item(self):
        resp = _search_response("Ceora", "Lee Morgan", "Cornbread")
        assert playlist_cli._first_track(resp)["name"] == "Ceora"

    def test_returns_none_when_empty(self):
        assert playlist_cli._first_track({"tracks": {"items": []}}) is None

    def test_returns_none_when_missing_keys(self):
        assert playlist_cli._first_track({}) is None


class TestResolveTrack:
    def test_album_constrained_query_tried_first(self, mocker):
        sp = mocker.MagicMock()
        sp.search.return_value = _search_response(
            "Ceora", "Lee Morgan", "Cornbread"
        )
        track = Track(artist="Lee Morgan", title="Ceora", album="Cornbread")

        match = playlist_cli.resolve_track(sp, track)

        assert match is not None
        assert match.uri == "spotify:track:abc"
        assert match.resolved_artist == "Lee Morgan"
        first_query = sp.search.call_args_list[0].kwargs["q"]
        assert 'album:"Cornbread"' in first_query

    def test_falls_back_to_artist_title_when_album_query_empty(self, mocker):
        sp = mocker.MagicMock()
        empty = {"tracks": {"items": []}}
        hit = _search_response("Soul Station", "Hank Mobley", "Soul Station")
        sp.search.side_effect = [empty, hit]
        track = Track(
            artist="Hank Mobley", title="Soul Station", album="Soul Station"
        )

        match = playlist_cli.resolve_track(sp, track)

        assert match is not None
        assert sp.search.call_count == 2
        assert 'album:' not in sp.search.call_args_list[1].kwargs["q"]

    def test_no_album_query_when_track_has_no_album(self, mocker):
        sp = mocker.MagicMock()
        sp.search.return_value = _search_response(
            "Soul Station", "Hank Mobley", "Soul Station"
        )
        track = Track(artist="Hank Mobley", title="Soul Station")

        playlist_cli.resolve_track(sp, track)

        assert sp.search.call_count == 1

    def test_returns_none_when_nothing_found(self, mocker):
        sp = mocker.MagicMock()
        sp.search.return_value = {"tracks": {"items": []}}
        track = Track(artist="Nobody", title="Nothing")
        assert playlist_cli.resolve_track(sp, track) is None


class TestResolveAll:
    def test_splits_matched_and_missing(self, mocker):
        sp = mocker.MagicMock()
        found = Track(artist="Lee Morgan", title="Ceora")
        gone = Track(artist="Nobody", title="Nothing")

        def fake(_sp, track):
            if track is found:
                return Match(
                    track=track,
                    uri="u",
                    resolved_artist="Lee Morgan",
                    resolved_title="Ceora",
                    resolved_album="Cornbread",
                )
            return None

        mocker.patch.object(playlist_cli, "resolve_track", side_effect=fake)
        matched, missing = playlist_cli.resolve_all(sp, [found, gone])

        assert [m.track for m in matched] == [found]
        assert missing == [gone]


class TestChunks:
    def test_splits_into_sized_chunks(self):
        chunks = list(playlist_cli._chunks(list(range(250)), 100))
        assert [len(c) for c in chunks] == [100, 100, 50]

    def test_empty_yields_nothing(self):
        assert list(playlist_cli._chunks([], 100)) == []


class TestCreatePlaylistWithTracks:
    def _matches(self, n):
        return [
            Match(
                track=Track(artist=f"A{i}", title=f"T{i}"),
                uri=f"spotify:track:{i}",
                resolved_artist=f"A{i}",
                resolved_title=f"T{i}",
                resolved_album="Alb",
            )
            for i in range(n)
        ]

    def test_creates_private_playlist_and_returns_url(self, mocker):
        sp = mocker.MagicMock()
        sp.current_user.return_value = {"id": "evan"}
        sp.user_playlist_create.return_value = {
            "id": "pl123",
            "external_urls": {"spotify": "https://open.spotify.com/pl123"},
        }

        url = playlist_cli.create_playlist_with_tracks(
            sp, "My Mix", "desc", self._matches(3)
        )

        assert url == "https://open.spotify.com/pl123"
        sp.user_playlist_create.assert_called_once_with(
            user="evan", name="My Mix", public=False, description="desc"
        )

    def test_add_items_is_chunked(self, mocker):
        sp = mocker.MagicMock()
        sp.current_user.return_value = {"id": "evan"}
        sp.user_playlist_create.return_value = {
            "id": "pl123",
            "external_urls": {"spotify": "https://x"},
        }

        playlist_cli.create_playlist_with_tracks(
            sp, "Big", "", self._matches(150)
        )

        sizes = [
            len(call.args[1])
            for call in sp.playlist_add_items.call_args_list
        ]
        assert sizes == [100, 50]


class TestConfirm:
    @pytest.mark.parametrize("answer", ["y", "yes", "Y", "YES"])
    def test_accepts_yes(self, mocker, answer):
        mocker.patch("builtins.input", return_value=answer)
        assert playlist_cli.confirm("go?") is True

    @pytest.mark.parametrize("answer", ["n", "no", "", "nope"])
    def test_rejects_others(self, mocker, answer):
        mocker.patch("builtins.input", return_value=answer)
        assert playlist_cli.confirm("go?") is False


class TestPrintReport:
    def test_lists_matched_and_missing(self, capsys):
        matched = [
            Match(
                track=Track(artist="Lee Morgan", title="Ceora"),
                uri="u",
                resolved_artist="Lee Morgan",
                resolved_title="Ceora",
                resolved_album="Cornbread",
            )
        ]
        missing = [Track(artist="Nobody", title="Nothing", album="X")]

        playlist_cli.print_report(matched, missing)
        out = capsys.readouterr().out

        assert "Matched 1 track(s)" in out
        assert "Lee Morgan — Ceora" in out
        assert "Could NOT find 1 track(s)" in out
        assert "Nobody — Nothing" in out


class TestMain:
    def _mock_client(self, mocker):
        mocker.patch.object(playlist_cli, "build_user_client")

    def test_success_creates_playlist(self, mocker, tracklist_file, capsys):
        self._mock_client(mocker)
        match = Match(
            track=Track(artist="Lee Morgan", title="Ceora"),
            uri="u",
            resolved_artist="Lee Morgan",
            resolved_title="Ceora",
            resolved_album="Cornbread",
        )
        mocker.patch.object(
            playlist_cli, "resolve_all", return_value=([match], [])
        )
        create = mocker.patch.object(
            playlist_cli,
            "create_playlist_with_tracks",
            return_value="https://open.spotify.com/pl",
        )

        rc = playlist_cli.main([tracklist_file, "--yes"])

        assert rc == 0
        create.assert_called_once()
        assert "https://open.spotify.com/pl" in capsys.readouterr().out

    def test_name_override(self, mocker, tracklist_file):
        self._mock_client(mocker)
        match = Match(
            track=Track(artist="Lee Morgan", title="Ceora"),
            uri="u",
            resolved_artist="Lee Morgan",
            resolved_title="Ceora",
            resolved_album="Cornbread",
        )
        mocker.patch.object(
            playlist_cli, "resolve_all", return_value=([match], [])
        )
        create = mocker.patch.object(
            playlist_cli, "create_playlist_with_tracks", return_value="url"
        )

        playlist_cli.main([tracklist_file, "--name", "Custom", "--yes"])

        assert create.call_args.args[1] == "Custom"

    def test_nothing_resolved_returns_1(self, mocker, tracklist_file):
        self._mock_client(mocker)
        mocker.patch.object(
            playlist_cli, "resolve_all", return_value=([], [])
        )
        create = mocker.patch.object(
            playlist_cli, "create_playlist_with_tracks"
        )

        rc = playlist_cli.main([tracklist_file, "--yes"])

        assert rc == 1
        create.assert_not_called()

    def test_abort_when_not_confirmed(self, mocker, tracklist_file):
        self._mock_client(mocker)
        match = Match(
            track=Track(artist="Lee Morgan", title="Ceora"),
            uri="u",
            resolved_artist="Lee Morgan",
            resolved_title="Ceora",
            resolved_album="Cornbread",
        )
        mocker.patch.object(
            playlist_cli, "resolve_all", return_value=([match], [])
        )
        mocker.patch.object(playlist_cli, "confirm", return_value=False)
        create = mocker.patch.object(
            playlist_cli, "create_playlist_with_tracks"
        )

        rc = playlist_cli.main([tracklist_file])

        assert rc == 0
        create.assert_not_called()
