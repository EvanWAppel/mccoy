import random

import pytest

from netviz.paths import describe_path, random_interesting_pair, shortest_path


def _graph(edges, extra_nodes=()):
    """Build a graph dict from (a, b, weight) tuples; names are 'M<id>'."""
    ids = {n for a, b, _ in edges for n in (a, b)} | set(extra_nodes)
    return {
        "nodes": [{"id": i, "name": f"M{i}"} for i in sorted(ids)],
        "edges": [
            {"source": a, "target": b, "weight": w,
             "sample_releases": [f"R{a}-{b}"]}
            for a, b, w in edges
        ],
    }


@pytest.fixture
def chain_graph():
    # 1-2-3-4 chain, plus an isolated pair 8-9 (a second component).
    return _graph([(1, 2, 3), (2, 3, 1), (3, 4, 5), (8, 9, 2)])


class TestShortestPath:
    def test_finds_chain_as_string_ids(self, chain_graph):
        assert shortest_path(chain_graph, 1, 4) == ["1", "2", "3", "4"]

    def test_accepts_string_ids(self, chain_graph):
        assert shortest_path(chain_graph, "4", "2") == ["4", "3", "2"]

    def test_direct_neighbors(self, chain_graph):
        assert shortest_path(chain_graph, 1, 2) == ["1", "2"]

    def test_no_path_across_components_returns_none(self, chain_graph):
        assert shortest_path(chain_graph, 1, 9) is None

    def test_same_node_raises(self, chain_graph):
        with pytest.raises(ValueError):
            shortest_path(chain_graph, 2, 2)

    def test_unknown_node_raises(self, chain_graph):
        with pytest.raises(KeyError):
            shortest_path(chain_graph, 1, 999)

    def test_prefers_fewest_hops_over_heavy_edges(self):
        # Direct weak edge beats a strong two-hop detour.
        g = _graph([(1, 2, 1), (1, 3, 50), (3, 2, 50)])
        assert shortest_path(g, 1, 2) == ["1", "2"]

    def test_tie_prefers_strongest_weakest_link(self):
        # Two 2-hop paths: via 2 (min 5, total 10) and via 3
        # (min 2, total 102). Strongest chain = highest minimum.
        g = _graph([(1, 2, 5), (2, 4, 5), (1, 3, 100), (3, 4, 2)])
        assert shortest_path(g, 1, 4) == ["1", "2", "4"]

    def test_tie_on_weakest_link_prefers_greater_total(self):
        # Both paths have min 3; via 3 totals 13, via 2 totals 6.
        g = _graph([(1, 2, 3), (2, 4, 3), (1, 3, 10), (3, 4, 3)])
        assert shortest_path(g, 1, 4) == ["1", "3", "4"]

    def test_tie_break_is_not_fooled_by_greedy_prefix(self):
        # To reach 4, prefix via 2 has min 5 / total 10 and via 3 has
        # min 3 / total 100. The last edge (weight 2) caps both at min
        # 2, so the greater total (via 3) must win. A greedy per-node
        # (min, total) comparison would wrongly keep the via-2 prefix.
        g = _graph([
            (1, 2, 5), (2, 4, 5), (1, 3, 3), (3, 4, 97), (4, 5, 2),
        ])
        assert shortest_path(g, 1, 5) == ["1", "3", "4", "5"]

    def test_full_ties_are_deterministic(self):
        g = _graph([(1, 2, 1), (2, 4, 1), (1, 3, 1), (3, 4, 1)])
        first = shortest_path(g, 1, 4)
        assert all(shortest_path(g, 1, 4) == first for _ in range(5))

    def test_missing_weight_defaults_to_one(self):
        g = {
            "nodes": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}],
            "edges": [{"source": 1, "target": 2}],
        }
        assert shortest_path(g, 1, 2) == ["1", "2"]


class TestDescribePath:
    def test_hops_carry_names_release_and_weight(self, chain_graph):
        hops = describe_path(chain_graph, ["1", "2", "3"])
        assert hops == [
            {"from": "M1", "to": "M2", "release": "R1-2", "weight": 3},
            {"from": "M2", "to": "M3", "release": "R2-3", "weight": 1},
        ]

    def test_release_found_regardless_of_edge_direction(self, chain_graph):
        hops = describe_path(chain_graph, ["2", "1"])
        assert hops[0]["release"] == "R1-2"

    def test_missing_sample_release_is_none(self):
        g = {
            "nodes": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}],
            "edges": [{"source": 1, "target": 2, "weight": 1}],
        }
        assert describe_path(g, ["1", "2"])[0]["release"] is None


class TestRandomInterestingPair:
    def test_pair_is_at_least_min_hops_apart(self, chain_graph):
        a, b = random_interesting_pair(
            chain_graph, random.Random(0), min_hops=3
        )
        path = shortest_path(chain_graph, a, b)
        assert path is not None
        assert len(path) - 1 >= 3

    def test_seeded_rng_is_deterministic(self, chain_graph):
        picks = {
            random_interesting_pair(chain_graph, random.Random(7))
            for _ in range(3)
        }
        assert len(picks) == 1

    def test_returns_none_when_no_pair_qualifies(self, chain_graph):
        assert random_interesting_pair(
            chain_graph, random.Random(0), min_hops=10
        ) is None
