"""Six-degrees path-finding over the musician network.

A path is the fewest-hop collaboration chain between two musicians.
Among equal-length chains we prefer the *strongest*: the greatest
weakest link (minimum edge weight), then the greatest total weight.
Node ids are normalized to strings (dropdown values are strings,
graph.json ids are ints).

The graph is small (~240 nodes), so this is plain BFS + two dynamic-
programming passes over the shortest-path DAG — no graph library.
"""

import logging
import random
from collections import deque

logger = logging.getLogger(__name__)


def _adjacency(graph: dict) -> dict[str, dict[str, int]]:
    """Undirected adjacency with the heaviest weight per node pair."""
    adj: dict[str, dict[str, int]] = {
        str(n["id"]): {} for n in graph.get("nodes", [])
    }
    for e in graph.get("edges", []):
        a, b = str(e["source"]), str(e["target"])
        w = e.get("weight", 1)
        adj.setdefault(a, {})
        adj.setdefault(b, {})
        adj[a][b] = max(adj[a].get(b, 0), w)
        adj[b][a] = max(adj[b].get(a, 0), w)
    return adj


def _bfs(adj: dict[str, dict[str, int]], start: str) -> dict[str, int]:
    dist = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in adj[node]:
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
    return dist


def shortest_path(graph: dict, a, b) -> list[str] | None:
    """Strongest fewest-hop chain from ``a`` to ``b``, or None.

    Raises KeyError for an unknown id and ValueError when a == b.
    """
    a, b = str(a), str(b)
    adj = _adjacency(graph)
    for node in (a, b):
        if node not in adj:
            raise KeyError(f"unknown musician id: {node}")
    if a == b:
        raise ValueError("start and end musician are the same")

    from_a = _bfs(adj, a)
    if b not in from_a:
        logger.info("no path between %s and %s", a, b)
        return None
    from_b = _bfs(adj, b)
    hops = from_a[b]

    # Nodes on some shortest path, in BFS order from a.
    on_path = sorted(
        (n for n in from_a if from_a[n] + from_b.get(n, hops + 1) == hops),
        key=lambda n: (from_a[n], n),
    )

    def preds(node: str):
        for u in sorted(adj[node]):
            if from_a.get(u) == from_a[node] - 1 and u in best_min:
                yield u, adj[node][u]

    # Pass 1: the best achievable weakest link into each node.
    best_min: dict[str, float] = {a: float("inf")}
    for node in on_path[1:]:
        best_min[node] = max(min(best_min[u], w) for u, w in preds(node))
    floor = best_min[b]

    # Pass 2: using only edges at least that strong, maximize total.
    # Ties go to the lowest predecessor id (sorted), so it's stable.
    best_sum: dict[str, int] = {a: 0}
    parent: dict[str, str] = {}
    for node in on_path[1:]:
        for u, w in preds(node):
            if w < floor or u not in best_sum:
                continue
            total = best_sum[u] + w
            if node not in best_sum or total > best_sum[node]:
                best_sum[node] = total
                parent[node] = u

    path = [b]
    while path[-1] != a:
        path.append(parent[path[-1]])
    path.reverse()
    logger.info(
        "path %s -> %s: %d hops, weakest link %s, total %s",
        a, b, hops, floor, best_sum[b],
    )
    return path


def describe_path(graph: dict, path: list[str]) -> list[dict]:
    """One dict per hop: names, one sample shared release, weight."""
    names = {str(n["id"]): n.get("name", str(n["id"]))
             for n in graph.get("nodes", [])}
    edges = {}
    for e in graph.get("edges", []):
        key = frozenset((str(e["source"]), str(e["target"])))
        edges[key] = e
    hops = []
    for u, v in zip(path, path[1:]):
        edge = edges[frozenset((u, v))]
        releases = edge.get("sample_releases") or []
        hops.append({
            "from": names[u],
            "to": names[v],
            "release": releases[0] if releases else None,
            "weight": edge.get("weight", 1),
        })
    return hops


def random_interesting_pair(
    graph: dict, rng: random.Random, min_hops: int = 3
) -> tuple[str, str] | None:
    """A random connected pair at least ``min_hops`` apart, or None."""
    adj = _adjacency(graph)
    sources = sorted(adj)
    rng.shuffle(sources)
    for src in sources:
        dist = _bfs(adj, src)
        far = sorted(n for n, d in dist.items() if d >= min_hops)
        if far:
            return src, rng.choice(far)
    return None
