"""Group YY — public read-only API (/api/v1/*) and its OpenAPI spec.

The blueprint is mounted on a bare Flask app here so the tests don't
need app.py's env (FLASK_SECRET_KEY, Spotify). Data sources are
patched; contract tests validate every response against
api/openapi.json.
"""
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from flask import Flask
from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

import public_api
from public_api import SPEC_PATH

SPEC = json.loads(SPEC_PATH.read_text())
_REGISTRY = Registry().with_resource(
    "urn:mccoy-openapi", DRAFT202012.create_resource(SPEC)
)

GRAPH = {
    "nodes": [
        {"id": 1, "name": "M1", "genre": "Jazz", "era": 1960, "degree": 1},
        {"id": 2, "name": "M2", "genre": "Jazz", "era": 1961, "degree": 2},
        {"id": 3, "name": "M3", "genre": None, "era": None, "degree": 1},
        {"id": 9, "name": "Loner", "genre": "Jazz", "era": 1970,
         "degree": 0},
    ],
    "edges": [
        {"source": 1, "target": 2, "weight": 3,
         "sample_releases": ["R12"]},
        {"source": 2, "target": 3, "weight": 1, "sample_releases": []},
    ],
}

SNAPSHOTS = [
    {
        "snapshot_id": i,
        "captured_at": datetime(2026, 9, i, tzinfo=timezone.utc),
        "time_range": "short_term",
        "artists": [
            {"rank": 1, "name": "A", "artist_id": "a",
             "image_url": "https://img/a", "genres": ["jazz"]},
        ],
    }
    for i in (1, 8)
]


def validate(response, path, status):
    """Validate a response body against the spec's schema for it."""
    op = SPEC["paths"][path]["get"]
    schema = op["responses"][str(status)]["content"][
        "application/json"]["schema"]
    wrapped = {"$ref": "urn:mccoy-openapi" + schema["$ref"]}
    Draft202012Validator(wrapped, registry=_REGISTRY).validate(
        response.get_json()
    )


@pytest.fixture(autouse=True)
def _reset_limiter():
    public_api.limiter.reset()
    yield
    public_api.limiter.reset()


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(public_api.api_bp)
    return app.test_client()


@pytest.fixture
def graph():
    with patch.object(public_api, "load_graph", return_value=GRAPH):
        yield


# --- spec -------------------------------------------------------------


class TestSpec:
    def test_is_openapi_31(self):
        assert SPEC["openapi"].startswith("3.1")

    def test_every_schema_is_valid_json_schema(self):
        for schema in SPEC["components"]["schemas"].values():
            Draft202012Validator.check_schema(schema)

    def test_spec_and_routes_agree(self, client):
        routes = {
            r.rule for r in client.application.url_map.iter_rules()
            if r.rule.startswith("/api/v1/")
        }
        assert routes == set(SPEC["paths"])

    def test_served_at_api_openapi_json(self, client):
        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        assert r.get_json() == SPEC
        assert r.headers["Access-Control-Allow-Origin"] == "*"


