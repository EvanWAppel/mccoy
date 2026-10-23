"""Synthetic marts snapshot for building the notebook (AAA-02).

The notebook's code and structure are written against this fixture, not
Evan's listening (the human-inspects-data rule: Evan runs it on the real
AAA-01 snapshot and writes the narrative, AAA-03). Artists and tracks
are made up. The data is seeded, so every run is identical.

`fct_plays` is generated; the other marts are derived from it the way
the dbt models in `analytics/models/marts/` derive them (30-minute
session gap, minutes rounded to 2 places, gaps-and-islands streaks).
Local time is a fixed UTC-7 for simplicity.
"""

import datetime as dt
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import ask
from scripts import export_marts

log = logging.getLogger(__name__)

SEED = 24
DAYS = 70
START = dt.date(2026, 8, 3)  # a Monday
UTC_OFFSET = pd.Timedelta(hours=-7)
SESSION_GAP = pd.Timedelta(minutes=30)

_FIRST = ["Paper", "Velvet", "Hollow", "Quiet", "Copper", "Lantern",
          "Salt", "Northern", "Glass", "Ember", "Static", "Orchard"]
_SECOND = ["Harbor", "Choir", "Moths", "Fields", "Signal", "Rivers"]
_WORDS = ["Night", "Window", "Summer", "Ghost", "Drive", "Letters",
          "Water", "Morning", "Wires", "Gold", "Home", "Echo"]


def _catalog(rng: np.random.Generator) -> pd.DataFrame:
    """24 made-up artists with 3-6 tracks each, Zipf-ish popularity."""
    rows = []
    for i in range(24):
        name = f"{_FIRST[i % 12]} {_SECOND[i % 6]}"
        weight = 1.0 / (i + 1) ** 0.9
        for j in range(int(rng.integers(3, 7))):
            words = rng.choice(_WORDS, size=2, replace=False)
            rows.append(
                {
                    "track_id": f"t{i:02d}{j}",
                    "track_name": " ".join(words),
                    "album_name": None if j == 5 else f"{name} LP{j % 2 + 1}",
                    "duration_ms": int(rng.integers(150, 360) * 1000),
                    "primary_artist_id": f"a{i:02d}",
                    "primary_artist_name": name,
                    # favour each artist's first tracks
                    "weight": weight / (j + 1),
                    # later artists are "discovered" partway through
                    "debut_day": 0 if i < 10 else int(rng.integers(5, DAYS)),
                }
            )
    return pd.DataFrame(rows)


def _plays(rng: np.random.Generator) -> pd.DataFrame:
    catalog = _catalog(rng)
    rows = []
    for day in range(DAYS):
        date = pd.Timestamp(START) + pd.Timedelta(days=day)
        weekend = date.day_of_week >= 5
        if rng.random() < (0.05 if weekend else 0.12):
            continue  # a day off
        n_sessions = int(rng.integers(1, 4 if weekend else 3))
        hours = rng.choice(
            [8, 9, 12, 17, 18, 21, 22] if not weekend else [10, 14, 20, 23],
            size=n_sessions,
            replace=False,
        )
        pool = catalog[catalog["debut_day"] <= day]
        p = (pool["weight"] / pool["weight"].sum()).to_numpy()
        for hour in sorted(hours):
            local = date + pd.Timedelta(
                hours=int(hour), minutes=int(rng.integers(0, 50))
            )
            n_plays = int(rng.choice([1, 2, 4, 6, 9, 14]))
            picks = rng.choice(len(pool), size=n_plays, p=p)
            for k in picks:
                track = pool.iloc[int(k)]
                rows.append({"played_at_local": local, **track.to_dict()})
                local += pd.Timedelta(
                    milliseconds=int(track["duration_ms"])
                ) + pd.Timedelta(seconds=int(rng.integers(0, 20)))
    plays = pd.DataFrame(rows).drop(columns=["weight", "debut_day"])
    plays = plays.sort_values("played_at_local").reset_index(drop=True)
    utc = plays["played_at_local"] - UTC_OFFSET
    plays["played_at"] = utc.dt.tz_localize("UTC")
    plays["play_id"] = [f"p{i:05d}" for i in range(len(plays))]
    gap = plays["played_at"].diff()
    plays["session_id"] = (gap.isna() | (gap > SESSION_GAP)).cumsum()
    return plays


def _minutes(ms: pd.Series) -> pd.Series:
    return (ms / 60000.0).round(2)


def _derive(plays: pd.DataFrame) -> dict[str, pd.DataFrame]:
    day = plays["played_at_local"].dt.normalize()
    sessions = (
        plays.groupby("session_id")
        .agg(
            started_at=("played_at", "min"),
            ended_at=("played_at", "max"),
            plays=("play_id", "size"),
            minutes=("duration_ms", "sum"),
            distinct_artists=("primary_artist_id", "nunique"),
        )
        .reset_index()
    )
    daily = (
        plays.assign(listen_date=day)
        .groupby("listen_date")
        .agg(
            plays=("play_id", "size"),
            minutes=("duration_ms", "sum"),
            distinct_artists=("primary_artist_id", "nunique"),
        )
        .reset_index()
    )
    how = (
        plays.assign(
            iso_dow=plays["played_at_local"].dt.day_of_week + 1,
            hour=plays["played_at_local"].dt.hour,
        )
        .groupby(["iso_dow", "hour"])
        .agg(plays=("play_id", "size"), minutes=("duration_ms", "sum"))
        .reset_index()
    )
    for frame in (sessions, daily, how):
        frame["minutes"] = _minutes(frame["minutes"])
    days = (
        plays.assign(listen_date=day)[
            ["primary_artist_id", "primary_artist_name", "listen_date"]
        ]
        .drop_duplicates(["primary_artist_id", "listen_date"])
        .sort_values(["primary_artist_id", "listen_date"])
    )
    rank = days.groupby("primary_artist_id").cumcount() + 1
    days["island"] = days["listen_date"] - pd.to_timedelta(rank, unit="D")
    streaks = (
        days.groupby(["primary_artist_id", "island"])
        .agg(
            artist_name=("primary_artist_name", "max"),
            streak_start=("listen_date", "min"),
            streak_end=("listen_date", "max"),
            streak_days=("listen_date", "size"),
        )
        .reset_index()
        .rename(columns={"primary_artist_id": "artist_id"})
    )
    return {
        "fct_listening_sessions": sessions,
        "mart_daily_listening": daily,
        "mart_hour_of_week": how,
        "mart_artist_streaks": streaks,
    }


def fixture_marts(seed: int = SEED) -> dict[str, pd.DataFrame]:
    """Every mart as a frame, columns in `ask.MARTS_SCHEMA` order."""
    plays = _plays(np.random.default_rng(seed))
    marts = {"fct_plays": plays, **_derive(plays)}
    return {
        mart: marts[mart][[c for c, _ in columns]].reset_index(drop=True)
        for mart, columns in ask.MARTS_SCHEMA.items()
    }


def write_fixture_snapshot(
    out_dir: Path | str, seed: int = SEED
) -> dict[str, int]:
    """Write the fixture marts as parquet with the AAA-01 export schema."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for mart, frame in fixture_marts(seed).items():
        table = pa.Table.from_pandas(
            frame, schema=export_marts._schema(mart), preserve_index=False
        )
        pq.write_table(table, out / f"{mart}.parquet", compression="zstd")
        counts[mart] = len(frame)
        log.info("fixture %s: %d rows", mart, len(frame))
    return counts
