"""
src/phase4/verdict.py: the confidence and the reason codes of "should I buy this?".

Pure functions, no database: each test builds a small wardrobe by hand, runs the REAL
compatibility.buy_advice and wardrobe_insights on it (the same two calls the route makes) and
hands both results to verdict.assess. The numbers of the team's file are passed in explicitly, so
a later edit of mappings/verdict_rules.csv cannot break these tests (one test reads the real file).
"""

import copy
import pickle

import numpy as np
import pytest

import compatibility as C
import verdict

RULES = C.rules_for("women")
SETTINGS = {"min_wardrobe_items": 8, "far_from_style_cut": 0.5, "budget_share": 0.3}


def piece(n, category, sub="", colour="black", **more):
    return {"id": f"p{n}", "category": category, "sub_category": sub, "colour": colour, "pattern": "solid",
            "pattern_conf": 1.0, "vector": None, "coverage": None, "season": set(), "usage": set(), **more}


def wardrobe(tops=0, bottoms=0, shoes=0):
    items = [piece(i, "top", f"top{i}") for i in range(tops)]
    items += [piece(100 + i, "bottom", f"bottom{i}") for i in range(bottoms)]
    items += [piece(200 + i, "shoes", f"shoes{i}") for i in range(shoes)]
    return items


FULL = wardrobe(tops=3, bottoms=3, shoes=2)        # 8 usable pieces: not a small wardrobe


def run(candidate, owned, profile=None, settings=SETTINGS):
    """What the route does: buy_advice + wardrobe_insights, then assess."""
    profile = profile or {}
    advice = C.buy_advice(candidate, owned, profile, RULES)
    insights = C.wardrobe_insights(owned, profile, RULES)
    return verdict.assess(advice, candidate, owned, profile, insights, RULES, settings)


def codes(result):
    return {c["code"]: c["params"] for c in result["codes"]}


def unit_vector(cos):
    """A unit vector whose cosine with e0 is `cos`."""
    v = np.zeros(512, np.float32)
    v[0], v[1] = cos, np.sqrt(1 - cos ** 2)
    return v


E0 = unit_vector(1.0)


# ---------------------------------------------------------------- a clean case
def test_nothing_to_say_is_high_confidence():
    result = run(piece(900, "top", "newtop"), FULL)
    assert result == {"confidence": "high", "codes": []}


# ---------------------------------------------------------------- small_wardrobe
def test_small_wardrobe_counts_the_pieces_and_gives_low_confidence():
    result = run(piece(900, "top", "newtop"), wardrobe(tops=1, bottoms=1, shoes=1))
    assert codes(result) == {"small_wardrobe": {"owned": 3, "minimum": 8}}
    assert result["confidence"] == "low"          # this code alone is enough for low (not "medium")


def test_usable_means_after_the_users_filters():
    owned = FULL[:6] + [piece(50, "top", "low1", coverage=1), piece(51, "top", "low2", coverage=1)]
    result = run(piece(900, "top", "newtop"), owned, {"min_coverage": 3})
    assert codes(result)["small_wardrobe"] == {"owned": 6, "minimum": 8}


def test_exactly_the_minimum_is_not_small():
    assert "small_wardrobe" not in codes(run(piece(900, "top", "newtop"), wardrobe(tops=4, bottoms=4)))


def test_the_default_minimum_comes_from_the_teams_file():
    owned = wardrobe(tops=1, bottoms=1)
    advice = C.buy_advice(piece(900, "top", "newtop"), owned, {}, RULES)
    result = verdict.assess(advice, piece(900, "top", "newtop"), owned, {}, C.wardrobe_insights(owned, {}, RULES), RULES)
    assert codes(result)["small_wardrobe"] == {"owned": 2, "minimum": int(verdict.load_rules()["min_wardrobe_items"])}


# ---------------------------------------------------------------- no_pairing_piece
@pytest.mark.parametrize("candidate, owned, slot", [
    (piece(900, "top", "newtop"), wardrobe(tops=8), "bottom"),           # a top with no bottoms
    (piece(900, "bottom", "newbottom"), wardrobe(bottoms=8), "top"),     # a bottom with no tops
    (piece(900, "shoes", "newshoes"), wardrobe(tops=8), "bottom"),       # shoes, but no outfit to wear them with
    (piece(900, "shoes", "newshoes"), wardrobe(bottoms=8), "top"),
])
def test_no_pairing_piece_names_what_is_missing(candidate, owned, slot):
    result = run(candidate, owned)
    assert codes(result)["no_pairing_piece"] == {"slot": slot}
    assert result["confidence"] == "medium"                              # one lowering code


