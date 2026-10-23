"""Listening analysis notebook (AAA-02), built on fixture data only.

`analysis/fixture.py` makes a synthetic marts snapshot shaped like the
AAA-01 export; `analysis/metrics.py` holds the tested data code the
notebook calls; the notebook itself is checked for structure and run
end to end on the fixture snapshot (figures are not shown).
"""

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

import ask
from analysis import fixture, metrics
from scripts import export_marts

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "analysis" / "listening.ipynb"


@pytest.fixture(scope="module")
def fixture_snapshot(tmp_path_factory):
    out = tmp_path_factory.mktemp("snapshot")
    fixture.write_fixture_snapshot(out)
    return out


@pytest.fixture
def marts(fixture_snapshot):
    return metrics.load_marts(fixture_snapshot)


# --- fixture snapshot -----------------------------------------------------


def test_fixture_writes_every_mart_with_export_schema(fixture_snapshot):
    for mart in ask.MARTS_SCHEMA:
        table = pq.read_table(fixture_snapshot / f"{mart}.parquet")
        assert table.schema.equals(export_marts._schema(mart)), mart


def test_fixture_is_deterministic(tmp_path):
    a = fixture.fixture_marts()
    b = fixture.fixture_marts()
    for mart in ask.MARTS_SCHEMA:
        pd.testing.assert_frame_equal(a[mart], b[mart])


def test_fixture_has_enough_shape_to_analyse():
    plays = fixture.fixture_marts()["fct_plays"]
    assert len(plays) >= 500
    assert plays["primary_artist_id"].nunique() >= 15
    assert plays["played_at_local"].dt.normalize().nunique() >= 40


def test_fixture_aggregates_agree_with_plays():
    m = fixture.fixture_marts()
    plays = m["fct_plays"]
    assert m["mart_daily_listening"]["plays"].sum() == len(plays)
    assert m["mart_hour_of_week"]["plays"].sum() == len(plays)
    assert m["fct_listening_sessions"]["plays"].sum() == len(plays)
    assert set(m["fct_listening_sessions"]["session_id"]) == set(
        plays["session_id"]
    )


def test_fixture_sessions_follow_the_30_minute_gap_rule():
    plays = fixture.fixture_marts()["fct_plays"].sort_values("played_at")
    gap = plays["played_at"].diff()
    new = plays["session_id"].diff().fillna(1) != 0
    assert (new == (gap.isna() | (gap > pd.Timedelta(minutes=30)))).all()


def test_fixture_streaks_cover_every_artist_day():
    m = fixture.fixture_marts()
    days = (
        m["fct_plays"]
        .assign(d=lambda f: f["played_at_local"].dt.normalize())
        .drop_duplicates(["primary_artist_id", "d"])
    )
    assert m["mart_artist_streaks"]["streak_days"].sum() == len(days)


# --- load_marts -----------------------------------------------------------


def test_load_marts_returns_every_mart_as_frames(marts):
    assert set(marts) == set(ask.MARTS_SCHEMA)
    for mart, columns in ask.MARTS_SCHEMA.items():
        assert list(marts[mart].columns) == [c for c, _ in columns]


def test_load_marts_fails_loudly_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        metrics.load_marts(tmp_path)


# --- metrics on small hand-made frames ------------------------------------


def _plays(rows):
    cols = [
        "played_at_local",
        "track_id",
        "track_name",
        "duration_ms",
        "primary_artist_id",
        "primary_artist_name",
    ]
    frame = pd.DataFrame(rows, columns=cols)
    frame["played_at_local"] = pd.to_datetime(frame["played_at_local"])
    return frame


@pytest.fixture
def small_plays():
    return _plays(
        [
            ("2026-10-05 09:00", "t1", "One", 60000, "a", "A"),
            ("2026-10-05 09:05", "t1", "One", 60000, "a", "A"),
            ("2026-10-06 21:00", "t2", "Two", 120000, "b", "B"),
            ("2026-10-13 21:00", "t3", "Three", 180000, "c", "C"),
        ]
    )


