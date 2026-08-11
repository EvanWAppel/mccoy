from netviz.ingest import cap_by_degree, focus_graph, prune_isolated


class TestFocusGraph:
    def test_drops_other_genre_and_pre_min_year(self):
        graph = {
            "nodes": [
                {"id": 1, "genre": "Hard Bop", "era": 1958},
                {"id": 2, "genre": "Modal", "era": 1961},
                {"id": 3, "genre": "Other", "era": 1960},   # swing/non-core
                {"id": 4, "genre": "Bebop", "era": 1949},   # pre-min-year
            ],
            "edges": [
                {"source": 1, "target": 2, "weight": 6},
                {"source": 1, "target": 3, "weight": 6},
                {"source": 1, "target": 4, "weight": 6},
            ],
        }
        focused = focus_graph(graph, min_year=1955)
        assert {n["id"] for n in focused["nodes"]} == {1, 2}
        assert focused["edges"] == [
            {"source": 1, "target": 2, "weight": 6}
        ]

    def test_none_genre_or_year_dropped(self):
        graph = {
            "nodes": [
                {"id": 1, "genre": "Hard Bop", "era": 1958},
                {"id": 2, "genre": None, "era": 1960},
                {"id": 3, "genre": "Modal", "era": None},
            ],
            "edges": [
                {"source": 1, "target": 2, "weight": 6},
                {"source": 1, "target": 3, "weight": 6},
            ],
        }
        focused = focus_graph(graph, min_year=1955)
        assert {n["id"] for n in focused["nodes"]} == set()


class TestCapByDegree:
    def test_noop_when_under_limit(self):
        graph = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2, "weight": 2}],
        }
        assert cap_by_degree(graph, limit=10) is graph

    def test_keeps_highest_degree_nodes(self):
        # Hub (1) connects to 2,3,4; node 5 dangles off 4 only.
        graph = {
            "nodes": [{"id": i} for i in range(1, 6)],
            "edges": [
                {"source": 1, "target": 2, "weight": 2},
                {"source": 1, "target": 3, "weight": 2},
                {"source": 1, "target": 4, "weight": 2},
                {"source": 4, "target": 5, "weight": 2},
            ],
        }
        capped = cap_by_degree(graph, limit=3)
        # Top-3 by degree: 1 (deg 3), 4 (deg 2), then 2/3/5 (deg 1) tie
        # -> lowest id (2) wins. Induced edges 1-2 and 1-4 survive.
        assert {n["id"] for n in capped["nodes"]} == {1, 2, 4}
        assert capped["edges"] == [
            {"source": 1, "target": 2, "weight": 2},
            {"source": 1, "target": 4, "weight": 2},
        ]


class TestPruneIsolated:
    def test_drops_nodes_with_no_edges(self):
        graph = {
            "nodes": [
                {"id": 1, "name": "A"},
                {"id": 2, "name": "B"},
                {"id": 3, "name": "Lonely"},
            ],
            "edges": [{"source": 1, "target": 2, "weight": 3}],
        }
        pruned = prune_isolated(graph)
        assert {n["id"] for n in pruned["nodes"]} == {1, 2}
        assert pruned["edges"] == graph["edges"]

    def test_empty_graph_stays_empty(self):
        assert prune_isolated({"nodes": [], "edges": []}) == {
            "nodes": [],
            "edges": [],
        }
