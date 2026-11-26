"""API quickstart notebook (YY-06).

The notebook calls the live public API by default. Here every
`requests.get` is routed into the API blueprint's Flask test client,
with a small fixture graph and no database (so trends fall back to
demo data). The notebook is committed without outputs, so live data
never lands in git.
"""

import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
import requests
from flask import Flask

import public_api

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "examples" / "api_quickstart.ipynb"
LIVE = "https://web-production-bee9a.up.railway.app"

GRAPH = {
    "nodes": [
        {"id": 1, "name": "M1", "genre": "Jazz", "era": 1960, "degree": 1},
        {"id": 2, "name": "M2", "genre": "Jazz", "era": 1961, "degree": 2},
        {"id": 3, "name": "M3", "genre": None, "era": None, "degree": 1},
    ],
    "edges": [
        {"source": 1, "target": 2, "weight": 3,
         "sample_releases": ["R12"]},
        {"source": 2, "target": 3, "weight": 1,
         "sample_releases": ["R23"]},
    ],
}


def _notebook():
    return json.loads(NOTEBOOK.read_text())


def _source(cell):
    src = cell["source"]
    return "".join(src) if isinstance(src, list) else src


def _code():
    return [
        _source(c) for c in _notebook()["cells"]
        if c["cell_type"] == "code"
    ]


def test_valid_nbformat_4():
    nb = _notebook()
    assert nb["nbformat"] == 4
    assert all(c["cell_type"] in {"markdown", "code"} for c in nb["cells"])


def test_committed_without_outputs():
    for cell in _notebook()["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


def test_defaults_to_the_live_api_but_is_overridable():
    code = "\n".join(_code())
    assert LIVE in code
    assert 'os.environ.get(' in code and '"MCCOY_API"' in code


def test_calls_every_documented_endpoint():
    code = "\n".join(_code())
    spec = json.loads(public_api.SPEC_PATH.read_text())
    for path in spec["paths"]:
        assert f'"{path}"' in code, path


@pytest.fixture
def routed(monkeypatch):
    """Route requests.get into the API blueprint; record each call."""
    public_api.limiter.reset()
    app = Flask(__name__)
    app.register_blueprint(public_api.api_bp)
    client = app.test_client()
    calls = []

    class Resp:
        def __init__(self, r):
            self.status_code = r.status_code
            self._r = r
            self.headers = dict(r.headers)

        def json(self):
            return self._r.get_json()

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code}")

    def fake_get(url, params=None, timeout=None):
        parts = urlsplit(url)
        assert f"{parts.scheme}://{parts.netloc}" == LIVE
        assert timeout, "always pass a timeout"
        calls.append((parts.path, params))
        return Resp(client.get(parts.path, query_string=params or {}))

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.delenv("MCCOY_API", raising=False)
    with patch.object(public_api, "load_graph", return_value=GRAPH), \
            patch.object(public_api.db, "get_snapshots",
                         side_effect=RuntimeError("no db")):
        yield calls
    public_api.limiter.reset()


def test_runs_end_to_end(routed, monkeypatch):
    import plotly.basedatatypes

    shown = []
    monkeypatch.setattr(
        plotly.basedatatypes.BaseFigure,
        "show",
        lambda self, *a, **k: shown.append(self),
    )
    namespace = {"display": print}
    for src in _code():
        exec(compile(src, str(NOTEBOOK), "exec"), namespace)
    paths = {p for p, _ in routed}
    spec = json.loads(public_api.SPEC_PATH.read_text())
    assert set(spec["paths"]) <= paths
    assert namespace["trends"]["source"] == "demo"
    assert namespace["route"]["path"]
    assert len(shown) >= 2