def test_summary_counts(small_plays):
    s = metrics.summary(small_plays)
    assert s["plays"] == 4
    assert s["minutes"] == pytest.approx(7.0)
    assert s["artists"] == 3
    assert s["tracks"] == 3
    assert s["first_day"] == dt.date(2026, 10, 5)
    assert s["last_day"] == dt.date(2026, 10, 13)
    assert s["days_listened"] == 3
    assert s["days_in_range"] == 9


def test_daily_series_fills_gaps_and_rolls():
    daily = pd.DataFrame(
        {
            "listen_date": pd.to_datetime(["2026-10-01", "2026-10-03"]),
            "plays": [2, 4],
            "minutes": [7.0, 14.0],
            "distinct_artists": [1, 2],
        }
    )
    out = metrics.daily_series(daily, window=2)
    assert list(out.index.date) == [
        dt.date(2026, 10, 1),
        dt.date(2026, 10, 2),
        dt.date(2026, 10, 3),
    ]
    assert list(out["minutes"]) == [7.0, 0.0, 14.0]
    assert list(out["plays"]) == [2, 0, 4]
    assert list(out["minutes_rolling"]) == [7.0, 3.5, 7.0]


def test_weekly_totals_start_on_monday():
    daily = pd.DataFrame(
        {
            "listen_date": pd.to_datetime(
                ["2026-10-04", "2026-10-05", "2026-10-11", "2026-10-12"]
            ),
            "plays": [1, 2, 3, 4],
            "minutes": [1.0, 2.0, 3.0, 4.0],
            "distinct_artists": [1, 1, 1, 1],
        }
    )
    out = metrics.weekly_totals(daily)
    assert list(out.index.date) == [
        dt.date(2026, 9, 28),
        dt.date(2026, 10, 5),
        dt.date(2026, 10, 12),
    ]
    assert list(out["plays"]) == [1, 5, 4]
    assert list(out["days_listened"]) == [1, 2, 1]


def test_hour_of_week_grid_is_7_by_24_with_zeros():
    how = pd.DataFrame(
        {"iso_dow": [1, 7], "hour": [8, 23], "plays": [3, 2],
         "minutes": [9.0, 4.0]}
    )
    grid = metrics.hour_of_week_grid(how, value="minutes")
    assert grid.shape == (7, 24)
    assert list(grid.index) == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat",
                                "Sun"]
    assert grid.loc["Mon", 8] == 9.0
    assert grid.loc["Sun", 23] == 4.0
    assert grid.to_numpy().sum() == 13.0


def test_session_stats():
    sessions = pd.DataFrame(
        {
            "session_id": [1, 2, 3, 4],
            "plays": [1, 3, 5, 11],
            "minutes": [3.0, 10.0, 20.0, 47.0],
            "distinct_artists": [1, 2, 2, 6],
        }
    )
    s = metrics.session_stats(sessions)
    assert s["sessions"] == 4
    assert s["median_minutes"] == pytest.approx(15.0)
    assert s["median_plays"] == pytest.approx(4.0)
    assert s["single_play_share"] == pytest.approx(0.25)


def test_session_length_buckets_cover_every_session():
    sessions = pd.DataFrame({"minutes": [2.0, 12.0, 25.0, 50.0, 200.0]})
    out = metrics.session_length_buckets(sessions)
    assert out.sum() == 5
    assert list(out.index) == ["<5", "5-15", "15-30", "30-60", "60+"]
    assert list(out) == [1, 1, 1, 1, 1]


def test_top_artists_ranks_by_plays_with_share(small_plays):
    out = metrics.top_artists(small_plays, n=2)
    # B and C tie on plays; C wins on minutes
    assert list(out["artist"]) == ["A", "C"]
    assert list(out["plays"]) == [2, 1]
    assert list(out["minutes"]) == [2.0, 3.0]
    assert list(out["share"]) == [0.5, 0.25]


