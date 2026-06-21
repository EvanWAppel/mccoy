import pytest
from tests.conftest import MOCK_ARTISTS
from spotify import (
    get_top_artists,
    get_user_profile,
    aggregate_genres,
    search_playlists,
    get_playlist_tracks,
    get_album_tracks,
    get_user_playlists,
    create_playlist,
    add_track_to_playlist,
    get_playlist_track_uris,
    get_user_product,
    start_playback,
)


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
            assert "artist_id" in artist
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

    def test_artist_id_extracted(self, mock_sp):
        result = get_top_artists(mock_sp, "short_term")
        assert result[0]["artist_id"] == "spotify_artist_1"

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


class TestSearchPlaylists:
    def test_calls_api_with_correct_args(self, mock_sp):
        mock_sp.search.return_value = {
            "playlists": {"items": [], "next": None}
        }
        search_playlists(mock_sp, "indie")
        mock_sp.search.assert_called_once_with(
            q="indie", type="playlist", limit=10, offset=0
        )

    def test_limit_capped_at_spotify_playlist_max(self, mock_sp):
        # Spotify rejects limit > 10 on type=playlist searches with
        # 400 Invalid limit (observed live, 2026-06)
        mock_sp.search.return_value = {
            "playlists": {"items": [], "next": None}
        }
        search_playlists(mock_sp, "indie", limit=50)
        mock_sp.search.assert_called_once_with(
            q="indie", type="playlist", limit=10, offset=0
        )

    def test_returns_dicts_with_id_name_image_url(self, mock_sp):
        mock_sp.search.return_value = {
            "playlists": {
                "items": [
                    {
                        "id": "pl1",
                        "name": "Indie Picks",
                        "images": [{"url": "https://example.com/p1.jpg"}],
                    }
                ],
                "next": None,
            }
        }
        result = search_playlists(mock_sp, "indie")
        assert result == [
            {
                "id": "pl1",
                "name": "Indie Picks",
                "image_url": "https://example.com/p1.jpg",
            }
        ]

    def test_returns_empty_list_on_zero_results(self, mock_sp):
        mock_sp.search.return_value = {
            "playlists": {"items": [], "next": None}
        }
        result = search_playlists(mock_sp, "asdfasdf")
        assert result == []

    def test_offset_passed_through(self, mock_sp):
        mock_sp.search.return_value = {
            "playlists": {"items": [], "next": None}
        }
        search_playlists(mock_sp, "indie", offset=40)
        mock_sp.search.assert_called_once_with(
            q="indie", type="playlist", limit=10, offset=40
        )

    def test_pagination_offset_clamps_limit(self, mock_sp):
        # DD-07: paging steps by the Spotify-capped limit (10) even
        # when a larger limit is requested at a non-zero offset
        mock_sp.search.return_value = {
            "playlists": {"items": [], "next": None}
        }
        search_playlists(mock_sp, "indie", limit=50, offset=40)
        mock_sp.search.assert_called_once_with(
            q="indie", type="playlist", limit=10, offset=40
        )

    def test_handles_playlist_with_no_image(self, mock_sp):
        mock_sp.search.return_value = {
            "playlists": {
                "items": [
                    {"id": "pl1", "name": "No Image", "images": []}
                ],
                "next": None,
            }
        }
        result = search_playlists(mock_sp, "x")
        assert result[0]["image_url"] is None

    def test_skips_null_items(self, mock_sp):
        # Spotify occasionally returns null entries in the playlists list
        mock_sp.search.return_value = {
            "playlists": {
                "items": [
                    None,
                    {
                        "id": "pl1",
                        "name": "Real",
                        "images": [{"url": "u"}],
                    },
                ],
                "next": None,
            }
        }
        result = search_playlists(mock_sp, "x")
        assert len(result) == 1
        assert result[0]["id"] == "pl1"


def _playlist_item(
    name="Song",
    uri="spotify:track:abc",
    album_id="alb1",
    album_name="Album",
    album_img="https://example.com/cover.jpg",
    preview="https://example.com/preview.mp3",
):
    return {
        "track": {
            "name": name,
            "uri": uri,
            "album": {
                "id": album_id,
                "name": album_name,
                "images": [{"url": album_img}] if album_img else [],
            },
            "preview_url": preview,
        }
    }


class TestGetPlaylistTracks:
    def test_returns_track_dicts(self, mock_sp):
        mock_sp.playlist_items.return_value = {
            "items": [_playlist_item()],
            "next": None,
        }
        result = get_playlist_tracks(mock_sp, "pl1")
        assert len(result) == 1
        assert result[0] == {
            "name": "Song",
            "uri": "spotify:track:abc",
            "album_id": "alb1",
            "album_name": "Album",
            "album_image_url": "https://example.com/cover.jpg",
            "preview_url": "https://example.com/preview.mp3",
        }

    def test_filters_out_null_tracks(self, mock_sp):
        mock_sp.playlist_items.return_value = {
            "items": [{"track": None}, _playlist_item()],
            "next": None,
        }
        result = get_playlist_tracks(mock_sp, "pl1")
        assert len(result) == 1

    def test_filters_out_null_uris(self, mock_sp):
        local_file = {
            "track": {
                "name": "Local",
                "uri": None,
                "album": {"id": "x", "name": "A", "images": []},
                "preview_url": None,
            }
        }
        mock_sp.playlist_items.return_value = {
            "items": [local_file, _playlist_item()],
            "next": None,
        }
        result = get_playlist_tracks(mock_sp, "pl1")
        assert len(result) == 1
        assert result[0]["uri"] == "spotify:track:abc"

    def test_handles_track_without_album_image(self, mock_sp):
        mock_sp.playlist_items.return_value = {
            "items": [_playlist_item(album_img=None)],
            "next": None,
        }
        result = get_playlist_tracks(mock_sp, "pl1")
        assert result[0]["album_image_url"] is None

    def test_paginates_when_next(self, mock_sp):
        page1 = {
            "items": [_playlist_item("A", "spotify:track:1")],
            "next": "https://api.spotify.com/v1/...",
        }
        page2 = {
            "items": [_playlist_item("B", "spotify:track:2")],
            "next": None,
        }
        mock_sp.playlist_items.return_value = page1
        mock_sp.next.return_value = page2
        result = get_playlist_tracks(mock_sp, "pl1")
        assert len(result) == 2
        names = [t["name"] for t in result]
        assert names == ["A", "B"]


