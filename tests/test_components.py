import pytest
from dash import html, dcc
from components.artist_grid import render_artist_card, render_grid
from components.genre_chart import render_genre_chart


SAMPLE_ARTIST = {
    "name": "Radiohead",
    "image_url": "https://example.com/radiohead.jpg",
    "rank": 1,
    "genres": ["alternative rock", "art rock"],
}

SAMPLE_GENRES = [
    {"genre": "indie rock", "count": 8},
    {"genre": "alternative", "count": 6},
    {"genre": "pop", "count": 4},
]


class TestRenderArtistCard:
    def test_returns_dash_component(self):
        result = render_artist_card(SAMPLE_ARTIST, 1)
        assert result is not None

    def test_returns_html_div(self):
        result = render_artist_card(SAMPLE_ARTIST, 1)
        assert isinstance(result, html.Div)

    def test_contains_artist_name(self):
        result = render_artist_card(SAMPLE_ARTIST, 1)
        assert _contains_text(result, "Radiohead")

    def test_contains_rank(self):
        result = render_artist_card(SAMPLE_ARTIST, 3)
        assert _contains_text(result, "#3") or _contains_text(result, "3")


class TestRenderGrid:
    def test_returns_html_div(self):
        artists = [SAMPLE_ARTIST] * 10
        result = render_grid(artists)
        assert isinstance(result, html.Div)

    def test_contains_ten_cards(self):
        artists = [
            {**SAMPLE_ARTIST, "name": f"Artist {i}", "rank": i}
            for i in range(1, 11)
        ]
        result = render_grid(artists)
        # Flatten and count Div children
        cards = _collect_divs(result)
        assert len(cards) >= 10


class TestRenderGenreChart:
    def test_returns_dcc_graph(self):
        result = render_genre_chart(SAMPLE_GENRES)
        assert isinstance(result, dcc.Graph)

    def test_empty_genres_returns_graph(self):
        result = render_genre_chart([])
        assert isinstance(result, dcc.Graph)

    def test_figure_contains_genre_labels(self):
        result = render_genre_chart(SAMPLE_GENRES)
        fig = result.figure
        # Plotly Figure object — access data via .data attribute
        assert any(
            "indie rock" in str(getattr(trace, "y", "") or getattr(trace, "x", ""))
            for trace in fig.data
        )


# --- Helpers ---

def _contains_text(component, text: str) -> bool:
    """Recursively search a Dash component tree for a string."""
    if isinstance(component, str):
        return text in component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            return any(_contains_text(c, text) for c in children)
        return _contains_text(children, text)
    return False


def _collect_divs(component) -> list:
    """Recursively collect all html.Div instances."""
    results = []
    if isinstance(component, html.Div):
        results.append(component)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for c in children:
                results.extend(_collect_divs(c))
        elif children is not None:
            results.extend(_collect_divs(children))
    return results
