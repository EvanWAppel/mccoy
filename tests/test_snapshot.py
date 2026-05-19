import pytest
import spotipy
from unittest.mock import patch, MagicMock, call
from snapshot import run_snapshot


TIME_RANGES = ["short_term", "medium_term", "long_term"]

MOCK_ARTISTS = [
    {"name": f"Artist {i}", "artist_id": f"id{i}", "rank": i,
     "image_url": None, "genres": ["indie"]}
    for i in range(1, 51)
]


class TestRunSnapshot:
    def test_returns_early_if_no_refresh_token(self):
        with patch("snapshot.db.get_refresh_token", return_value=None):
            run_snapshot()  # should not raise

    def test_fetches_all_three_time_ranges(self, mocker):
        mocker.patch("snapshot.db.get_refresh_token", return_value="tok")
        mocker.patch("snapshot.db.save_snapshot", return_value=1)
        mock_get_artists = mocker.patch("snapshot.get_top_artists", return_value=MOCK_ARTISTS)
        mocker.patch("snapshot.spotipy.Spotify")
        mocker.patch("snapshot._get_sp_from_token", return_value=MagicMock())

        run_snapshot()

        called_ranges = [c.args[1] for c in mock_get_artists.call_args_list]
        assert set(called_ranges) == {"short_term", "medium_term", "long_term"}

    def test_saves_snapshot_three_times(self, mocker):
        mocker.patch("snapshot.db.get_refresh_token", return_value="tok")
        mock_save = mocker.patch("snapshot.db.save_snapshot", return_value=1)
        mocker.patch("snapshot.get_top_artists", return_value=MOCK_ARTISTS)
        mocker.patch("snapshot._get_sp_from_token", return_value=MagicMock())

        run_snapshot()

        assert mock_save.call_count == 3

    def test_fetches_top_50_artists(self, mocker):
        mocker.patch("snapshot.db.get_refresh_token", return_value="tok")
        mocker.patch("snapshot.db.save_snapshot", return_value=1)
        mock_get_artists = mocker.patch("snapshot.get_top_artists", return_value=MOCK_ARTISTS)
        mocker.patch("snapshot._get_sp_from_token", return_value=MagicMock())

        run_snapshot()

        for c in mock_get_artists.call_args_list:
            assert c.kwargs.get("limit") == 50 or (len(c.args) > 2 and c.args[2] == 50)
