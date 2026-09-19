from components.editorial import listening_summary


def test_summary_counts_unique_genres(listening_artists):
    summary = listening_summary(listening_artists)
    assert summary.children[0].children[0].children == "03"
    assert summary.children[1].children[0].children == "02"
    assert summary.children[2].children[0].children == "art rock"


def test_summary_handles_empty_collection():
    summary = listening_summary([])
    assert summary.children[0].children[0].children == "00"
    assert summary.children[1].children[0].children == "00"
    assert summary.children[2].children[0].children == "Unclassified"
