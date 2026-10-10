"""The team's rules per gender (compatibility.rules_for): gendered rows override the
neutral ones, the other gender's rows are ignored, and neutral rules = today's rules."""

import shutil
import sys

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import compatibility as C  # noqa: E402
import explain_similarity as S  # noqa: E402


def copy_mappings(tmp_path):
    folder = tmp_path / "mappings"
    shutil.copytree(C.MAP_DIR, folder)
    return folder


def add_row(path, line):
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(line + "\n")


def test_neutral_rules_are_the_default_rules():
    assert C.rules_for(None) is C.RULES
    assert C.rules_for("") is C.RULES
    assert C.rules_for("men") is C.rules_for("men")      # cached
    assert C.RULES.gender is None


def test_gendered_rows_override_neutral_ones(tmp_path):
    folder = copy_mappings(tmp_path)
    add_row(folder / "outfit_structure.csv", "accessory,extra,2,REVIEW test,men")
    add_row(folder / "compatibility_weights.csv", "good_outfit,70,REVIEW test,women")
    add_row(folder / "sub_category_pairing.csv", "shorts,blazer,0.1,REVIEW test,men")
    add_row(folder / "item_seasons.csv", "sub_category,skirt,summer,REVIEW test,women")
    men, women = C.Rules(folder, "men"), C.Rules(folder, "women")
    neutral = C.Rules(folder)
    assert men.max_items["accessory"] == 2 and women.max_items["accessory"] == 4
    assert women.settings["good_outfit"] == 70 and men.settings["good_outfit"] == 60
    assert men.sub_pairs[("blazer", "shorts")] == 0.1 and women.sub_pairs[("blazer", "shorts")] == 0.4
    assert women.default_seasons({"sub_category": "skirt"}) == {"summer"}
    assert men.default_seasons({"sub_category": "skirt"}) is None
    assert neutral.max_items == C.RULES.max_items and neutral.settings == C.RULES.settings


def test_reload_rules_refreshes_every_gender_in_place(tmp_path):
    folder = copy_mappings(tmp_path)
    men = C.rules_for("men")
    try:
        add_row(folder / "outfit_structure.csv", "accessory,extra,3,REVIEW test,men")
        C.reload_rules(folder)
        assert C.rules_for("men") is men and men.max_items["accessory"] == 3
    finally:
        C.reload_rules()
    assert C.rules_for("men").max_items["accessory"] == 4


def test_concepts_per_gender():
    neutral = {r["concept"]: r["prompt"] for r in S.load_concepts()}
    men = {r["concept"]: r["prompt"] for r in S.load_concepts(gender="men")}
    assert set(neutral) == set(men)                      # same concepts, one row each
    assert "menswear" in men["formal"] and "menswear" not in neutral["formal"]
    assert men["denim"] == neutral["denim"]
