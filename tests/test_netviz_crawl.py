"""Crawl bounding + BFS priority tests (mocked Discogs sources / db)."""

import pytest

from netviz import crawl as crawl_mod


class FakeDB:
    """In-memory stand-in for netviz.db to prove idempotency."""

    def __init__(self):
        self.musicians = {}   # discogs_id -> id
        self.releases = {}    # discogs_id -> id
        self.credits = set()  # (musician_id, release_id, role)
        self.styles = {}      # release_id -> styles
        self._next = iter(range(1, 100000))

    def upsert_musician_by_discogs(self, discogs_id, name,
                                   primary_instrument=None):
        if discogs_id not in self.musicians:
            self.musicians[discogs_id] = next(self._next)
        return self.musicians[discogs_id]

    def upsert_release_by_discogs(self, discogs_id, title, year=None,
                                  label=None, styles=None):
        if discogs_id not in self.releases:
            self.releases[discogs_id] = next(self._next)
        return self.releases[discogs_id]

    def add_credit(self, musician_id, release_id, role):
        self.credits.add((musician_id, release_id, role))

    def set_release_styles(self, release_id, styles):
        self.styles[release_id] = styles


@pytest.fixture
def fake_db(mocker):
    db = FakeDB()
    for fn in ("upsert_musician_by_discogs", "upsert_release_by_discogs",
               "add_credit", "set_release_styles"):
        mocker.patch.object(crawl_mod.db, fn, getattr(db, fn))
    return db


def _wire_sources(mocker, releases_by_name, personnel_by_release):
    def discogs_releases_for(name, limit=40):
        return releases_by_name.get(name, [])[:limit]

    def discogs_personnel_for(release_did):
        return {
            "styles": None,
            "personnel": personnel_by_release.get(release_did, []),
        }

    mocker.patch.object(
        crawl_mod.sources, "discogs_releases_for",
        side_effect=discogs_releases_for,
    )
    mocker.patch.object(
        crawl_mod.sources, "discogs_personnel_for",
        side_effect=discogs_personnel_for,
    )


def _rel(did, title="R", year=1960):
    return {"discogs_id": did, "title": title, "year": year, "label": "BN"}


def _person(did, name, instrument="sax"):
    return {"discogs_id": did, "name": name, "instrument": instrument}


class TestNodeCap:
    def test_crawl_stops_at_node_cap(self, mocker, fake_db):
        releases = {
            "Seed": [_rel("r1")],
            "A": [_rel("r2")],
            "B": [_rel("r3")],
        }
        personnel = {
            "r1": [_person("m-seed", "Seed", "piano"),
                   _person("m-a", "A"), _person("m-b", "B", "bass")],
            "r2": [_person("m-a", "A")],
            "r3": [_person("m-b", "B", "bass")],
        }
        _wire_sources(mocker, releases, personnel)
        result = crawl_mod.crawl(seeds=["Seed"], node_cap=2, max_hops=2)
        assert len(result["crawled"]) <= 2


class TestBfsPriority:
    def test_most_connected_discovered_admitted_first(self, mocker, fake_db):
        releases = {
            "Seed": [_rel("r1"), _rel("r2")],
            "A": [_rel("r3")],
            "B": [_rel("r4")],
        }
        personnel = {
            "r1": [_person("m-seed", "Seed", "piano"), _person("m-a", "A")],
            "r2": [_person("m-seed", "Seed", "piano"), _person("m-a", "A"),
                   _person("m-b", "B", "bass")],
            "r3": [_person("m-a", "A")],
            "r4": [_person("m-b", "B", "bass")],
        }
        _wire_sources(mocker, releases, personnel)
        result = crawl_mod.crawl(seeds=["Seed"], node_cap=2, max_hops=2)
        assert "A" in result["crawled"]
        assert "B" not in result["crawled"]


class TestReleaseCap:
    def test_per_musician_release_cap_respected(self, mocker, fake_db):
        releases = {"Seed": [_rel(f"r{i}") for i in range(5)]}
        personnel = {
            f"r{i}": [_person("m-seed", "Seed", "piano")] for i in range(5)
        }
        _wire_sources(mocker, releases, personnel)
        crawl_mod.crawl(seeds=["Seed"], node_cap=10, max_hops=0,
                        release_cap=2)
        assert crawl_mod.sources.discogs_personnel_for.call_count == 2


class TestIdempotency:
    def test_rerun_does_not_duplicate_rows(self, mocker, fake_db):
        releases = {"Seed": [_rel("r1")]}
        personnel = {
            "r1": [_person("m-seed", "Seed", "piano"), _person("m-a", "A")],
        }
        _wire_sources(mocker, releases, personnel)
        crawl_mod.crawl(seeds=["Seed"], node_cap=10, max_hops=0)
        counts = (len(fake_db.musicians), len(fake_db.releases),
                  len(fake_db.credits))
        crawl_mod.crawl(seeds=["Seed"], node_cap=10, max_hops=0)
        assert (len(fake_db.musicians), len(fake_db.releases),
                len(fake_db.credits)) == counts


class TestUnresolved:
    def test_unresolved_names_reported_not_raised(self, mocker, fake_db):
        _wire_sources(mocker, {}, {})
        result = crawl_mod.crawl(seeds=["Ghost"], node_cap=10, max_hops=0)
        assert result["crawled"] == []
        assert "Ghost" in result["unresolved"]
