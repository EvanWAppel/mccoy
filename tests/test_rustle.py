import pytest
from dash import html, dcc

# Group T is the TDD red phase for `components/rustle.py`. The module is
# implemented in Group U (vertical slice). Until then, skip this file
# cleanly instead of erroring out the whole test suite.
try:
    from components.rustle import (
        mode_switcher,
        target_picker,
        search_bar,
        recents_chips,
        playlist_card,
        track_card,
        end_of_queue_card,
        added_stamp_overlay,
        add_counter_chip,
        card_stack,
    )
except ImportError:
    pytest.skip(
        "components.rustle not yet implemented (Group U)",
        allow_module_level=True,
    )


SAMPLE_PLAYLIST = {
    "id": "pl1",
    "name": "Indie Picks",
    "image_url": "https://example.com/playlist.jpg",
}

SAMPLE_TRACK = {
    "name": "Karma Police",
    "uri": "spotify:track:abc",
    "album_id": "alb1",
    "album_name": "OK Computer",
    "album_image_url": "https://example.com/album.jpg",
    "preview_url": "https://example.com/preview.mp3",
}


# --- Tree-walking helpers ---

def _walk(component):
    yield component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for c in children:
                yield from _walk(c)
        elif children is not None:
            yield from _walk(children)


def _contains_text(component, text: str) -> bool:
    for c in _walk(component):
        if isinstance(c, str) and text in c:
            return True
    return False


def _find_id(component, target_id):
    for c in _walk(component):
        if getattr(c, "id", None) == target_id:
            return c
    return None


def _has_image_src(component, url: str) -> bool:
    for c in _walk(component):
        if isinstance(c, html.Img) and getattr(c, "src", None) == url:
            return True
    return False


# --- Tests ---

class TestModeSwitcher:
    def test_returns_tabs(self):
        result = mode_switcher()
        assert isinstance(result, dcc.Tabs)

    def test_has_stats_and_rustle_values(self):
        result = mode_switcher()
        values = [tab.value for tab in result.children]
        assert "stats" in values
        assert "rustle" in values


class TestTargetPicker:
    def test_returns_div(self):
        result = target_picker([SAMPLE_PLAYLIST])
        assert isinstance(result, html.Div)

    def test_renders_playlist_name(self):
        result = target_picker(
            [{"id": "pl1", "name": "My Mix", "image_url": None}]
        )
        assert _contains_text(result, "My Mix")

    def test_includes_create_new_option(self):
        result = target_picker([SAMPLE_PLAYLIST])
        assert _contains_text(result, "Create new")

    def test_empty_playlists_still_has_create_new(self):
        result = target_picker([])
        assert _contains_text(result, "Create new")


class TestSearchBar:
    def test_has_rustle_search_id(self):
        result = search_bar()
        assert _find_id(result, "rustle-search") is not None

    def test_search_input_is_dcc_input(self):
        result = search_bar()
        node = _find_id(result, "rustle-search")
        assert isinstance(node, dcc.Input)


class TestRecentsChips:
    def test_renders_one_chip_per_query(self):
        result = recents_chips(["alpha", "beta", "gamma"])
        for q in ["alpha", "beta", "gamma"]:
            assert _contains_text(result, q)

    def test_empty_has_no_chip_text(self):
        result = recents_chips([])
        # No "Clear" button when there are no chips
        assert not _contains_text(result, "Clear")

    def test_renders_up_to_five(self):
        result = recents_chips(["q1", "q2", "q3", "q4", "q5"])
        for q in ["q1", "q2", "q3", "q4", "q5"]:
            assert _contains_text(result, q)


class TestPlaylistCard:
    def test_returns_div(self):
        result = playlist_card(SAMPLE_PLAYLIST)
        assert isinstance(result, html.Div)

    def test_contains_name(self):
        result = playlist_card(
            {"id": "p1", "name": "My Mix", "image_url": None}
        )
        assert _contains_text(result, "My Mix")

    def test_contains_cover_image(self):
        url = "https://example.com/cover.jpg"
        result = playlist_card(
            {"id": "p1", "name": "X", "image_url": url}
        )
        assert _has_image_src(result, url)


class TestTrackCard:
    def test_returns_div(self):
        result = track_card(SAMPLE_TRACK)
        assert isinstance(result, html.Div)

    def test_contains_track_name(self):
        result = track_card({**SAMPLE_TRACK, "name": "Karma Police"})
        assert _contains_text(result, "Karma Police")

    def test_contains_album_image(self):
        url = "https://example.com/album.jpg"
        result = track_card({**SAMPLE_TRACK, "album_image_url": url})
        assert _has_image_src(result, url)

    def test_already_added_shows_badge(self):
        result = track_card(SAMPLE_TRACK, already_added=True)
        assert _contains_text(result, "Already added")

    def test_not_already_added_has_no_badge(self):
        result = track_card(SAMPLE_TRACK, already_added=False)
        assert not _contains_text(result, "Already added")

    def test_no_preview_url_shows_indicator(self):
        # Group X tests this from the preview-availability angle too
        result = track_card({**SAMPLE_TRACK, "preview_url": None})
        assert _contains_text(result, "No preview")


class TestEndOfQueueCard:
    def test_returns_div(self):
        result = end_of_queue_card("All done.")
        assert isinstance(result, html.Div)

    def test_contains_message(self):
        result = end_of_queue_card("Custom message here")
        assert _contains_text(result, "Custom message here")


class TestAddedStampOverlay:
    def test_returns_div(self):
        result = added_stamp_overlay()
        assert isinstance(result, html.Div)

    def test_has_added_stamp_class(self):
        result = added_stamp_overlay()
        assert "added-stamp" in (result.className or "")


class TestAddCounterChip:
    def test_returns_div(self):
        result = add_counter_chip(3)
        assert isinstance(result, html.Div)

    def test_renders_count(self):
        result = add_counter_chip(3)
        assert _contains_text(result, "+3 added")


class TestCardStack:
    def _cards(self, n):
        return [playlist_card(SAMPLE_PLAYLIST) for _ in range(n)]

    def test_returns_div_with_stack_class(self):
        result = card_stack(self._cards(4))
        assert isinstance(result, html.Div)
        assert "rustle-stack" in (result.className or "")

    def test_renders_at_most_four_cards(self):
        result = card_stack(self._cards(6))
        assert len(result.children) == 4

    def test_single_card_renders_one_slot(self):
        result = card_stack(self._cards(1))
        assert len(result.children) == 1

    def test_slots_have_depth_position_classes(self):
        result = card_stack(self._cards(4))
        classes = [c.className for c in result.children]
        for i in range(4):
            assert f"rustle-stack__card--{i}" in classes[i]
