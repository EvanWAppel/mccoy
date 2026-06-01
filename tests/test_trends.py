import pytest
from datetime import datetime, timezone, timedelta
from dash import dcc, html
from components.trends import render_bump_chart, render_area_chart


def make_snapshot(snapshot_id: int, days_ago: int, artists: list[dict]) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "captured_at": datetime.now(timezone.utc) - timedelta(days=days_ago),
        "artists": artists,
    }


def make_artist(name: str, rank: int, genres: list[str]) -> dict:
    return {"name": name, "rank": rank, "artist_id": name.lower(),
            "image_url": None, "genres": genres}


SNAP_1 = make_snapshot(1, 14, [
    make_artist("Radiohead", 1, ["art rock"]),
    make_artist("Portishead", 2, ["trip hop"]),
    make_artist("Burial", 3, ["uk garage"]),
])

SNAP_2 = make_snapshot(2, 7, [
    make_artist("Portishead", 1, ["trip hop"]),
    make_artist("Radiohead", 2, ["art rock"]),
    make_artist("Burial", 3, ["uk garage"]),
])

TWO_SNAPS = [SNAP_1, SNAP_2]


class TestRenderBumpChart:
    def test_returns_graph_with_two_or_more_snapshots(self):
        result = render_bump_chart(TWO_SNAPS, n=3)
        assert isinstance(result, dcc.Graph)

    def test_returns_empty_state_with_zero_snapshots(self):
        result = render_bump_chart([], n=10)
        assert isinstance(result, html.Div)

    def test_returns_empty_state_with_one_snapshot(self):
        result = render_bump_chart([SNAP_1], n=10)
        assert isinstance(result, html.Div)

    def test_empty_state_contains_message(self):
        result = render_bump_chart([], n=10)
        assert _contains_text(result, "snapshot") or _contains_text(result, "week")

    def test_figure_has_one_trace_per_artist_in_top_n(self):
        result = render_bump_chart(TWO_SNAPS, n=3)
        # 3 unique artists in top 3
        assert len(result.figure.data) == 3

    def test_respects_n_limit(self):
        result = render_bump_chart(TWO_SNAPS, n=2)
        assert len(result.figure.data) <= 2

    def test_y_axis_inverted(self):
        result = render_bump_chart(TWO_SNAPS, n=3)
        # rank 1 should be at top — autorange should be reversed
        layout = result.figure.layout
        assert layout.yaxis.autorange == "reversed"


class TestRenderAreaChart:
    def test_returns_graph_with_two_or_more_snapshots(self):
        result = render_area_chart(TWO_SNAPS)
        assert isinstance(result, dcc.Graph)

    def test_returns_empty_state_with_zero_snapshots(self):
        result = render_area_chart([])
        assert isinstance(result, html.Div)

    def test_returns_empty_state_with_one_snapshot(self):
        result = render_area_chart([SNAP_1])
        assert isinstance(result, html.Div)

    def test_figure_has_one_trace_per_genre(self):
        result = render_area_chart(TWO_SNAPS)
        # 3 unique genres: art rock, trip hop, uk garage
        assert len(result.figure.data) == 3

    def test_traces_are_stacked_area(self):
        result = render_area_chart(TWO_SNAPS)
        for trace in result.figure.data:
            assert trace.stackgroup is not None

    def test_returns_empty_state_when_no_genres_available(self):
        snapshots = [
            make_snapshot(1, 14, [make_artist("Radiohead", 1, [])]),
            make_snapshot(2, 7, [make_artist("Portishead", 1, [])]),
        ]
        result = render_area_chart(snapshots)
        assert isinstance(result, html.Div)
        assert _contains_text(result, "genre")


# --- Helpers ---

def _contains_text(component, text: str) -> bool:
    if isinstance(component, str):
        return text.lower() in component.lower()
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            return any(_contains_text(c, text) for c in children)
        return _contains_text(children, text)
    return False
