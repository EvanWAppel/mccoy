"""Group WW — Listening Patterns view (heatmap, daily minutes, streaks)."""
from datetime import date, timedelta

from dash import dcc

import demo_data
from components.patterns import day_streaks, render_patterns


class TestDayStreaks:
    def test_empty(self):
        assert day_streaks([], today=date(2026, 9, 30)) == (0, 0)

    def test_current_streak_runs_through_today(self):
        days = [date(2026, 9, d) for d in (20, 21, 28, 29, 30)]
        assert day_streaks(days, today=date(2026, 9, 30)) == (3, 3)

    def test_yesterday_still_counts_as_current(self):
        # Today isn't over yet; a streak ending yesterday is alive.
        days = [date(2026, 9, d) for d in (28, 29)]
        assert day_streaks(days, today=date(2026, 9, 30)) == (2, 2)

    def test_broken_streak_is_zero_but_longest_kept(self):
        days = [date(2026, 9, d) for d in (1, 2, 3, 4, 10)]
        assert day_streaks(days, today=date(2026, 9, 30)) == (0, 4)

    def test_duplicates_and_order_ignored(self):
        days = [date(2026, 9, 30), date(2026, 9, 29), date(2026, 9, 30)]
        assert day_streaks(days, today=date(2026, 9, 30)) == (2, 2)


class TestDemoPatterns:
    def test_deterministic(self):
        assert demo_data.demo_patterns() == demo_data.demo_patterns()

    def test_shape(self):
        data = demo_data.demo_patterns()
        assert data["hour_of_week"]
        for row in data["hour_of_week"]:
            assert 1 <= row["iso_dow"] <= 7
            assert 0 <= row["hour"] <= 23
        assert len(data["daily"]) == 30
        assert data["streaks"]


class TestRenderPatterns:
    def test_has_heatmap_and_daily_charts(self, component_ids):
        tree = render_patterns(demo_data.demo_patterns(), is_demo=True)
        ids = component_ids(tree)
        assert {"patterns-heatmap", "patterns-daily"} <= ids

    def test_heatmap_is_7_by_24(self, component_ids):
        tree = render_patterns(demo_data.demo_patterns(), is_demo=True)
        graph = _find(tree, "patterns-heatmap")
        z = graph.figure.data[0].z
        assert len(z) == 7 and all(len(row) == 24 for row in z)

    def test_demo_caption_says_sample(self, component_text):
        tree = render_patterns(demo_data.demo_patterns(), is_demo=True)
        assert "sample data" in component_text(tree).lower()

    def test_real_data_has_no_sample_caption(self, component_text):
        tree = render_patterns(demo_data.demo_patterns(), is_demo=False)
        assert "sample data" not in component_text(tree).lower()

    def test_shows_top_artist_streak(self, component_text):
        data = {
            "hour_of_week": [], "daily": [],
            "streaks": [
                {"artist_name": "Wayne Shorter", "streak_days": 4,
                 "streak_end": date(2026, 9, 30)},
                {"artist_name": "Lee Morgan", "streak_days": 2,
                 "streak_end": date(2026, 9, 12)},
            ],
        }
        text = component_text(render_patterns(data, is_demo=False))
        assert "Wayne Shorter" in text and "4 days" in text

    def test_empty_data_shows_empty_state(self, component_text):
        data = {"hour_of_week": [], "daily": [], "streaks": []}
        text = component_text(render_patterns(data, is_demo=False))
        assert "No play history yet" in text


class TestDailyWindow:
    """Daily chart covers the last 30 calendar days, not 30 rows."""

    TODAY = date(2026, 9, 30)

    def _dates(self, daily):
        data = {"hour_of_week": [], "daily": daily, "streaks": []}
        tree = render_patterns(data, is_demo=False, today=self.TODAY)
        return list(_find(tree, "patterns-daily").figure.data[0].x)

    def _row(self, back):
        return {"listen_date": self.TODAY - timedelta(days=back),
                "plays": 1, "minutes": 3.9}

    def test_row_40_days_old_excluded(self):
        dates = self._dates([self._row(40), self._row(1)])
        assert dates == [self.TODAY - timedelta(days=1)]

    def test_row_exactly_29_days_old_included(self):
        dates = self._dates([self._row(30), self._row(29)])
        assert dates == [self.TODAY - timedelta(days=29)]

    def test_demo_data_within_window(self):
        data = demo_data.demo_patterns(today=self.TODAY)
        tree = render_patterns(data, is_demo=True, today=self.TODAY)
        dates = list(_find(tree, "patterns-daily").figure.data[0].x)
        assert dates
        start = self.TODAY - timedelta(days=29)
        assert all(start <= d <= self.TODAY for d in dates)
        expected = [r["listen_date"] for r in data["daily"]
                    if r["listen_date"] >= start]
        assert dates == expected


def _find(tree, target):
    from tests.conftest import _walk_components
    return next(
        c for c in _walk_components(tree)
        if getattr(c, "id", None) == target and isinstance(c, dcc.Graph)
    )


def test_tz_matches_dbt_project():
    from pathlib import Path

    from components.patterns import LISTENING_TZ
    cfg = (Path(__file__).parent.parent / "analytics"
           / "dbt_project.yml").read_text()
    assert f'listening_tz: "{LISTENING_TZ}"' in cfg