class TestDocsPage:
    def test_lists_every_endpoint(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200
        assert r.mimetype == "text/html"
        body = r.get_data(as_text=True)
        for path in SPEC["paths"]:
            assert path in body
        assert "/api/openapi.json" in body

    def test_escapes_spec_text(self, client):
        with patch.dict(SPEC["info"], {"title": "<script>x</script>"}):
            body = client.get("/api/docs").get_data(as_text=True)
        assert "<script>x</script>" not in body


# --- endpoints + contract ----------------------------------------------


class TestGraph:
    def test_returns_graph_matching_contract(self, client, graph):
        r = client.get("/api/v1/network/graph")
        assert r.status_code == 200
        validate(r, "/api/v1/network/graph", 200)
        assert {n["name"] for n in r.get_json()["nodes"]} >= {"M1", "M3"}

    def test_committed_graph_json_matches_contract(self, client):
        # the real fallback graph, not a fixture
        with patch("components.network.get_graph",
                   side_effect=RuntimeError("no db")):
            r = client.get("/api/v1/network/graph")
        assert r.status_code == 200
        validate(r, "/api/v1/network/graph", 200)


class TestPath:
    URL = "/api/v1/network/path"

    def test_finds_chain(self, client, graph):
        r = client.get(self.URL, query_string={"from": "1", "to": "3"})
        assert r.status_code == 200
        validate(r, self.URL, 200)
        body = r.get_json()
        assert body["path"] == ["1", "2", "3"]
        assert body["hops"][0] == {
            "from": "M1", "to": "M2", "release": "R12", "weight": 3,
        }
        assert body["hops"][1]["release"] is None

    def test_unconnected_is_null_path(self, client, graph):
        r = client.get(self.URL, query_string={"from": "1", "to": "9"})
        assert r.status_code == 200
        validate(r, self.URL, 200)
        assert r.get_json()["path"] is None
        assert r.get_json()["hops"] == []

    @pytest.mark.parametrize(
        "qs", [{}, {"from": "1"}, {"to": "1"}, {"from": "", "to": "2"},
               {"from": "2", "to": "2"}],
        ids=["none", "no-to", "no-from", "empty", "same"],
    )
    def test_bad_request(self, client, graph, qs):
        r = client.get(self.URL, query_string=qs)
        assert r.status_code == 400
        validate(r, self.URL, 400)

    def test_unknown_id_is_404(self, client, graph):
        r = client.get(self.URL, query_string={"from": "1", "to": "404"})
        assert r.status_code == 404
        validate(r, self.URL, 404)


class TestTrends:
    URL = "/api/v1/trends/artists"

    def test_live_snapshots(self, client):
        with patch.object(public_api.db, "get_snapshots",
                          return_value=SNAPSHOTS) as get:
            r = client.get(self.URL)
        get.assert_called_once_with("short_term")
        assert r.status_code == 200
        validate(r, self.URL, 200)
        body = r.get_json()
        assert body["source"] == "live"
        assert body["snapshots"][0]["captured_at"].startswith(
            "2026-09-01T")
        # image URLs are presentation, not part of the API
        assert "image_url" not in body["snapshots"][0]["artists"][0]

    def test_time_range_param(self, client):
        with patch.object(public_api.db, "get_snapshots",
                          return_value=SNAPSHOTS) as get:
            client.get(self.URL, query_string={"time_range": "long_term"})
        get.assert_called_once_with("long_term")

    def test_unknown_time_range_is_400(self, client):
        r = client.get(self.URL, query_string={"time_range": "forever"})
        assert r.status_code == 400
        validate(r, self.URL, 400)

    @pytest.mark.parametrize("live", [[], SNAPSHOTS[:1], None])
    def test_falls_back_to_demo(self, client, live):
        effect = RuntimeError("db down") if live is None else None
        with patch.object(public_api.db, "get_snapshots",
                          return_value=live, side_effect=effect):
            r = client.get(self.URL)
        assert r.status_code == 200
        validate(r, self.URL, 200)
        assert r.get_json()["source"] == "demo"
        assert len(r.get_json()["snapshots"]) >= 2


class TestHourOfWeek:
    URL = "/api/v1/listening/hour-of-week"

    def test_is_demo_only(self, client):
        with patch.object(public_api.db, "get_listening_patterns") as real:
            r = client.get(self.URL)
        real.assert_not_called()  # real hours are owner-only
        assert r.status_code == 200
        validate(r, self.URL, 200)
        assert r.get_json()["source"] == "demo"
        assert r.get_json()["hour_of_week"]


# --- HTTP rules -----------------------------------------------------------


class TestHttpRules:
    def test_cors_and_cache_headers(self, client, graph):
        r = client.get("/api/v1/network/graph")
        assert r.headers["Access-Control-Allow-Origin"] == "*"
        assert "public" in r.headers["Cache-Control"]
        assert "max-age=" in r.headers["Cache-Control"]
        assert r.mimetype == "application/json"

    def test_errors_are_not_cached(self, client, graph):
        r = client.get("/api/v1/network/path")
        assert r.headers["Cache-Control"] == "no-store"

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_get_only(self, client, graph, method):
        r = getattr(client, method)("/api/v1/network/graph")
        assert r.status_code == 405


class TestRateLimit:
    def test_429_with_retry_after_after_limit(self, client, graph):
        for _ in range(public_api.RATE_LIMIT):
            assert client.get("/api/v1/network/graph").status_code == 200
        r = client.get("/api/v1/network/graph")
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) >= 1
        assert r.headers["Access-Control-Allow-Origin"] == "*"
        validate(r, "/api/v1/network/graph", 429)

    def test_limit_is_per_ip(self, client, graph):
        for _ in range(public_api.RATE_LIMIT):
            client.get("/api/v1/network/graph")
        other = client.get(
            "/api/v1/network/graph",
            environ_overrides={"REMOTE_ADDR": "10.0.0.2"},
        )
        assert other.status_code == 200

    def test_uses_last_forwarded_hop(self, client, graph):
        # Railway's proxy appends the real client IP; earlier entries
        # are client-supplied and must not let a caller reset its quota.
        for i in range(public_api.RATE_LIMIT):
            client.get("/api/v1/network/graph", headers={
                "X-Forwarded-For": f"1.1.1.{i}, 203.0.113.7"})
        r = client.get("/api/v1/network/graph", headers={
            "X-Forwarded-For": "9.9.9.9, 203.0.113.7"})
        assert r.status_code == 429

    def test_window_slides(self):
        lim = public_api.RateLimiter(limit=2, window=60)
        assert lim.hit("ip", now=0) is None
        assert lim.hit("ip", now=1) is None
        assert lim.hit("ip", now=2) == 58
        assert lim.hit("ip", now=61) is None  # first hit expired


def test_mounted_on_the_dash_server(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test_secret")
    import app as app_module

    rules = {r.rule for r in app_module.server.url_map.iter_rules()}
    assert set(SPEC["paths"]) <= rules
    assert {"/api/openapi.json", "/api/docs"} <= rules