def test_concentration_is_top_k_share(small_plays):
    assert metrics.concentration(small_plays, k=1) == pytest.approx(0.5)
    assert metrics.concentration(small_plays, k=10) == pytest.approx(1.0)


def test_new_artists_by_week_counts_first_plays(small_plays):
    out = metrics.new_artists_by_week(small_plays)
    assert list(out.index.date) == [
        dt.date(2026, 10, 5),
        dt.date(2026, 10, 12),
    ]
    assert list(out["new_artists"]) == [2, 1]
    assert list(out["artists"]) == [2, 1]


def test_top_streaks_longest_first():
    streaks = pd.DataFrame(
        {
            "artist_id": ["a", "b", "a"],
            "artist_name": ["A", "B", "A"],
            "streak_start": pd.to_datetime(
                ["2026-10-01", "2026-10-02", "2026-10-10"]
            ),
            "streak_end": pd.to_datetime(
                ["2026-10-02", "2026-10-06", "2026-10-10"]
            ),
            "streak_days": [2, 5, 1],
        }
    )
    out = metrics.top_streaks(streaks, n=2)
    assert list(out["artist_name"]) == ["B", "A"]
    assert list(out["streak_days"]) == [5, 2]


def test_top_tracks_and_replay_share(small_plays):
    out = metrics.top_tracks(small_plays, n=1)
    assert list(out["track"]) == ["One"]
    assert list(out["artist"]) == ["A"]
    assert list(out["plays"]) == [2]
    # 2 of 4 plays are of a track played more than once
    assert metrics.replay_share(small_plays) == pytest.approx(0.5)


# --- the notebook ---------------------------------------------------------


def _notebook():
    return json.loads(NOTEBOOK.read_text())


def _source(cell):
    src = cell["source"]
    return "".join(src) if isinstance(src, list) else src


SECTIONS = [
    "## 0. Data",
    "## 1. How much I listen",
    "## 2. When I listen",
    "## 3. Sessions",
    "## 4. Who I listen to",
    "## 5. Streaks",
    "## 6. Repeats",
    "## 7. Caveats",
]


def test_notebook_is_valid_nbformat_4():
    nb = _notebook()
    assert nb["nbformat"] == 4
    assert all(c["cell_type"] in {"markdown", "code"} for c in nb["cells"])


def test_notebook_has_the_sections_in_order():
    heads = [
        line
        for c in _notebook()["cells"]
        if c["cell_type"] == "markdown"
        for line in _source(c).splitlines()
        if line.startswith("## ")
    ]
    assert [h for h in heads if h in SECTIONS] == SECTIONS


def test_every_section_leaves_narrative_to_evan():
    md = [
        _source(c)
        for c in _notebook()["cells"]
        if c["cell_type"] == "markdown"
    ]
    todos = sum(s.count("TODO(Evan)") for s in md)
    assert todos >= len(SECTIONS)


def test_notebook_is_committed_without_outputs():
    for cell in _notebook()["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


def test_notebook_defaults_to_fixture_data():
    code = "\n".join(
        _source(c)
        for c in _notebook()["cells"]
        if c["cell_type"] == "code"
    )
    assert 'SOURCE = "fixture"' in code


def test_notebook_runs_end_to_end_on_fixture(monkeypatch, tmp_path):
    import plotly.basedatatypes

    shown = []
    monkeypatch.setattr(
        plotly.basedatatypes.BaseFigure,
        "show",
        lambda self, *a, **k: shown.append(self),
    )
    monkeypatch.chdir(ROOT / "analysis")
    namespace = {"display": print}
    for cell in _notebook()["cells"]:
        if cell["cell_type"] == "code":
            exec(compile(_source(cell), str(NOTEBOOK), "exec"), namespace)
    assert namespace["SOURCE"] == "fixture"
    assert len(shown) >= 6
