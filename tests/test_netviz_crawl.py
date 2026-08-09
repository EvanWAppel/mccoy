"""Crawl bounding + BFS priority tests (mocked sources / db)."""

import pytest

from netviz import crawl as crawl_mod


class FakeDB:
    """In-memory stand-in for netviz.db to prove idempotency."""

    def __init__(self):
        self.musicians = {}   # mbid -> id
        self.releases = {}    # mbid -> id
        self.credits = set()  # (musician_id, release_id, role)
        self._next = iter(range(1, 100000))

    def upsert_musician(self, mbid, name, primary_instrument=None, **kw):
        if mbid not in self.musicians:
            self.musicians[mbid] = next(self._next)
        return self.musicians[mbid]

    def upsert_release(self, mbid, title, year=None, label=None, **kw):
        if mbid not in self.releases:
            self.releases[mbid] = next(self._next)
        return self.releases[mbid]

    def add_credit(self, musician_id, release_id, role):
        self.credits.add((musician_id, release_id, role))


@pytest.fixture
def fake_db(mocker):
    db = FakeDB()
    for fn in ("upsert_musician", "upsert_release", "add_credit"):
        mocker.patch.object(crawl_mod.db, fn, getattr(db, fn))
    return db


def _wire_sources(mocker, releases_by_name, personnel_by_release):
    def mb_releases_for(name):
        return releases_by_name.get(name, [])

    def mb_personnel_for(rel_mbid):
        return personnel_by_release.get(rel_mbid, [])

    mocker.patch.object(
        crawl_mod.sources, "mb_releases_for", side_effect=mb_releases_for
    )
    mocker.patch.object(
        crawl_mod.sources, "mb_personnel_for", side_effect=mb_personnel_for
    )


class TestNodeCap:
    def test_crawl_stops_at_node_cap(self, mocker, fake_db):
        # Seed leads to a chain of discoverable musicians; cap at 2.
        releases = {
            "Seed": [{"mbid": "r1", "title": "R1", "year": 1960,
                      "label": "BN"}],
            "A": [{"mbid": "r2", "title": "R2", "year": 1961,
                   "label": "BN"}],
            "B": [{"mbid": "r3", "title": "R3", "year": 1962,
                   "label": "BN"}],
        }
        personnel = {
            "r1": [{"mbid": "m-seed", "name": "Seed", "instrument": "piano"},
                   {"mbid": "m-a", "name": "A", "instrument": "sax"},
                   {"mbid": "m-b", "name": "B", "instrument": "bass"}],
            "r2": [{"mbid": "m-a", "name": "A", "instrument": "sax"}],
            "r3": [{"mbid": "m-b", "name": "B", "instrument": "bass"}],
        }
        _wire_sources(mocker, releases, personnel)
        result = crawl_mod.crawl(seeds=["Seed"], node_cap=2, max_hops=2)
        assert len(result["crawled"]) <= 2


class TestBfsPriority:
    def test_most_connected_discovered_admitted_first(self, mocker, fake_db):
        # A co-appears on both seed releases (2 links); B on one (1 link).
        releases = {
            "Seed": [
                {"mbid": "r1", "title": "R1", "year": 1960, "label": "BN"},
                {"mbid": "r2", "title": "R2", "year": 1961, "label": "BN"},
            ],
            "A": [{"mbid": "r3", "title": "R3", "year": 1962, "label": "BN"}],
            "B": [{"mbid": "r4", "title": "R4", "year": 1963, "label": "BN"}],
        }
        personnel = {
            "r1": [{"mbid": "m-seed", "name": "Seed", "instrument": "piano"},
                   {"mbid": "m-a", "name": "A", "instrument": "sax"}],
            "r2": [{"mbid": "m-seed", "name": "Seed", "instrument": "piano"},
                   {"mbid": "m-a", "name": "A", "instrument": "sax"},
                   {"mbid": "m-b", "name": "B", "instrument": "bass"}],
            "r3": [{"mbid": "m-a", "name": "A", "instrument": "sax"}],
            "r4": [{"mbid": "m-b", "name": "B", "instrument": "bass"}],
        }
        _wire_sources(mocker, releases, personnel)
        # Cap = seed + exactly one discovered musician.
        result = crawl_mod.crawl(seeds=["Seed"], node_cap=2, max_hops=2)
        assert "A" in result["crawled"]
        assert "B" not in result["crawled"]


class TestReleaseCap:
    def test_per_musician_release_cap_respected(self, mocker, fake_db):
        releases = {
            "Seed": [
                {"mbid": f"r{i}", "title": f"R{i}", "year": 1960,
                 "label": "BN"}
                for i in range(5)
            ]
        }
        personnel = {
            f"r{i}": [{"mbid": "m-seed", "name": "Seed",
                       "instrument": "piano"}]
            for i in range(5)
        }
        _wire_sources(mocker, releases, personnel)
        crawl_mod.crawl(seeds=["Seed"], node_cap=10, max_hops=0,
                        release_cap=2)
        # Only 2 of the 5 releases should have been read for personnel.
        assert crawl_mod.sources.mb_personnel_for.call_count == 2


class TestIdempotency:
    def test_rerun_does_not_duplicate_rows(self, mocker, fake_db):
        releases = {
            "Seed": [{"mbid": "r1", "title": "R1", "year": 1960,
                      "label": "BN"}],
        }
        personnel = {
            "r1": [{"mbid": "m-seed", "name": "Seed", "instrument": "piano"},
                   {"mbid": "m-a", "name": "A", "instrument": "sax"}],
        }
        _wire_sources(mocker, releases, personnel)
        crawl_mod.crawl(seeds=["Seed"], node_cap=10, max_hops=0)
        m1, r1, c1 = (len(fake_db.musicians), len(fake_db.releases),
                      len(fake_db.credits))
        crawl_mod.crawl(seeds=["Seed"], node_cap=10, max_hops=0)
        assert (len(fake_db.musicians), len(fake_db.releases),
                len(fake_db.credits)) == (m1, r1, c1)


class TestUnresolved:
    def test_unresolved_names_reported_not_raised(self, mocker, fake_db):
        _wire_sources(mocker, {}, {})  # nothing resolves
        result = crawl_mod.crawl(seeds=["Ghost"], node_cap=10, max_hops=0)
        assert result["crawled"] == []
        assert "Ghost" in result["unresolved"]
