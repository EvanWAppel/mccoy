from netviz import genre


class TestNormalizeStyle:
    def test_exact_match(self):
        assert genre.normalize_style("Hard Bop") == genre.HARD_BOP

    def test_case_and_hyphen_insensitive(self):
        assert genre.normalize_style("soul-jazz") == genre.SOUL_JAZZ
        assert genre.normalize_style("Post-Bop") == genre.POST_BOP
        assert genre.normalize_style("POST BOP") == genre.POST_BOP

    def test_free_jazz_variants_collapse(self):
        assert genre.normalize_style("Free Jazz") == genre.FREE
        assert genre.normalize_style("Avant-garde Jazz") == genre.FREE

    def test_latin_variants_collapse(self):
        assert genre.normalize_style("Latin Jazz") == genre.LATIN
        assert genre.normalize_style("Afro-Cuban Jazz") == genre.LATIN

    def test_bop_maps_to_bebop(self):
        assert genre.normalize_style("Bop") == genre.BEBOP

    def test_contemporary_jazz_maps_to_post_bop(self):
        assert genre.normalize_style("Contemporary Jazz") == genre.POST_BOP

    def test_unknown_style_is_other(self):
        assert genre.normalize_style("Big Band") == genre.OTHER
        assert genre.normalize_style("Fusion") == genre.OTHER

    def test_none_or_empty_is_other(self):
        assert genre.normalize_style(None) == genre.OTHER
        assert genre.normalize_style("") == genre.OTHER


class TestDominantGenre:
    def test_picks_most_common_bucket(self):
        styles = ["Hard Bop", "Hard Bop", "Modal"]
        assert genre.dominant_genre(styles) == genre.HARD_BOP

    def test_specific_beats_other_even_when_rarer(self):
        # Two "Other" styles, one Modal -> Modal still wins.
        styles = ["Big Band", "Fusion", "Modal"]
        assert genre.dominant_genre(styles) == genre.MODAL

    def test_all_other_returns_other(self):
        assert genre.dominant_genre(["Big Band", "Swing"]) == genre.OTHER

    def test_empty_or_none_returns_none(self):
        assert genre.dominant_genre([]) is None
        assert genre.dominant_genre(None) is None
