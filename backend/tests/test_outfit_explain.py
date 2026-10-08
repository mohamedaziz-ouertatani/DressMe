"""Outfit score and buy-advice explanations (src/phase4/explain_outfit.py) and the
problem codes of the formula. Pure functions: no Mongo, no model."""

import sys

import numpy as np

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import compatibility as C  # noqa: E402
import explain_outfit as X  # noqa: E402


def vec(seed, base=3.0):
    v = np.random.default_rng(seed).normal(size=512) + base
    return (v / np.linalg.norm(v)).astype(np.float32)


def item(id, category, sub="", colour="", pattern="", seed=0):
    return {"id": id, "category": category, "sub_category": sub, "colour": colour,
            "pattern": pattern, "pattern_conf": 1.0, "vector": vec(seed)}


def codes(lines):
    return [(l["sign"], l["code"]) for l in lines]


def test_problems_mirror_the_english_reasons():
    outfit = [item("t", "top", "t-shirt", "red", "striped", 1), item("b", "bottom", "jeans", "orange", "floral", 2)]
    r = C.score_outfit(outfit)
    got = codes(r["problems"])
    assert ("-", "structure_no_shoes") in got
    assert ("-", "pattern_clash") in got
    clash = next(l for l in r["problems"] if l["code"] == "pattern_clash")
    assert set(clash["params"].values()) == {"striped", "floral"}
    assert "no shoes" in r["reasons"]                              # English reasons unchanged
    assert all(l["sign"] == "-" for l in r["problems"])


def test_incomplete_and_over_limit_codes():
    r = C.score_outfit([item("t", "top", "t-shirt", "black")])
    inc = next(l for l in r["problems"] if l["code"] == "structure_incomplete")
    assert inc["params"] == {"missing": "top_or_bottom"}
    r = C.score_outfit([item("s", "shoes", "sneakers"), item("s2", "shoes", "heels")])
    assert next(l for l in r["problems"] if l["code"] == "structure_incomplete")["params"] == {"missing": "main_piece"}
    over = [l for l in r["problems"] if l["code"] == "structure_over_limit"]
    assert over and over[0]["params"] == {"category": "shoes", "n": 2}


def test_style_helpers():
    a, b = item("a", "top", seed=1), item("b", "bottom", seed=1)      # same vector
    assert C.style_coherence([a, b], C.RULES) == 1.0
    assert C.style_coherence([a], C.RULES) is None
    assert C.rescale_style(C.RULES.settings["style_low"], C.RULES) == 0.0
    shirt = item("s", "top", pattern="striped")
    shoes = item("f", "shoes", pattern="striped")                     # shoes are not clothes here
    assert C.clothing_patterns([shirt, shoes], C.RULES) == ["striped"]


SETTINGS = {"strength_style": 0.7, "strength_colour_pair": 0.8, "near_miss": 5}


def test_contributions_add_up_and_rescale():
    result = {"score": 71.8, "parts": {"style": 0.8, "colour": 0.6, "pattern": None, "structure": 0.75}}
    w = {"style": 0.35, "colour": 0.30, "pattern": 0.15, "structure": 0.20}
    rows = {r["part"]: r for r in X.contributions(result, w)}
    assert round(sum(r["points"] for r in rows.values()), 1) == 71.8   # 71.76 exact
    assert rows["pattern"]["counted"] is False and rows["pattern"]["why_not"] == "no_patterns"
    assert rows["style"]["max_points"] == round(100 * 0.35 / 0.85, 1)     # rescaled without pattern
    w0 = {**w, "colour": 0.0}
    assert {r["part"]: r for r in X.contributions(result, w0)}["colour"]["why_not"] == "weight_zero"


def test_contributions_match_score_outfit():
    outfit = [item("t", "top", "t-shirt", "navy", "solid", 1), item("b", "bottom", "jeans", "white", "solid", 2),
              item("s", "shoes", "sneakers", "white", seed=3)]
    r = C.score_outfit(outfit)
    assert round(sum(x["points"] for x in X.contributions(r, C.RULES.weights)), 1) == r["score"]


def test_strengths():
    same = [item("t", "top", "t-shirt", "navy", "striped", 1), item("b", "bottom", "jeans", "white", "solid", 1),
            item("s", "shoes", "sneakers", "white", seed=1)]
    r = C.score_outfit(same)
    got = codes(X.strengths(same, r["parts"], C.RULES, SETTINGS))
    assert ("+", "style_coherent") in got                      # identical vectors
    assert ("+", "pattern_one_bold") in got and ("+", "structure_complete") in got
    assert all(sign == "+" for sign, _ in got)
    plain = [item("t", "top", "t-shirt", "", "solid", 1), item("b", "bottom", "jeans", "", "solid", 9)]
    got = codes(X.strengths(plain, C.score_outfit(plain)["parts"], C.RULES, SETTINGS))
    assert ("+", "pattern_calm") in got and ("+", "structure_complete") not in got


def test_settings_file_has_outfit_rows():
    import explain
    s = explain.load_settings()
    assert {"strength_style", "strength_colour_pair", "near_miss"} <= set(s)
