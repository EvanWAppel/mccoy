import json
from pathlib import Path

import dash_cytoscape as cyto
from dash import html

from components.network import (
    to_cytoscape_elements,
    network_page,
    load_graph,
)

SAMPLE_GRAPH = {
    "nodes": [
        {"id": 1, "name": "Lee Morgan", "era": 1956,
         "instrument": "trumpet", "degree": 2},
        {"id": 2, "name": "Art Blakey", "era": 1954,
         "instrument": "drums", "degree": 1},
        {"id": 3, "name": "Wayne Shorter", "era": 1959,
         "instrument": "saxophone", "degree": 1},
    ],
    "edges": [
        {"source": 1, "target": 2, "weight": 4,
         "sample_releases": ["The Sidewinder"]},
        {"source": 1, "target": 3, "weight": 2,
         "sample_releases": ["Search for the New Land"]},
    ],
}


class TestToCytoscapeElements:
    def test_returns_node_and_edge_dicts(self):
        elements = to_cytoscape_elements(SAMPLE_GRAPH)
        nodes = [e for e in elements if "source" not in e["data"]]
        edges = [e for e in elements if "source" in e["data"]]
        assert len(nodes) == 3
        assert len(edges) == 2

    def test_node_has_id_and_label(self):
        elements = to_cytoscape_elements(SAMPLE_GRAPH)
        node = next(
            e for e in elements if e["data"].get("id") == "1"
        )
        assert node["data"]["label"] == "Lee Morgan"

    def test_node_carries_degree_and_era(self):
        elements = to_cytoscape_elements(SAMPLE_GRAPH)
        node = next(e for e in elements if e["data"].get("id") == "1")
        assert node["data"]["degree"] == 2
        assert node["data"]["era"] == 1956

    def test_edge_has_source_target_weight(self):
        elements = to_cytoscape_elements(SAMPLE_GRAPH)
        edge = next(e for e in elements if "source" in e["data"])
        assert edge["data"]["source"] in {"1", "2", "3"}
        assert edge["data"]["target"] in {"1", "2", "3"}
        assert isinstance(edge["data"]["weight"], int)

    def test_empty_graph_yields_no_elements(self):
        assert to_cytoscape_elements({"nodes": [], "edges": []}) == []


class TestNetworkPage:
    def test_returns_component_with_cytoscape(self):
        page = network_page(SAMPLE_GRAPH)
        # The page is a Dash component tree; find the Cytoscape in it.
        assert _contains_type(page, cyto.Cytoscape)

    def test_renders_for_empty_graph(self):
        page = network_page({"nodes": [], "edges": []})
        assert page is not None


class TestLoadGraph:
    def test_falls_back_to_committed_json_when_db_empty(self, mocker):
        mocker.patch(
            "components.network.get_graph",
            return_value={"nodes": [], "edges": []},
        )
        graph = load_graph()
        # Committed graph.json must be non-empty so the demo is never bare.
        assert len(graph["nodes"]) > 0

    def test_uses_db_graph_when_present(self, mocker):
        mocker.patch(
            "components.network.get_graph",
            return_value=SAMPLE_GRAPH,
        )
        graph = load_graph()
        assert len(graph["nodes"]) == 3

    def test_falls_back_when_db_raises(self, mocker):
        mocker.patch(
            "components.network.get_graph",
            side_effect=RuntimeError("no DATABASE_URL"),
        )
        graph = load_graph()
        assert len(graph["nodes"]) > 0


class TestCommittedGraphJson:
    def test_graph_json_is_valid_and_nonempty(self):
        path = Path(__file__).parent.parent / "netviz" / "graph.json"
        data = json.loads(path.read_text())
        assert data["nodes"]
        assert data["edges"]


def _contains_type(component, target_type):
    if isinstance(component, target_type):
        return True
    children = getattr(component, "children", None)
    if children is None:
        return False
    if not isinstance(children, (list, tuple)):
        children = [children]
    return any(
        _contains_type(c, target_type)
        for c in children
        if hasattr(c, "children") or isinstance(c, target_type)
    )
