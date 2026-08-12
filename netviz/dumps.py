"""Build the multi-genre atlas from a Discogs monthly *releases* dump.

Two stages, deliberately split so the slow part runs once and the
tunable part re-runs in seconds:

  extract  — stream the ~10GB dump ONCE, keep only in-scope releases
             (year 1955-1975 and a scope genre), write a compact JSONL.
  build    — from that JSONL: tally credits, keep the top-K performers
             per genre (balanced), build co-credit edges, assign each a
             top-level genre + dominant style, cap to a readable core,
             and write graph.json.

The dump download is IP-throttled by data.discogs.com, so run `extract`
locally against a downloaded file (or the URL) — it is NOT a Railway
job. `build` needs no network and is safe to iterate on.

CLI:
  uv run python -m netviz.dumps extract <dump.xml.gz|url> data/inscope.jsonl
  uv run python -m netviz.dumps build   data/inscope.jsonl netviz/graph.json
"""

import gzip
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from netviz.ingest import cap_by_degree, prune_isolated

logger = logging.getLogger(__name__)

# Atlas scope (Evan, 2026-08-11): the connected classic-era core.
SCOPE_GENRES = ("Jazz", "Rock", "Blues", "Funk / Soul")
YEAR_LO, YEAR_HI = 1955, 1975

_HEADERS = {"User-Agent": "mccoy-netviz/0.1 (+appelew@gmail.com)"}

# Credit roles that are not performances (drop from the network).
_NON_PERFORMER = (
    "producer", "engineer", "design", "photography", "mastered",
    "recorded by", "mixed by", "artwork", "liner notes", "lacquer",
    "written-by", "composed by", "arranged by", "management", "compiled",
    "supervised", "coordinator", "layout", "illustration",
)


def _is_performer(role: str | None) -> bool:
    r = (role or "").lower()
    return not any(bad in r for bad in _NON_PERFORMER)


def _year(rel) -> int | None:
    for tag in ("released", "year"):
        el = rel.find(tag)
        if el is not None and el.text and el.text.strip()[:4].isdigit():
            return int(el.text.strip()[:4])
    return None


def _open_source(source: str):
    """Return a binary, gzip-decompressed stream for a URL or file path."""
    if source.startswith("http"):
        import requests

        for attempt in range(6):
            r = requests.get(
                source, stream=True, timeout=60, headers=_HEADERS
            )
            if r.status_code == 429:
                wait = 20 * (attempt + 1)
                logger.warning("429; backoff %ss [%d/6]", wait, attempt + 1)
                r.close()
                time.sleep(wait)
                continue
            r.raise_for_status()
            return gzip.GzipFile(fileobj=r.raw)
        raise RuntimeError("Discogs download still 429 after retries")
    if source.endswith(".gz"):
        return gzip.open(source, "rb")
    return open(source, "rb")


def iter_inscope(source: str):
    """Yield compact records for in-scope releases from a dump stream.

    Record: ``{"y": year, "g": [scope genres], "s": [styles],
    "p": [[artist_id, name], ...], "t": title}``. Performers are the
    main artists plus performing ``extraartists`` (engineers etc.
    dropped), deduped by artist id.
    """
    stream = _open_source(source)
    for _event, rel in ET.iterparse(stream, events=("end",)):
        if rel.tag != "release":
            continue
        yr = _year(rel)
        genres = {g.text for g in rel.findall("genres/genre") if g.text}
        hit = [g for g in SCOPE_GENRES if g in genres]
        if yr and YEAR_LO <= yr <= YEAR_HI and hit:
            performers = {}
            for a in rel.findall("artists/artist"):
                aid, nm = a.findtext("id"), a.findtext("name")
                if aid and nm:
                    performers[aid] = nm
            for a in rel.findall("extraartists/artist"):
                aid, nm = a.findtext("id"), a.findtext("name")
                if aid and nm and _is_performer(a.findtext("role")):
                    performers.setdefault(aid, nm)
            if performers:
                yield {
                    "y": yr,
                    "g": hit,
                    "s": [s.text for s in rel.findall("styles/style")
                          if s.text],
                    "p": [[aid, nm] for aid, nm in performers.items()],
                    "t": rel.findtext("title") or "",
                }
        rel.clear()