class TestGetAlbumTracks:
    def test_returns_track_dicts_in_order(self, mock_sp):
        mock_sp.album.return_value = {
            "images": [{"url": "https://example.com/album.jpg"}],
            "tracks": {
                "items": [
                    {
                        "name": "T1",
                        "uri": "spotify:track:1",
                        "track_number": 1,
                        "duration_ms": 1000,
                        "preview_url": "p1",
                    },
                    {
                        "name": "T2",
                        "uri": "spotify:track:2",
                        "track_number": 2,
                        "duration_ms": 2000,
                        "preview_url": None,
                    },
                ]
            },
        }
        result = get_album_tracks(mock_sp, "alb1")
        assert result == [
            {
                "name": "T1",
                "uri": "spotify:track:1",
                "track_number": 1,
                "duration_ms": 1000,
                "image_url": "https://example.com/album.jpg",
                "preview_url": "p1",
            },
            {
                "name": "T2",
                "uri": "spotify:track:2",
                "track_number": 2,
                "duration_ms": 2000,
                "image_url": "https://example.com/album.jpg",
                "preview_url": None,
            },
        ]

    def test_handles_album_with_no_image(self, mock_sp):
        mock_sp.album.return_value = {
            "images": [],
            "tracks": {
                "items": [
                    {
                        "name": "T",
                        "uri": "u",
                        "track_number": 1,
                        "duration_ms": 1,
                        "preview_url": None,
                    }
                ]
            },
        }
        result = get_album_tracks(mock_sp, "x")
        assert result[0]["image_url"] is None


class TestGetUserPlaylists:
    def test_returns_id_and_name(self, mock_sp):
        mock_sp.current_user_playlists.return_value = {
            "items": [
                {"id": "p1", "name": "My Playlist"},
                {"id": "p2", "name": "Other"},
            ],
            "next": None,
        }
        result = get_user_playlists(mock_sp)
        assert result == [
            {"id": "p1", "name": "My Playlist"},
            {"id": "p2", "name": "Other"},
        ]

    def test_paginates(self, mock_sp):
        page1 = {"items": [{"id": "p1", "name": "A"}], "next": "url"}
        page2 = {"items": [{"id": "p2", "name": "B"}], "next": None}
        mock_sp.current_user_playlists.return_value = page1
        mock_sp.next.return_value = page2
        result = get_user_playlists(mock_sp)
        assert len(result) == 2


class TestCreatePlaylist:
    def test_calls_api_with_public_false_and_returns_id(self, mock_sp):
        mock_sp.user_playlist_create.return_value = {"id": "new_pl"}
        result = create_playlist(mock_sp, "user1", "My New Playlist")
        mock_sp.user_playlist_create.assert_called_once_with(
            user="user1", name="My New Playlist", public=False
        )
        assert result == "new_pl"


class TestAddTrackToPlaylist:
    def test_calls_api(self, mock_sp):
        add_track_to_playlist(mock_sp, "pl1", "spotify:track:abc")
        mock_sp.playlist_add_items.assert_called_once_with(
            "pl1", ["spotify:track:abc"]
        )


class TestGetPlaylistTrackUris:
    def test_returns_set(self, mock_sp):
        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"uri": "spotify:track:a"}},
                {"track": {"uri": "spotify:track:b"}},
            ],
            "next": None,
        }
        result = get_playlist_track_uris(mock_sp, "pl1")
        assert result == {"spotify:track:a", "spotify:track:b"}

    def test_skips_null_tracks_and_null_uris(self, mock_sp):
        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": None},
                {"track": {"uri": "spotify:track:a"}},
                {"track": {"uri": None}},
            ],
            "next": None,
        }
        result = get_playlist_track_uris(mock_sp, "pl1")
        assert result == {"spotify:track:a"}

    def test_paginates(self, mock_sp):
        page1 = {
            "items": [{"track": {"uri": "spotify:track:a"}}],
            "next": "url",
        }
        page2 = {
            "items": [{"track": {"uri": "spotify:track:b"}}],
            "next": None,
        }
        mock_sp.playlist_items.return_value = page1
        mock_sp.next.return_value = page2
        result = get_playlist_track_uris(mock_sp, "pl1")
        assert result == {"spotify:track:a", "spotify:track:b"}


class TestGetUserProduct:
    @pytest.mark.parametrize("product", ["premium", "free", "open"])
    def test_returns_product_string(self, mock_sp, product):
        mock_sp.current_user.return_value = {
            "product": product,
            "display_name": "X",
            "images": [],
        }
        result = get_user_product(mock_sp)
        assert result == product


# Y-06: premium full-track playback via the Web Playback SDK device
class TestStartPlayback:
    def test_calls_start_playback_with_device_and_uri(self, mock_sp):
        start_playback(mock_sp, "device123", "spotify:track:abc")
        mock_sp.start_playback.assert_called_once_with(
            device_id="device123", uris=["spotify:track:abc"]
        )
