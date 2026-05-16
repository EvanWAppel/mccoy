"""H-05: Integration test — mock Spotify response → aggregate_genres → render_genre_chart."""
from dash import dcc
from tests.conftest import MOCK_ARTISTS_RAW, MOCK_ARTISTS
from spotify import get_top_artists, aggregate_genres
from components.genre_chart import render_genre_chart


class TestFullDataFlow:
    def test_artists_to_chart_contains_expected_genres(self, mock_sp):
        artists = get_top_artists(mock_sp, "short_term")
        genres = aggregate_genres(artists)
        chart = render_genre_chart(genres)

        assert isinstance(chart, dcc.Graph)
        genre_labels = [g["genre"] for g in genres]
        assert "indie rock" in genre_labels or "pop" in genre_labels

    def test_genre_chart_y_axis_matches_aggregated_genres(self, mock_sp):
        artists = get_top_artists(mock_sp, "short_term")
        genres = aggregate_genres(artists)
        chart = render_genre_chart(genres)

        chart_y_values = list(chart.figure.data[0].y)
        for g in genres:
            assert g["genre"] in chart_y_values

    def test_api_error_returns_empty_chart(self, mock_sp):
        import spotipy
        mock_sp.current_user_top_artists.side_effect = spotipy.SpotifyException(
            http_status=401, code=-1, msg="Unauthorized"
        )
        artists = get_top_artists(mock_sp, "short_term")
        assert artists == []
        genres = aggregate_genres(artists)
        assert genres == []
        chart = render_genre_chart(genres)
        assert isinstance(chart, dcc.Graph)
