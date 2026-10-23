"""Data code for `analysis/listening.ipynb` (AAA-02).

Pure pandas over the marts snapshot written by `scripts/export_marts.py`
(or the synthetic one from `analysis/fixture.py`). Every function takes
mart frames and returns a number, dict or frame, so it is unit-tested in
`tests/test_analysis.py`; the notebook only draws and narrates.
"""

import logging
from pathlib import Path

import pandas as pd

import ask

log = logging.getLogger(__name__)

DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SESSION_BUCKETS = [0, 5, 15, 30, 60, float("inf")]
SESSION_LABELS = ["<5", "5-15", "15-30", "30-60", "60+"]
DATE_COLUMNS = ("listen_date", "streak_start", "streak_end")


def load_marts(data_dir: Path | str) -> dict[str, pd.DataFrame]:
    """Read `<mart>.parquet` for every mart in `ask.MARTS_SCHEMA`.

    Date columns come back as pandas datetimes (midnight) so they plot
    and resample like the timestamp columns. A missing file raises.
    """
    data = Path(data_dir)
    marts: dict[str, pd.DataFrame] = {}
    for mart in ask.MARTS_SCHEMA:
        frame = pd.read_parquet(data / f"{mart}.parquet")
        for col in DATE_COLUMNS:
            if col in frame:
                frame[col] = pd.to_datetime(frame[col])
        marts[mart] = frame
        log.info("loaded %s: %d rows", mart, len(frame))
    return marts


def _minutes(plays: pd.DataFrame) -> pd.Series:
    return plays["duration_ms"] / 60000.0


def summary(plays: pd.DataFrame) -> dict:
    """Headline counts over `fct_plays`."""
    days = plays["played_at_local"].dt.normalize()
    first, last = days.min(), days.max()
    return {
        "plays": len(plays),
        "minutes": float(_minutes(plays).sum()),
        "artists": int(plays["primary_artist_id"].nunique()),
        "tracks": int(plays["track_id"].nunique()),
        "first_day": first.date(),
        "last_day": last.date(),
        "days_listened": int(days.nunique()),
        "days_in_range": (last - first).days + 1,
    }


def daily_series(daily: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """`mart_daily_listening` on a gap-free daily index.

    Days without listening are 0, and `minutes_rolling` is the trailing
    `window`-day mean of minutes (partial windows at the start).
    """
    out = daily.set_index("listen_date")[
        ["plays", "minutes", "distinct_artists"]
    ].sort_index()
    full = pd.date_range(out.index.min(), out.index.max(), freq="D")
    out = out.reindex(full, fill_value=0)
    out.index.name = "listen_date"
    out["minutes_rolling"] = (
        out["minutes"].rolling(window, min_periods=1).mean()
    )
    return out


def weekly_totals(daily: pd.DataFrame) -> pd.DataFrame:
    """Plays, minutes and days listened per ISO week (Monday start)."""
    frame = daily.set_index("listen_date").sort_index()
    weeks = frame.resample("W-MON", label="left", closed="left")
    out = pd.DataFrame(
        {
            "plays": weeks["plays"].sum(),
            "minutes": weeks["minutes"].sum(),
            "days_listened": weeks["plays"].apply(
                lambda s: int((s > 0).sum())
            ),
        }
    )
    out.index.name = "week"
    return out


def hour_of_week_grid(
    how: pd.DataFrame, value: str = "minutes"
) -> pd.DataFrame:
    """`mart_hour_of_week` as a 7 x 24 grid (Mon..Sun x 0..23), 0-filled."""
    grid = how.pivot_table(
        index="iso_dow", columns="hour", values=value, aggfunc="sum"
    ).reindex(index=range(1, 8), columns=range(24), fill_value=0)
    grid = grid.fillna(0)
    grid.index = DOW_LABELS
    grid.columns.name = "hour"
    return grid


def session_stats(sessions: pd.DataFrame) -> dict:
    """Typical session size over `fct_listening_sessions`."""
    return {
        "sessions": len(sessions),
        "median_minutes": float(sessions["minutes"].median()),
        "median_plays": float(sessions["plays"].median()),
        "single_play_share": float((sessions["plays"] == 1).mean()),
    }


def session_length_buckets(sessions: pd.DataFrame) -> pd.Series:
    """Session counts per length bucket in minutes (<5 .. 60+)."""
    buckets = pd.cut(
        sessions["minutes"],
        SESSION_BUCKETS,
        labels=SESSION_LABELS,
        right=False,
    )
    return buckets.value_counts().reindex(SESSION_LABELS, fill_value=0)


def top_artists(plays: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """Top `n` artists by plays, with minutes and share of all plays."""
    frame = plays.assign(minutes=_minutes(plays))
    out = (
        frame.groupby("primary_artist_id")
        .agg(
            artist=("primary_artist_name", "max"),
            plays=("primary_artist_id", "size"),
            minutes=("minutes", "sum"),
        )
        .sort_values(["plays", "minutes", "artist"],
                     ascending=[False, False, True])
        .head(n)
        .reset_index(drop=True)
    )
    out["share"] = out["plays"] / len(plays)
    return out


def concentration(plays: pd.DataFrame, k: int = 10) -> float:
    """Share of all plays that go to the top `k` artists."""
    counts = plays["primary_artist_id"].value_counts()
    return float(counts.head(k).sum() / counts.sum())


def new_artists_by_week(plays: pd.DataFrame) -> pd.DataFrame:
    """Per ISO week: artists played, and how many were played first."""
    frame = plays.assign(
        week=plays["played_at_local"].dt.to_period("W-SUN").dt.start_time
    )
    first = frame.groupby("primary_artist_id")["week"].min()
    out = pd.DataFrame(
        {
            "artists": frame.groupby("week")["primary_artist_id"].nunique(),
            "new_artists": first.value_counts(),
        }
    ).fillna(0)
    out = out.astype(int).sort_index()
    out.index.name = "week"
    return out


def top_streaks(streaks: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The `n` longest artist streaks, longest (then earliest) first."""
    return (
        streaks.sort_values(
            ["streak_days", "streak_start"], ascending=[False, True]
        )
        .head(n)
        .reset_index(drop=True)
    )


def top_tracks(plays: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """Top `n` tracks by plays."""
    return (
        plays.groupby("track_id")
        .agg(
            track=("track_name", "max"),
            artist=("primary_artist_name", "max"),
            plays=("track_id", "size"),
        )
        .sort_values(["plays", "track"], ascending=[False, True])
        .head(n)
        .reset_index(drop=True)
    )


def replay_share(plays: pd.DataFrame) -> float:
    """Share of plays that are of a track played more than once."""
    counts = plays["track_id"].value_counts()
    return float(counts[counts > 1].sum() / counts.sum())
