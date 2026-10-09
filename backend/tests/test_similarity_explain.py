"""Why two pieces look alike (src/phase4/explain_similarity.py): shared labels and
the concepts the picture model associates with each piece. No model needed."""

import sys

import numpy as np

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import explain_similarity as S  # noqa: E402


def unit(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


CONCEPTS = {"denim": unit([1, 0, 0, 0]), "formal": unit([0, 1, 0, 0]),
            "sporty": unit([0, 0, 1, 0]), "lace": unit([0, 0, 0, 1])}


def test_concepts_file():
    rows = S.load_concepts()
    assert len(rows) >= 15 and len({r["concept"] for r in rows}) == len(rows)
    assert all(r["prompt"] and r["group"] in {"style", "material", "fit", "pattern", "other"} for r in rows)
    assert all(r["check"] == "" or "=" in r["check"] for r in rows)


def test_shared_attributes_skip_unknown_fields():
    a = {"category": "bottom", "sub_category": "jeans", "colour": "blue", "pattern": ""}
    b = {"category": "bottom", "sub_category": "jeans", "colour": "black", "pattern": "solid"}
    out = S.shared_attributes(a, b)
    assert out["shared"] == [{"field": "category", "value": "bottom"}, {"field": "sub_category", "value": "jeans"}]
    assert out["differs"] == [{"field": "colour", "a": "blue", "b": "black"}]      # pattern unknown on a


def test_top_concepts_and_overlap():
    va = unit([0.9, 0.5, 0.1, 0.0])          # denim, then formal
    vb = unit([0.8, 0.1, 0.6, 0.0])          # denim, then sporty
    assert S.top_concepts(va, CONCEPTS, k=2) == ["denim", "formal"]
    out = S.concept_overlap(va, vb, CONCEPTS, k=2)
    assert out["both"] == ["denim"]
    vc = unit([0.0, 1.0, 0.0, 0.2])          # formal
    vd = unit([0.0, 0.0, 1.0, 0.1])          # sporty
    contrast = S.concept_overlap(vc, vd, CONCEPTS, k=1)
    assert contrast["both"] == [] and contrast["contrast"] == {"a": "formal", "b": "sporty"}


def test_explain_pair_without_vectors():
    a = {"category": "top", "colour": "red"}
    out = S.explain_pair(a, dict(a), None, None, CONCEPTS)
    assert out["both"] == [] and out["contrast"] is None and out["shared"]
