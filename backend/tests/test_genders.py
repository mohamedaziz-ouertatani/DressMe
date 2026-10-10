"""Item gender (src/phase4/genders.py): own label first, then the team table, then unisex;
and the merge of gendered rule rows over neutral ones."""

import sys

import pandas as pd

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import genders as G  # noqa: E402
from item_images import ROOT  # noqa: E402


def test_normalise_any_source_spelling():
    assert G.normalise("Men") == G.normalise("homme") == G.normalise("MAN") == "men"
    assert G.normalise("Women") == G.normalise("femme") == "women"
    assert G.normalise("Unisex") == "unisex"
    assert G.normalise("Boys") == G.normalise("Girls") == G.normalise("") == G.normalise(None) == ""


def test_table_covers_exactly_the_vocabulary():
    vocab = pd.read_csv(ROOT / "mappings" / "sub_category_vocabulary.csv", dtype=str)
    table = G.load_table()
    assert set(table) == set(vocab["sub_category"])
    assert set(table.values()) <= set(G.VALUES)


def test_item_gender_label_beats_table_beats_default():
    assert G.item_gender({"gender": "Men", "sub_category": "skirt"}) == "men"
    assert G.item_gender({"gender": "", "sub_category": "skirt"}) == "women"
    assert G.item_gender({"sub_category": "tie"}) == "men"
    assert G.item_gender({"sub_category": "jeans"}) == "unisex"
    assert G.item_gender({"sub_category": ""}) == "unisex"
    assert G.item_gender({}) == "unisex"


def test_item_genders_vectorised_matches_item_gender():
    labels = pd.Series(["Women", "", "", "Boys"])
    subs = pd.Series(["tie", "tie", "jeans", "heels"])
    assert G.item_genders(labels, subs).tolist() == ["women", "men", "unisex", "women"]


def test_shown():
    assert G.shown("men") == {"men", "unisex"}
    assert G.shown(None) is None and G.shown("") is None


def test_for_gender_overrides_neutral_rows_and_ignores_the_other_gender():
    t = pd.DataFrame({"category": ["top", "accessory", "accessory", "accessory"],
                      "max_items": ["1", "4", "2", "6"], "gender": ["", "", "men", "women"]})
    key = lambda r: r.category
    men = G.for_gender(t, "men", key).set_index("category")["max_items"].to_dict()
    women = G.for_gender(t, "women", key).set_index("category")["max_items"].to_dict()
    neutral = G.for_gender(t, None, key).set_index("category")["max_items"].to_dict()
    assert men == {"top": "1", "accessory": "2"}
    assert women == {"top": "1", "accessory": "6"}
    assert neutral == {"top": "1", "accessory": "4"}


def test_for_gender_without_the_column_keeps_everything():
    t = pd.DataFrame({"name": ["a", "b"], "value": ["1", "2"]})
    assert G.for_gender(t, "men", lambda r: r.name).equals(t)


def test_for_gender_unordered_pair_key():
    t = pd.DataFrame({"a": ["shorts", "blazer"], "b": ["blazer", "shorts"],
                      "score": ["0.4", "0.1"], "gender": ["", "men"]})
    out = G.for_gender(t, "men", lambda r: frozenset((r.a, r.b)))
    assert out["score"].tolist() == ["0.1"]
