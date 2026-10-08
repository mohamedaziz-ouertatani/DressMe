"""The item-label explanations (src/phase4/explain.py) and the helpers they use:
top-3 answers of the classifier and colour model, Grad-CAM, colour map.
No trained model needed: Grad-CAM runs on an untrained network."""

import sys

import numpy as np
import pytest
from PIL import Image

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import classifier  # noqa: E402
import colour_utils  # noqa: E402
import estimate_colours  # noqa: E402
import explain  # noqa: E402


def probs_with(head_values):
    """Fake softmax output for one picture: 0.01 everywhere, then the given values."""
    probs = {h: np.full((1, len(c)), 0.01) for h, c in classifier.HEADS.items()}
    for head, values in head_values.items():
        for cls, p in values.items():
            probs[head][0, classifier.HEADS[head].index(cls)] = p
    return probs


def test_decode_returns_top3():
    probs = probs_with({"category": {"bottom": 0.6, "top": 0.3},
                        "sub_category": {"t-shirt": 0.9, "jeans": 0.5, "shorts": 0.3},
                        "pattern": {"solid": 0.7}})
    r = classifier.decode(probs)[0]
    assert [a["value"] for a in r["top3"]["category"][:2]] == ["bottom", "top"]
    subs = r["top3"]["sub_category"]
    # t-shirt is more probable but belongs to "top": only bottoms are offered
    assert subs[0]["value"] == "jeans" and subs[1]["value"] == "shorts"
    assert all(classifier.SUB_PARENT[a["value"]] == "bottom" for a in subs)
    assert subs[0]["conf"] == round(r["sub_category_conf"], 3)
    assert len(r["top3"]["pattern"]) == 3 and r["top3"]["pattern"][0]["value"] == "solid"


def test_item_pixels_mask_drops_the_white_background():
    px = np.full((20, 20, 3), 255)
    px[5:15, 5:15] = (10, 10, 120)
    px[8:12, 8:12] = 250                 # a white detail INSIDE the item stays
    mask = estimate_colours.item_pixels_mask(px)
    assert mask[5:15, 5:15].all() and mask.sum() == 100


def test_palette_nearest_index():
    pal = colour_utils.Palette()
    idx = pal.nearest_index(np.array([[0, 0, 0], [255, 255, 255]]))
    assert [pal.names[i] for i in idx] == ["black", "white"]


class FakeColourModel:
    classes_ = np.array(["black", "gold", "navy", "red"])

    def predict_proba(self, X):
        return np.array([[0.2, 0.5, 0.25, 0.05]] * len(X))


def test_predict_top_skips_metals_for_clothes():
    X = np.zeros((2, 3))
    top = estimate_colours.predict_top(FakeColourModel(), X, ["top", "bag"])
    assert [a["value"] for a in top[0]] == ["navy", "black", "red"]     # no gold on a top
    assert top[0][0]["conf"] == pytest.approx(0.25 / 0.5, abs=1e-3)
    assert top[1][0]["value"] == "gold"                                  # a bag can be gold
    # same best answer as predict()
    colour, conf = estimate_colours.predict(FakeColourModel(), X, ["top", "bag"])
    assert list(colour) == ["navy", "gold"]


SETTINGS = {"min_conf_category": 0.6, "min_conf_sub_category": 0.5, "min_conf_pattern": 0.6,
            "min_conf_colour": 0.7, "margin": 0.15}


def alts(*confs):
    return [{"value": f"c{i}", "conf": c} for i, c in enumerate(confs)]


def test_unsure_rule():
    assert not explain.is_unsure("category", alts(0.9, 0.05), SETTINGS)
    assert explain.is_unsure("category", alts(0.55, 0.3), SETTINGS)       # below the cut
    assert explain.is_unsure("category", alts(0.62, 0.5), SETTINGS)       # too close to the 2nd
    assert not explain.is_unsure("sub_category", alts(0.55, 0.1), SETTINGS)
    assert not explain.is_unsure("pattern", alts(0.8), SETTINGS)          # only one answer
    assert not explain.is_unsure("colour", [], SETTINGS)                  # old item, nothing known


def test_settings_file_has_every_cut():
    s = explain.load_settings()
    assert set(s) == {"min_conf_" + f for f in explain.FIELDS} | {"margin"}
    assert all(0 <= v <= 1 for v in s.values())
