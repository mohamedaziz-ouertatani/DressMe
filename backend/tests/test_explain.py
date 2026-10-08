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
    cuts = {"min_conf_" + f for f in explain.FIELDS} | {"margin"}
    assert cuts <= set(s)
    assert all(0 <= s[k] <= 1 for k in cuts)


@pytest.fixture(scope="module")
def untrained():
    return classifier.DressMeNet(pretrained=False).eval()


def noise(size, seed=0):
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))


def test_class_index():
    assert explain.class_index("pattern", "striped") == classifier.PATTERNS.index("striped")
    with pytest.raises(ValueError):
        explain.class_index("pattern", "polka")
    with pytest.raises(ValueError):
        explain.class_index("brand", "zara")


def test_letterbox_box():
    assert explain.letterbox_box(100, 200) == (56, 0, 168, 224)      # tall picture: white sides


def test_gradcam_shape_range_and_padding(untrained):
    img = noise((100, 200))
    heat = explain.gradcam(untrained, img, "category", 0, "cpu")
    assert heat.shape == (224, 224) and heat.dtype == np.float32
    assert heat.min() >= 0 and heat.max() <= 1
    assert heat[:, :56].max() == 0 and heat[:, 168:].max() == 0         # nothing on the padding
    other = explain.gradcam(untrained, img, "category", 1, "cpu")
    assert not np.allclose(heat, other)                                # another class, another map


def test_overlay_is_a_224_picture(untrained):
    img = noise((80, 80))
    out = explain.overlay(img, explain.gradcam(untrained, img, "pattern", 0, "cpu"))
    assert out.size == (224, 224) and out.mode == "RGB"


def hex_rgb(name):
    import pandas as pd
    pal = pd.read_csv(colour_utils.PALETTE_PATH, keep_default_na=False).set_index("colour")
    h = pal.loc[name, "hex"]
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def two_colour_piece():
    """A piece on white: left half black, right half navy."""
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    img.paste(Image.new("RGB", (50, 100), hex_rgb("black")), (50, 50))
    img.paste(Image.new("RGB", (50, 100), hex_rgb("navy")), (100, 50))
    return img


def test_colour_map_finds_half_the_piece():
    mask, share, reliable = explain.colour_map(two_colour_piece(), "black")
    assert mask.shape == (224, 224) and reliable
    assert 0.4 < share < 0.6
    assert mask[:, :100].sum() > mask[:, 124:].sum()                  # the black half is on the left


def test_colour_map_light_colours_are_not_reliable():
    _, _, reliable = explain.colour_map(two_colour_piece(), "white")
    assert not reliable


def test_colour_map_multicolour_and_unknown():
    mask, share, reliable = explain.colour_map(two_colour_piece(), "multicolour")   # no single hex
    assert mask.sum() == 0 and share == 0 and not reliable
    with pytest.raises(ValueError):
        explain.colour_map(two_colour_piece(), "rainbow")


def test_mask_overlay_size():
    mask, _, _ = explain.colour_map(two_colour_piece(), "navy")
    assert explain.mask_overlay(two_colour_piece(), mask).size == (224, 224)
