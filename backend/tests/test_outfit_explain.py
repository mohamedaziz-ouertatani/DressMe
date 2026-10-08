"""Outfit score and buy-advice explanations (src/phase4/explain_outfit.py) and the
problem codes of the formula. Pure functions: no Mongo, no model."""

import sys

import numpy as np

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import compatibility as C  # noqa: E402


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
