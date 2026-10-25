"""The pure search logic (src/phase4/search.py): the words normaliser, the ranking, the two team tables."""

import numpy as np
import pytest

import search


@pytest.fixture(scope="module")
def terms():
    return search.load_terms()


def test_words_become_english_where_the_table_knows_them(terms):
    q = lambda text: search.normalise_query(text, terms)          # noqa: E731
    assert q("Black Jeans") == "a photo of black jeans"                   # English passes through
    assert q("pantalon noir") == "a photo of trousers black"             # French
    assert q("sac à main") == "a photo of handbag"                        # three words, one handbag
    assert q("le sac à main noir") == "a photo of handbag black"          # "le" is dropped
    assert q("a black dress") == "a photo of black dress"
    assert q("جينز أسود") == "a photo of jeans black"                     # Arabic
    assert q("الفستان الأحمر") == "a photo of dress red"                  # Arabic "the" glued to the word
    assert q("فُسْتَان") == "a photo of dress"                            # with Arabic vowel marks


def test_an_unknown_word_is_kept_and_a_query_is_never_emptied_by_articles(terms):
    assert search.normalise_query("zorglub shirt", terms) == "a photo of zorglub shirt"
    assert search.normalise_query("the", terms) == "a photo of the"
    assert search.normalise_query("  ,, ", terms) == ""                   # no words at all


def test_rank_owned_orders_by_cosine_and_marks_the_close_ones():
    items = [{"id": "far", "vector": [0, 1, 0]},
             {"id": "same", "vector": [3, 0, 0]},                        # same direction, a longer vector
             {"id": "near", "vector": [0.8, 0.6, 0]}]
    out = search.rank_owned([1, 0, 0], items, cut=0.9, limit=2)
    assert [r["item"]["id"] for r in out["results"]] == ["same", "near"]
    assert [round(r["similarity"], 2) for r in out["results"]] == [1.0, 0.8]
    assert [r["close"] for r in out["results"]] == [True, False]
    assert out["nothing_close"] is False and out["skipped_no_vector"] == 0
    assert search.rank_owned([1, 0, 0], items, cut=1.1, limit=8)["nothing_close"] is True


def test_rank_owned_skips_pieces_without_a_vector_and_copes_with_an_empty_wardrobe():
    items = [{"id": "a", "vector": None}, {"id": "b", "vector": np.zeros(3)}, {"id": "c", "vector": [1, 0, 0]}]
    out = search.rank_owned([1, 0, 0], items, cut=0.5, limit=8)
    assert [r["item"]["id"] for r in out["results"]] == ["c"] and out["skipped_no_vector"] == 2
    empty = search.rank_owned([1, 0, 0], [], cut=0.5, limit=8)
    assert empty == {"results": [], "nothing_close": True, "skipped_no_vector": 0}


def test_the_terms_table_stops_on_a_bad_row(tmp_path):
    def table(*rows):
        path = tmp_path / "terms.csv"
        path.write_text("term,lang,en,note\n" + "\n".join(rows) + "\n", encoding="utf-8")
        return path
    assert search.load_terms(table("robe,fr,dress,", "Robé,fr,dress,")) == {"robe": "dress"}       # same meaning twice is fine
    with pytest.raises(ValueError, match="already means"):
        search.load_terms(table("robe,fr,dress,", "robe,fr,gown,"))
    with pytest.raises(ValueError, match="lang must be fr or ar"):
        search.load_terms(table("robe,de,dress,"))
    with pytest.raises(ValueError, match="both needed"):
        search.load_terms(table("robe,fr,,"))


def test_the_team_tables_are_complete():
    rules = search.load_rules()
    assert 0 < rules["text_cut"] < 1 and 0 < rules["photo_cut"] < 1 and 0 < rules["target_precision"] <= 1
    assert rules["default_limit"] >= 1 and rules["closest_anyway"] >= 1 and rules["wardrobe_size"] >= 2
    terms = search.load_terms()
    assert terms["pantalon"] == "trousers" and terms["فستان"] == "dress"
