"""Public read-only API (Group YY, PRD Feature 4).

``/api/v1/*`` on Dash's Flask server: public-safe aggregates only,
never raw plays. GET only, JSON only, CORS open, cache headers, and a
simple in-memory per-IP rate limit. The hand-written OpenAPI 3.1 spec
(``api/openapi.json``) is served at ``/api/openapi.json`` and rendered
at ``/api/docs``; tests/test_public_api.py validates every response
against it.
"""
import html
import json
import logging
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

import db
import demo_data
from components.network import load_graph
from netviz.paths import describe_path, shortest_path

logger = logging.getLogger(__name__)

SPEC_PATH = Path(__file__).parent / "api" / "openapi.json"
RATE_LIMIT = 60  # requests per client IP per window
RATE_WINDOW = 60  # seconds
TIME_RANGES = ("short_term", "medium_term", "long_term")

api_bp = Blueprint("public_api", __name__, url_prefix="/api")


class RateLimiter:
    """Sliding-window counter per key, held in process memory.

    Each gunicorn worker keeps its own window, so the effective limit
    is per worker. That is enough for a personal project; a shared
    store would be the next step if it ever isn't.
    """

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> int | None:
        """Record a request; seconds to wait if over the limit, else None."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, int(hits[0] + self.window - now))
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter(RATE_LIMIT, RATE_WINDOW)


def _client_ip() -> str:
    """The last X-Forwarded-For hop (added by Railway's proxy).

    Earlier entries are whatever the client sent, so trusting them
    would let a caller pick a fresh IP per request.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    hops = [h.strip() for h in forwarded.split(",") if h.strip()]
    return hops[-1] if hops else (request.remote_addr or "unknown")


def _error(status: int, message: str) -> Response:
    resp = jsonify(error=message)
    resp.status_code = status
    return resp


@api_bp.before_request
def _rate_limit():
    retry = limiter.hit(_client_ip())
    if retry is not None:
        logger.info("rate limited %s on %s", _client_ip(), request.path)
        resp = _error(429, "rate limit exceeded; retry later")
        resp.headers["Retry-After"] = str(retry)
        return resp
    return None


@api_bp.after_request
def _headers(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    if resp.status_code == 200:
        resp.headers.setdefault("Cache-Control", "public, max-age=300")
    else:
        resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.get("/openapi.json")
def openapi_spec():
    return Response(SPEC_PATH.read_text(), mimetype="application/json")


@api_bp.get("/docs")
def docs():
    spec = json.loads(SPEC_PATH.read_text())
    esc = html.escape
    rows = []
    for path, item in spec["paths"].items():
        op = item["get"]
        params = "".join(
            f"<li><code>{esc(p['name'])}</code>"
            f"{' (required)' if p.get('required') else ''}: "
            f"{esc(p.get('description', ''))}</li>"
            for p in op.get("parameters", [])
        )
        codes = ", ".join(esc(c) for c in op["responses"])
        rows.append(
            f"<section><h2><code>GET {esc(path)}</code></h2>"
            f"<p><strong>{esc(op.get('summary', ''))}</strong></p>"
            f"<p>{esc(op.get('description', ''))}</p>"
            + (f"<ul>{params}</ul>" if params else "")
            + f"<p>Responses: {codes}</p></section>"
        )
    info = spec["info"]
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,"
        "initial-scale=1'>"
        f"<title>{esc(info['title'])}</title>"
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:46rem;"
        "margin:2rem auto;padding:0 1rem}code{background:#f2efe9;"
        "padding:0 .2em}section{border-top:1px solid #ddd}</style>"
        f"</head><body><h1>{esc(info['title'])} "
        f"<small>v{esc(info['version'])}</small></h1>"
        f"<p>{esc(info.get('description', ''))}</p>"
        "<p>Machine-readable spec: "
        "<a href='/api/openapi.json'>/api/openapi.json</a></p>"
        + "".join(rows)
        + "</body></html>"
    )
    return Response(page, mimetype="text/html")


@api_bp.get("/v1/network/graph")
def network_graph():
    graph = load_graph()
    resp = jsonify(nodes=graph["nodes"], edges=graph["edges"])
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@api_bp.get("/v1/network/path")
def network_path():
    a = request.args.get("from", "")
    b = request.args.get("to", "")
    if not a or not b:
        return _error(400, "both 'from' and 'to' are required")
    graph = load_graph()
    try:
        path = shortest_path(graph, a, b)
    except KeyError as exc:
        return _error(404, str(exc.args[0]))
    except ValueError as exc:
        return _error(400, str(exc))
    hops = describe_path(graph, path) if path else []
    resp = jsonify({"from": a, "to": b, "path": path, "hops": hops})
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


def _snapshot_json(snap: dict) -> dict:
    captured = snap["captured_at"]
    return {
        "captured_at": (
            captured.isoformat()
            if hasattr(captured, "isoformat") else str(captured)
        ),
        "artists": [
            {
                "rank": a["rank"],
                "name": a["name"],
                "artist_id": a.get("artist_id"),
                "genres": list(a.get("genres") or []),
            }
            for a in snap["artists"]
        ],
    }


@api_bp.get("/v1/trends/artists")
def artist_trends():
    time_range = request.args.get("time_range", "short_term")
    if time_range not in TIME_RANGES:
        return _error(
            400, f"time_range must be one of {', '.join(TIME_RANGES)}"
        )
    try:
        snapshots = db.get_snapshots(time_range)
    except Exception as exc:  # same fallback as the public Trends tab
        logger.warning("api trends load failed: %s", exc)
        snapshots = []
    source = "live"
    if len(snapshots) < 2:
        snapshots = demo_data.demo_snapshots(time_range)
        source = "demo"
    return jsonify(
        time_range=time_range,
        source=source,
        snapshots=[_snapshot_json(s) for s in snapshots],
    )


@api_bp.get("/v1/listening/hour-of-week")
def hour_of_week():
    # Real listening hours are owner-only (DECISIONS 2026-09-30), so the
    # public API serves the same sample data as the public Patterns tab.
    cells = demo_data.demo_patterns()["hour_of_week"]
    return jsonify(source="demo", hour_of_week=cells)
