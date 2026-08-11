from netviz.ingest import prune_isolated


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