def extract_to_file(source: str, out_path: str) -> int:
    """Stream the dump once, writing in-scope records as JSONL. Returns
    the count. This is the slow, one-time, network-heavy stage."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for rec in iter_inscope(source):
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            n += 1
            if n % 50_000 == 0:
                logger.info("extracted %d in-scope releases", n)
    logger.info("extract complete: %d in-scope releases -> %s", n, out_path)
    return n


def _read_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def build_graph(
    records_factory,
    top_k: int = 500,
    min_weight: int = 2,
    node_limit: int = 700,
) -> dict:
    """Build the atlas graph from in-scope records.

    ``records_factory`` is a zero-arg callable returning a FRESH
    iterator each call (the records are streamed twice — once to tally,
    once to build edges — so a bare generator won't do).

    Keeps the ``top_k`` most-credited performers *per genre* (balanced),
    forms co-credit edges (weight = shared in-scope releases) at or above
    ``min_weight``, colors each node by its dominant top-level genre with
    a dominant style, then caps to ``node_limit`` by degree.
    """
    # Pass 1: tally per-performer genre/style counts, name, earliest year.
    gcount: dict[str, Counter] = defaultdict(Counter)
    scount: dict[str, Counter] = defaultdict(Counter)
    name: dict[str, str] = {}
    minyear: dict[str, int] = {}
    for rec in records_factory():
        for aid, nm in rec["p"]:
            name[aid] = nm
            for g in rec["g"]:
                gcount[aid][g] += 1
            for s in rec["s"]:
                scount[aid][s] += 1
            y = rec["y"]
            minyear[aid] = min(minyear.get(aid, y), y)

    # Top-K performers per genre -> keep-set (genre-balanced).
    per_genre: dict[str, list] = defaultdict(list)
    for aid, gc in gcount.items():
        for g, c in gc.items():
            per_genre[g].append((c, aid))
    keep: set[str] = set()
    for g, lst in per_genre.items():
        lst.sort(key=lambda t: (-t[0], t[1]))
        keep.update(aid for _, aid in lst[:top_k])

    idmap = {aid: i for i, aid in enumerate(sorted(keep), start=1)}
    nodes = [
        {
            "id": idmap[aid],
            "name": name[aid],
            "genre": gcount[aid].most_common(1)[0][0],
            "style": (scount[aid].most_common(1)[0][0]
                      if scount[aid] else None),
            "era": minyear[aid],
        }
        for aid in keep
    ]

    # Pass 2: co-credit edges among kept performers.
    weight: Counter = Counter()
    samples: dict[tuple, list] = defaultdict(list)
    for rec in records_factory():
        kept = sorted({idmap[aid] for aid, _ in rec["p"] if aid in keep})
        for a, b in combinations(kept, 2):
            weight[(a, b)] += 1
            if len(samples[(a, b)]) < 3:
                samples[(a, b)].append(rec["t"])
    edges = [
        {"source": a, "target": b, "weight": w,
         "sample_releases": samples[(a, b)]}
        for (a, b), w in weight.items()
        if w >= min_weight
    ]

    graph = cap_by_degree(prune_isolated({"nodes": nodes, "edges": edges}),
                          node_limit)
    # Set degree from the final edge set (drives node size in the UI).
    degree: Counter = Counter()
    for e in graph["edges"]:
        degree[e["source"]] += 1
        degree[e["target"]] += 1
    for n in graph["nodes"]:
        n["degree"] = degree.get(n["id"], 0)
    return graph


def build_from_extract(
    extract_path: str,
    out_json: str,
    top_k: int = 500,
    min_weight: int = 2,
    node_limit: int = 700,
) -> dict:
    graph = build_graph(
        lambda: _read_jsonl(extract_path), top_k, min_weight, node_limit
    )
    Path(out_json).write_text(json.dumps(graph, indent=2))
    logger.info(
        "wrote %s (%d nodes, %d edges)",
        out_json, len(graph["nodes"]), len(graph["edges"]),
    )
    return graph


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s"
    )
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) >= 3 and argv[0] == "extract":
        extract_to_file(argv[1], argv[2])
        return 0
    if len(argv) >= 3 and argv[0] == "build":
        build_from_extract(argv[1], argv[2])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
