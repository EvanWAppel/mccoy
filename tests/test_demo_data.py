"""Demo fallback data for the public (no-login) dashboard."""

import demo_data


def test_demo_snapshots_have_at_least_two():
    # The trends bump chart needs >=2 snapshots to render.
    snaps = demo_data.demo_snapshots("short_term")
    assert len(snaps) >= 2


def test_demo_snapshot_artists_have_required_fields():
    snap = demo_data.demo_latest_snapshot("short_term")
    assert snap["artists"]
    for a in snap["artists"]:
        assert a["rank"] >= 1
        assert a["name"]
        assert isinstance(a["genres"], list)
        assert a["genres"]


def test_demo_ranks_are_contiguous():
    snap = demo_data.demo_latest_snapshot()
    ranks = sorted(a["rank"] for a in snap["artists"])
    assert ranks == list(range(1, len(ranks) + 1))


def test_demo_snapshots_are_not_real_rows():
    # Negative snapshot_ids make it obvious this is not DB data.
    for snap in demo_data.demo_snapshots():
        assert snap["snapshot_id"] < 0
