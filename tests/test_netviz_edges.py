from netviz.edges import build_edges


def _credit(musician_id, release_id, title):
    return {
        "musician_id": musician_id,
        "release_id": release_id,
        "release_title": title,
    }


class TestBuildEdges:
    def test_co_credit_creates_weighted_edge(self):
        # Musicians 1 and 2 share two releases -> weight 2.
        credits = [
            _credit(1, 10, "The Sidewinder"),
            _credit(2, 10, "The Sidewinder"),
            _credit(1, 11, "Search for the New Land"),
            _credit(2, 11, "Search for the New Land"),
        ]
        edges = build_edges(credits)
        assert len(edges) == 1
        edge = edges[0]
        assert {edge["musician_a"], edge["musician_b"]} == {1, 2}
        assert edge["weight"] == 2

    def test_no_edge_for_solo_release(self):
        credits = [_credit(1, 10, "Solo")]
        assert build_edges(credits) == []

    def test_prunes_weak_edges_below_min_weight(self):
        # Pair (1,2) shares 2 releases; pair (1,3) shares only 1.
        credits = [
            _credit(1, 10, "A"),
            _credit(2, 10, "A"),
            _credit(1, 11, "B"),
            _credit(2, 11, "B"),
            _credit(1, 12, "C"),
            _credit(3, 12, "C"),
        ]
        edges = build_edges(credits, min_weight=2)
        pairs = {frozenset((e["musician_a"], e["musician_b"])) for e in edges}
        assert frozenset((1, 2)) in pairs
        assert frozenset((1, 3)) not in pairs

    def test_sample_releases_populated_for_tooltip(self):
        credits = [
            _credit(1, 10, "The Sidewinder"),
            _credit(2, 10, "The Sidewinder"),
        ]
        edges = build_edges(credits, min_weight=1)
        assert edges[0]["sample_releases"] == ["The Sidewinder"]

    def test_dedupes_repeated_credit_on_same_release(self):
        # Same musician credited twice on one release (two instruments)
        # must not inflate the shared-release weight.
        credits = [
            _credit(1, 10, "A"),
            _credit(1, 10, "A"),
            _credit(2, 10, "A"),
        ]
        edges = build_edges(credits, min_weight=1)
        assert len(edges) == 1
        assert edges[0]["weight"] == 1