def test_a_full_piece_needs_no_pairing():
    result = run(piece(900, "dress", "dress"), wardrobe(shoes=8))
    assert "no_pairing_piece" not in codes(result)


def test_a_piece_the_profile_removes_is_not_a_pairing_problem():
    # buy_advice says skip because of the user's modesty level: that is its own reason
    candidate = piece(900, "top", "newtop", coverage=1)
    result = run(candidate, wardrobe(tops=8), {"min_coverage": 4})
    assert "no_pairing_piece" not in codes(result)


# ---------------------------------------------------------------- guessed_field
def guess(conf, unsure):
    return {"value": "x", "conf": conf, "alternatives": [], "unsure": unsure}


def test_a_flagged_guess_the_user_did_not_correct_is_reported():
    candidate = piece(900, "top", "newtop", predicted={"colour": guess(0.55, True), "pattern": guess(0.95, False)},
                      corrected=[])
    result = run(candidate, FULL)
    assert codes(result) == {"guessed_field": {"field": "colour", "conf": 0.55}}
    assert result["confidence"] == "medium"


def test_a_corrected_guess_is_not_reported():
    candidate = piece(900, "top", "newtop", predicted={"colour": guess(0.55, True)}, corrected=["colour"])
    assert codes(run(candidate, FULL)) == {}


def test_a_scan_from_before_the_flag_existed_has_no_guessed_field():
    candidate = piece(900, "top", "newtop", predicted={"colour": {"value": "x", "conf": 0.3}}, corrected=[])
    assert codes(run(candidate, FULL)) == {}


def test_two_guessed_fields_give_low_confidence():
    candidate = piece(900, "top", "newtop", corrected=[],
                      predicted={"colour": guess(0.5, True), "sub_category": guess(0.4, True)})
    result = run(candidate, FULL)
    assert [c["params"]["field"] for c in result["codes"] if c["code"] == "guessed_field"] == ["sub_category", "colour"]
    assert result["confidence"] == "low"


# ---------------------------------------------------------------- fills_gap (reuses wardrobe_insights.missing)
def test_fills_gap_uses_what_wardrobe_insights_calls_missing():
    owned = wardrobe(tops=4, bottoms=4)                                   # no shoes
    assert C.wardrobe_insights(owned, {}, RULES)["missing"] == ["shoes"]
    result = run(piece(900, "shoes", "newshoes"), owned)
    assert codes(result) == {"fills_gap": {"slot": "shoes"}}
    assert result["confidence"] == "high"                                 # it only informs


def test_fills_gap_for_a_missing_bottom_and_for_a_missing_main_piece():
    assert codes(run(piece(900, "bottom", "newbottom"), wardrobe(tops=8)))["fills_gap"] == {"slot": "bottom"}
    assert codes(run(piece(900, "top", "newtop"), []))["fills_gap"] == {"slot": "main"}


def test_a_piece_that_fills_nothing_is_not_reported():
    assert "fills_gap" not in codes(run(piece(900, "top", "newtop"), wardrobe(tops=4, bottoms=4)))


# ---------------------------------------------------------------- far_from_style
def test_far_from_style_below_the_cut():
    result = run(piece(900, "top", "newtop", vector=unit_vector(0.3)), FULL, {"style_vector": E0})
    assert codes(result) == {"far_from_style": {"similarity": 0.3}}
    assert result["confidence"] == "high"                                 # it only informs


def test_close_to_the_style_or_exactly_on_the_cut_is_not_reported():
    assert codes(run(piece(900, "top", "newtop", vector=unit_vector(0.8)), FULL, {"style_vector": E0})) == {}
    assert codes(run(piece(900, "top", "newtop", vector=unit_vector(0.5)), FULL, {"style_vector": E0})) == {}


