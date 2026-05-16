import pytest
from tests.conftest import MOCK_ARTISTS
from spotify import get_top_artists, get_user_profile, aggregate_genres


class TestGetTopArtists:
    def test_returns_list_of_ten(self, mock_sp):
        result = get_top_artists(mock_sp, "short_term")
        assert len(result) == 10

    def test_calls_api_with_correct_args(self, mock_sp):
        get_top_artists(mock_sp, "medium_term")
        mock_sp.current_user_top_artists.assert_called_once_with(
            limit=10, time_range="medium_term"
        )

    def test_result_has_required_keys(self, mock_sp):
        result = get_top_artists(mock_sp, "short_term")
        for artist in result:
            assert "name" in artist
            assert "image_url" in artist
            assert "rank" in artist
            assert "genres" in artist

    def test_rank_is_one_indexed(self, mock_sp):
        result = get_top_artists(mock_sp, "short_term")
        assert result[0]["rank"] == 1
        assert result[9]["rank"] == 10

    def test_image_url_extracted_from_first_image(self, mock_sp):
        result = get_top_artists(mock_sp, "short_term")
        assert result[0]["image_url"] == "https://example.com/img1.jpg"

    def test_artist_with_no_images_returns_none_url(self, mock_sp):
        mock_sp.current_user_top_artists.return_value = {
            "items": [{"name": "No Image Artist", "genres": [], "images": []}]
        }
        result = get_top_artists(mock_sp, "short_term")
        assert result[0]["image_url"] is None


class TestGetUserProfile:
    def test_returns_display_name(self, mock_sp):
        result = get_user_profile(mock_sp)
        assert result["display_name"] == "Evan Appel"

    def test_returns_avatar_url(self, mock_sp):
        result = get_user_profile(mock_sp)
        assert result["avatar_url"] == "https://example.com/avatar.jpg"

    def test_no_avatar_returns_none(self, mock_sp):
        mock_sp.current_user.return_value = {
            "display_name": "Evan",
            "images": [],
        }
        result = get_user_profile(mock_sp)
        assert result["avatar_url"] is None


class TestAggregateGenres:
    def test_returns_list(self):
        result = aggregate_genres(MOCK_ARTISTS)
        assert isinstance(result, list)

    def test_each_item_has_genre_and_count(self):
        result = aggregate_genres(MOCK_ARTISTS)
        for item in result:
            assert "genre" in item
            assert "count" in item

    def test_sorted_by_count_descending(self):
        result = aggregate_genres(MOCK_ARTISTS)
        counts = [item["count"] for item in result]
        assert counts == sorted(counts, reverse=True)

    def test_max_twenty_genres(self):
        # Build artists with many unique genres
        artists = [{"genres": [f"genre_{i}"], "name": f"A{i}", "image_url": None, "rank": i}
                   for i in range(30)]
        result = aggregate_genres(artists)
        assert len(result) <= 20

    def test_correct_count(self):
        # "indie rock" appears in artists 2,4,6,8,10 (5 artists)
        result = aggregate_genres(MOCK_ARTISTS)
        indie = next(r for r in result if r["genre"] == "indie rock")
        assert indie["count"] == 5

    def test_empty_genres_excluded(self):
        artists = [
            {"genres": [], "name": "Silent Artist", "image_url": None, "rank": 1},
            {"genres": ["ambient"], "name": "Ambient Artist", "image_url": None, "rank": 2},
        ]
        result = aggregate_genres(artists)
        genres = [r["genre"] for r in result]
        assert "ambient" in genres
        assert len(result) == 1

    def test_empty_artist_list_returns_empty(self):
        result = aggregate_genres([])
        assert result == []
