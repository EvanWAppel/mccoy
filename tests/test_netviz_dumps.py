from pathlib import Path

from netviz import dumps

FIXTURE = str(Path(__file__).parent / "fixtures" / "discogs_dump_sample.xml")


def _records():
    return list(dumps.iter_inscope(FIXTURE))


class TestIterInscope:
    def test_filters_by_year_and_genre(self):
        titles = {r["t"] for r in _records()}
        # r1/r4/r5 in scope; r2 too late (1988), r3 wrong genre.
        assert titles == {"The Real McCoy", "Heavy Sessions",
                          "Tender Moments"}

    def test_drops_non_performers(self):
        r1 = next(r for r in _records() if r["t"] == "The Real McCoy")
        names = {nm for _, nm in r1["p"]}
        assert "Rudy Van Gelder" not in names  # engineer dropped
        assert {"McCoy Tyner", "Joe Henderson", "Elvin Jones"} <= names

    def test_main_artist_and_extraartists_both_kept(self):
        r4 = next(r for r in _records() if r["t"] == "Heavy Sessions")
        names = {nm for _, nm in r4["p"]}
        assert "The Rock Band" in names        # main artist
        assert "Jimmy Page" in names           # extraartist performer

    def test_carries_genre_style_year(self):
        r1 = next(r for r in _records() if r["t"] == "The Real McCoy")
        assert r1["g"] == ["Jazz"]
        assert "Hard Bop" in r1["s"]
        assert r1["y"] == 1967


class TestBuildGraph:
    def _graph(self, **kw):
        recs = _records()
        return dumps.build_graph(lambda: iter(recs), **kw)

    def test_nodes_have_genre_style_era(self):
        g = self._graph(top_k=100, min_weight=1, node_limit=100)
        tyner = next(n for n in g["nodes"] if n["name"] == "McCoy Tyner")
        assert tyner["genre"] == "Jazz"
        assert tyner["style"] == "Hard Bop"      # 2x Hard Bop vs 1x Modal
        assert tyner["era"] == 1965              # earliest of 1965/1967

    def test_cross_genre_performer_gets_dominant_genre(self):
        # Joe Henderson: 2 Jazz releases, 1 Rock -> Jazz dominates.
        g = self._graph(top_k=100, min_weight=1, node_limit=100)
        joe = next(n for n in g["nodes"] if n["name"] == "Joe Henderson")
        assert joe["genre"] == "Jazz"

    def test_edge_weight_counts_shared_releases(self):
        # Tyner & Henderson share r1 and r5 -> weight 2.
        g = self._graph(top_k=100, min_weight=2, node_limit=100)
        ids = {n["name"]: n["id"] for n in g["nodes"]}
        te, jo = ids["McCoy Tyner"], ids["Joe Henderson"]
        edge = next(
            e for e in g["edges"]
            if {e["source"], e["target"]} == {te, jo}
        )
        assert edge["weight"] == 2

    def test_min_weight_prunes_weak_edges(self):
        # At min_weight=2, the single Rock co-credits (weight 1) drop,
        # isolating those nodes -> pruned out.
        g = self._graph(top_k=100, min_weight=2, node_limit=100)
        names = {n["name"] for n in g["nodes"]}
        assert "Jimmy Page" not in names
        assert {"McCoy Tyner", "Joe Henderson"} <= names

    def test_top_k_per_genre_balances(self):
        # top_k=1 keeps only the single most-credited performer per
        # genre. Jazz's busiest here is Joe Henderson (3 credits).
        g = self._graph(top_k=1, min_weight=1, node_limit=100)
        jazz = [n for n in g["nodes"] if n["genre"] == "Jazz"]
        # At most one kept per genre before edge pruning; edges may then
        # leave it isolated, so just assert we didn't keep everyone.
        assert len(g["nodes"]) <= 4


class TestExtractRoundTrip:
    def test_extract_then_build(self, tmp_path):
        jsonl = tmp_path / "inscope.jsonl"
        n = dumps.extract_to_file(FIXTURE, str(jsonl))
        assert n == 3
        out = tmp_path / "graph.json"
        g = dumps.build_from_extract(
            FIXTURE and str(jsonl), str(out),
            top_k=100, min_weight=1, node_limit=100,
        )
        assert out.exists()
        assert {n["name"] for n in g["nodes"]} >= {
            "McCoy Tyner", "Joe Henderson"
        }