def test_no_taste_vector_means_no_far_from_style():
    assert codes(run(piece(900, "top", "newtop", vector=unit_vector(0.1)), FULL, {})) == {}
    assert codes(run(piece(900, "top", "newtop", vector=unit_vector(0.1)), FULL, {"style_vector": None})) == {}


def test_no_candidate_vector_means_no_far_from_style():
    assert codes(run(piece(900, "top", "newtop"), FULL, {"style_vector": E0})) == {}


# ---------------------------------------------------------------- over_budget
def test_over_budget_when_the_price_is_more_than_the_share_of_the_budget():
    result = run(piece(900, "top", "newtop", price_tnd=100.0), FULL, {"budget_tnd": 200.0})
    assert codes(result) == {"over_budget": {"price": 100.0, "budget": 200.0, "share": 0.5}}
    assert result["confidence"] == "high"                                 # it only informs


def test_a_price_within_the_share_is_not_reported():
    assert codes(run(piece(900, "top", "newtop", price_tnd=50.0), FULL, {"budget_tnd": 200.0})) == {}
    assert codes(run(piece(900, "top", "newtop", price_tnd=60.0), FULL, {"budget_tnd": 200.0})) == {}   # not MORE than 30 %


@pytest.mark.parametrize("price, profile", [
    (None, {"budget_tnd": 200.0}),            # no price
    (100.0, {}),                              # no budget
    (100.0, {"budget_tnd": None}),
    (None, {}),
])
def test_missing_price_or_budget_means_no_over_budget(price, profile):
    assert codes(run(piece(900, "top", "newtop", price_tnd=price), FULL, profile)) == {}


# ---------------------------------------------------------------- confidence
def test_informing_codes_never_lower_the_confidence():
    candidate = piece(900, "shoes", "newshoes", vector=unit_vector(0.1), price_tnd=500.0)
    result = run(candidate, wardrobe(tops=4, bottoms=4), {"style_vector": E0, "budget_tnd": 100.0})
    assert set(codes(result)) == {"fills_gap", "far_from_style", "over_budget"}
    assert result["confidence"] == "high"


@pytest.mark.parametrize("flagged, expected", [(0, "high"), (1, "medium"), (2, "low"), (3, "low")])
def test_confidence_follows_the_number_of_lowering_codes(flagged, expected):
    fields = ["colour", "pattern", "sub_category"][:flagged]
    candidate = piece(900, "top", "newtop", corrected=[], predicted={f: guess(0.5, True) for f in fields})
    assert run(candidate, FULL)["confidence"] == expected


# ---------------------------------------------------------------- it only reads
def test_assess_never_changes_what_it_is_given():
    candidate = piece(900, "top", "newtop", vector=unit_vector(0.1), price_tnd=500.0, corrected=[],
                      predicted={"colour": guess(0.5, True)})
    profile = {"style_vector": E0, "budget_tnd": 100.0, "min_coverage": 2}
    advice = C.buy_advice(candidate, FULL, profile, RULES)
    insights = C.wardrobe_insights(FULL, profile, RULES)
    before = [pickle.dumps(copy.deepcopy(x)) for x in (advice, candidate, FULL, profile, insights)]
    verdict.assess(advice, candidate, FULL, profile, insights, RULES, SETTINGS)
    after = [pickle.dumps(x) for x in (advice, candidate, FULL, profile, insights)]
    assert before == after
    # and the verdict is exactly what compatibility says on its own
    assert advice["verdict"] == C.buy_advice(candidate, FULL, profile, RULES)["verdict"]


# ---------------------------------------------------------------- the team's file
def test_the_rules_file_has_every_row_and_marks_it_review():
    import csv
    rules = verdict.load_rules()
    assert set(verdict.REQUIRED) <= set(rules) and all(v > 0 for v in rules.values())
    with open(verdict.RULES_CSV, encoding="utf-8", newline="") as f:
        notes = {r["name"]: r["note"] for r in csv.DictReader(f)}
    assert all(n.startswith("REVIEW") for n in notes.values()), "every row is an open team decision"


def test_a_rules_file_with_a_missing_row_is_refused(tmp_path):
    path = tmp_path / "verdict_rules.csv"
    path.write_text("name,value,note\nmin_wardrobe_items,8,REVIEW\n", encoding="utf-8")
    with pytest.raises(ValueError, match="far_from_style_cut"):
        verdict.load_rules(path)
