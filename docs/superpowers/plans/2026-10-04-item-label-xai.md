# Item-label XAI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain the classifier's and colour model's labels to users (Grad-CAM heatmap, colour pixel map, top-3 alternatives, "unsure" flag) and measure the explanations offline.

**Architecture:** Pure explanation functions live in `src/phase4/explain.py` (shared by the API and the evaluation script). The free extras (top 3, unsure) are added at analysis time and stored in `predicted`; the heatmaps are computed on demand by `Analyzer.explain` behind `GET /items/{id}/explain` and `GET /candidates/{id}/explain`. The React app shows them in a new `ExplainPanel`.

**Tech Stack:** PyTorch (EfficientNet-B0 already trained), numpy / PIL / scipy, FastAPI + pymongo, React + TypeScript + Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-04-item-label-xai-design.md`

## Global Constraints

- No new Python or npm dependency.
- Never change or retrain a model; never change the colour model's features (`product_features` must give identical numbers).
- Team-owned thresholds live in `mappings/xai_settings.csv`, every row marked `REVIEW` in its note; code never hard-codes them.
- Privacy: every endpoint goes through `own_item` (another user's item answers 404). Nothing new is stored except `alternatives` / `unsure` inside `predicted`.
- Readers of `predicted` must accept old documents without `alternatives` / `unsure` (use `.get`).
- Keep code simple and commented (mixed-experience team); match the surrounding style.
- Commits: no Co-Authored-By trailer and no "Generated with Claude Code" footer (user preference).
- Backend tests run from `backend/`: `python -m pytest` (MongoDB must be running). Runs longer than 10 min go in a separate process writing a log.

## Deviations from the spec (decided while planning)

- The colour map's item area reuses the colour model's own background rule (near-white regions touching the border, `WHITE = 235`) instead of "ΔE 6 from white": same pixels the model reads, and no second rule to maintain.
- The heatmap overlay uses a yellow → red ramp whose opacity follows the heat (cold areas show the plain photo) instead of jet at 45%: easier to read on product shots.
- `Analyzer.explain` returns PIL images; the router turns them into data URLs with the existing `as_data_url` from `routers/tryon.py`.
- No `note` field and no 503 in the response: the app writes its own translated text, and the Analyzer is always loaded (no other model endpoint answers 503).
- For EfficientNet + one linear layer per head, Grad-CAM equals the classic CAM, so the gradient only goes through the head (the body runs once, no backward through it). The code says so.

## File structure

| File | Change | Responsibility |
|---|---|---|
| `src/phase4/classifier.py` | modify | `decode` also returns `top3` per head |
| `src/phase3/colour_utils.py` | modify | `Palette.nearest_index` (vectorised nearest colour) |
| `src/phase3/estimate_colours.py` | modify | extract `item_pixels_mask`, add `predict_top` |
| `src/phase4/explain.py` | create | settings + unsure rule, Grad-CAM, colour map, overlays |
| `mappings/xai_settings.csv` | create | team thresholds (REVIEW) |
| `backend/app/ml.py` | modify | alternatives + unsure in `analyze`, new `explain`, `unsure` helper |
| `backend/app/routers/items.py` | modify | `load_photo` shared by image and explain routes |
| `backend/app/routers/explain.py` | create | the two `/explain` endpoints |
| `backend/app/main.py` | modify | include the router |
| `backend/tests/conftest.py` | modify | `FakeAnalyzer.explain` |
| `backend/tests/test_explain.py` | create | unit tests of `src/phase4/explain.py` + decode + colour helpers |
| `backend/tests/test_explain_api.py` | create | API tests |
| `backend/tests/test_real_models.py` | modify | one real end-to-end explain |
| `frontend/src/api/types.ts`, `api/client.ts` | modify | types + `api.explain` |
| `frontend/src/ui/ExplainPanel.tsx` | create | the "why" panel |
| `frontend/src/ui/Field.tsx` | modify | "not sure, check" badge |
| `frontend/src/pages/ScanPage.tsx`, `WardrobePage.tsx` | modify | "Why these labels?" toggle |
| `frontend/src/i18n/strings.ts` | modify | en / fr / ar strings |
| `src/phase4/evaluate_explanations.py` | create | report + figure |
| `reports/phase4/explanations_evaluation.md`, `reports/phase4/figures/gradcam_examples.png` | generated | |
| `CLAUDE.md`, the spec | modify | documentation |

---

### Task 1: Top-3 alternatives from the classifier and the colour model

**Files:**
- Modify: `src/phase4/classifier.py` (function `decode`, ~line 117)
- Modify: `src/phase3/colour_utils.py` (class `Palette`)
- Modify: `src/phase3/estimate_colours.py` (`product_features` ~line 90, `predict` ~line 231)
- Create: `backend/tests/test_explain.py`

**Interfaces:**
- Produces: `classifier.decode(probs)[i]["top3"] -> {"category": [{"value": str, "conf": float}, ...], "sub_category": [...], "pattern": [...]}` (sub_category list only holds children of the predicted category; conf rounded to 3 decimals).
- Produces: `estimate_colours.item_pixels_mask(px: np.ndarray HxWx3 int) -> np.ndarray HxW bool` (True = item pixel).
- Produces: `estimate_colours.predict_top(clf, X, categories, k=3) -> list[list[{"value": str, "conf": float}]]` (one list per row, best first, zero-probability colours left out).
- Produces: `colour_utils.Palette.nearest_index(rgb: np.ndarray Nx3) -> np.ndarray N int` (index into `Palette.names`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_explain.py`:

```python
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
```

- [ ] **Step 2: Run the tests to see them fail**

Run (from `backend/`): `python -m pytest tests/test_explain.py -v`
Expected: FAIL — `KeyError: 'top3'`, `AttributeError: ... item_pixels_mask`, `nearest_index`, `predict_top`.

- [ ] **Step 3: Implement `top3` in `src/phase4/classifier.py`**

Add above `decode`:

```python
def top_k(p, classes, k=3):
    """The k most probable classes of one probability row, best first."""
    order = np.argsort(p)[::-1][:k]
    return [{"value": classes[i], "conf": round(float(p[i]), 3)} for i in order]
```

In `decode`, after `pat = ...`, compute the renormalised sub_category row and add `top3` to the dict:

```python
        sub_norm = sub_p / max(sub_p.sum(), 1e-9)
        sub_top = [a for a in top_k(sub_norm, SUB_CATEGORIES)
                   if SUB_PARENT[a["value"]] == CATEGORIES[cat]]     # a category may have < 3 children
        results.append({
            ...existing keys unchanged...,
            "top3": {"category": top_k(probs["category"][i], CATEGORIES),
                     "sub_category": sub_top,
                     "pattern": top_k(probs["pattern"][i], PATTERNS)},
        })
```

Also add `"top3"` to the example in the module docstring (line ~12).

- [ ] **Step 4: Implement `Palette.nearest_index` in `src/phase3/colour_utils.py`**

```python
    def nearest_index(self, rgb):
        """Index (in self.names) of the closest palette colour, for many RGB colours (N x 3)."""
        lab = rgb_to_lab(np.asarray(rgb).reshape(-1, 3))
        dist = np.linalg.norm(lab[:, None, :] - self.lab[None, :, :], axis=2)
        return dist.argmin(axis=1)
```

- [ ] **Step 5: Extract `item_pixels_mask` and add `predict_top` in `src/phase3/estimate_colours.py`**

Replace the background lines of `product_features` with a call to a new function (the result must be identical):

```python
def item_pixels_mask(px):
    """True for the item's pixels of a product shot on white (H x W x 3, 0-255).
    Background = near-white regions touching the border, so white parts INSIDE
    the item (e.g. a white shirt with a dark outline) are kept."""
    near_white = (px > WHITE).all(axis=2)
    regions, _ = ndimage.label(near_white)
    border = np.unique(np.concatenate([regions[0], regions[-1], regions[:, 0], regions[:, -1]]))
    return ~np.isin(regions, border[border > 0])


def product_features(path):
    """Product shot on white: drop the white background, keep the item."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((THUMB, THUMB))
    px = np.asarray(img).astype(int)
    item = px[item_pixels_mask(px)]
    if len(item) < 30:  # nothing left: the item itself is white-ish
        item = px.reshape(-1, 3)
    return features(item)
```

Split `predict` so `predict_top` shares the metal rule:

```python
def probabilities(clf, X, categories):
    """Colour probabilities per row; metallic colours are skipped for clothes."""
    proba = clf.predict_proba(X)
    classes = np.array(clf.classes_)
    no_metal = np.isin(np.asarray(categories), list(METAL_FREE))
    proba[np.ix_(no_metal, np.isin(classes, list(METALS)))] = 0
    return classes, proba / proba.sum(axis=1, keepdims=True)


def predict(clf, X, categories):
    """Best colour per row; metallic colours are skipped for clothes."""
    classes, proba = probabilities(clf, X, categories)
    best = proba.argmax(axis=1)
    return classes[best], proba[np.arange(len(best)), best]


def predict_top(clf, X, categories, k=3):
    """The k most probable colours per row (best first), for the app's "why" panel."""
    classes, proba = probabilities(clf, X, categories)
    return [[{"value": str(classes[i]), "conf": round(float(row[i]), 3)}
             for i in np.argsort(row)[::-1][:k] if row[i] > 0] for row in proba]
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `python -m pytest tests/test_explain.py -v`
Expected: 5 passed.

- [ ] **Step 7: Check the colour features did not change**

Run (from the repo root):
```bash
python -c "import sys; sys.path[:0]=['src/common','src/phase3','src/phase4']; import estimate_colours as E, glob; p=sorted(glob.glob('data/raw/FashionProduct/images/*.jpg'))[:50]; import numpy as np, hashlib; print(hashlib.md5(np.stack([E.product_features(x) for x in p]).tobytes()).hexdigest())"
```
Run it once on the stashed old code (`git stash`, run, `git stash pop`) and once on the new code. Expected: the same hash.

- [ ] **Step 8: Commit**

```bash
git add src/phase4/classifier.py src/phase3/colour_utils.py src/phase3/estimate_colours.py backend/tests/test_explain.py
git commit -m "XAI: top-3 answers from the classifier and the colour model"
```

---

### Task 2: Unsure rule + team settings file

**Files:**
- Create: `mappings/xai_settings.csv`
- Create: `src/phase4/explain.py`
- Modify: `backend/tests/test_explain.py`

**Interfaces:**
- Produces: `explain.load_settings(path=SETTINGS_PATH) -> dict[str, float]` (keys `min_conf_category`, `min_conf_sub_category`, `min_conf_pattern`, `min_conf_colour`, `margin`).
- Produces: `explain.is_unsure(field: str, alternatives: list[{"value","conf"}], settings: dict) -> bool` (False when `alternatives` is empty).
- Produces: `explain.FIELDS = ["category", "sub_category", "pattern", "colour"]`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_explain.py`; add `import explain  # noqa: E402` next to the other src imports)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_explain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'explain'`.

- [ ] **Step 3: Create `mappings/xai_settings.csv`**

```csv
setting,value,note
min_conf_category,0.6,REVIEW: start value; below it the app says "not sure, check" (see reports/phase4/explanations_evaluation.md)
min_conf_sub_category,0.5,REVIEW: start value; sub_category has many close classes
min_conf_pattern,0.6,REVIEW: start value
min_conf_colour,0.7,REVIEW: same as MIN_CONFIDENCE in estimate_colours.py (the empty-colour rule does not change)
margin,0.15,REVIEW: also unsure when the best answer leads the second by less than this
```

- [ ] **Step 4: Create `src/phase4/explain.py` with the rule**

```python
"""
Explanations of the item labels (XAI), shared by the API and
src/phase4/evaluate_explanations.py:

    is_unsure(field, alternatives, settings) -> should the app ask the user to check?
    gradcam(model, img, head, class_idx, device) -> 224 x 224 map: where the classifier looked
    colour_map(img, colour)    -> the item pixels that look like that colour
    overlay(img, heat), mask_overlay(img, mask) -> pictures for the app

The thresholds of the unsure rule are the TEAM's (mappings/xai_settings.csv).
torch is imported inside gradcam only, so the light parts load without it.
"""

import numpy as np
import pandas as pd

from item_images import ROOT

SETTINGS_PATH = ROOT / "mappings" / "xai_settings.csv"
FIELDS = ["category", "sub_category", "pattern", "colour"]


def load_settings(path=SETTINGS_PATH):
    """{setting: value} from the team's file (read each time: edits apply at once)."""
    df = pd.read_csv(path, keep_default_na=False)
    return {r.setting: float(r.value) for r in df.itertuples()}


def is_unsure(field, alternatives, settings):
    """Unsure = the best answer is below the field's cut, or barely ahead of the second."""
    if not alternatives:
        return False
    best = alternatives[0]["conf"]
    second = alternatives[1]["conf"] if len(alternatives) > 1 else 0.0
    return best < settings["min_conf_" + field] or best - second < settings["margin"]
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_explain.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add mappings/xai_settings.csv src/phase4/explain.py backend/tests/test_explain.py
git commit -m "XAI: unsure rule with the team's thresholds (REVIEW)"
```

---

### Task 3: Grad-CAM and heatmap overlay

**Files:**
- Modify: `src/phase4/explain.py`
- Modify: `backend/tests/test_explain.py`

**Interfaces:**
- Consumes: `classifier.DressMeNet`, `classifier.TO_TENSOR`, `classifier.SIZE`, `classifier.HEADS`, `item_images.letterbox`.
- Produces: `explain.class_index(head: str, value: str) -> int` (raises `ValueError` for an unknown head or value).
- Produces: `explain.letterbox_box(width, height, size=224) -> (left, top, right, bottom)`.
- Produces: `explain.gradcam(model, img: PIL.Image, head: str, class_idx: int, device: str) -> np.ndarray (224, 224) float32 in [0, 1]`, 0 on the letterbox padding.
- Produces: `explain.overlay(img: PIL.Image, heat: np.ndarray) -> PIL.Image (224 x 224 RGB)`.

- [ ] **Step 1: Write the failing tests** (append)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_explain.py -v`
Expected: FAIL — `AttributeError: module 'explain' has no attribute 'class_index'`.

- [ ] **Step 3: Implement in `src/phase4/explain.py`**

Add `from PIL import Image` and `from item_images import ROOT, letterbox` to the imports, then:

```python
SIZE = 224          # the classifier's input size (classifier.SIZE)


def class_index(head, value):
    """Position of a class in the classifier's output; ValueError if unknown."""
    from classifier import HEADS
    if head not in HEADS:
        raise ValueError(f"unknown field {head!r}")
    if value not in HEADS[head]:
        raise ValueError(f"unknown {head} {value!r}")
    return HEADS[head].index(value)


def letterbox_box(width, height, size=SIZE):
    """Where the real picture sits inside the white letterbox square (same maths as letterbox)."""
    scale = size / max(width, height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    left, top = (size - w) // 2, (size - h) // 2
    return left, top, left + w, top + h


def gradcam(model, img, head, class_idx, device):
    """Where the classifier looked to give `class_idx` for `head` (224 x 224, 0 to 1).

    Grad-CAM: weigh each of the 1280 feature maps (7 x 7) of the last block by
    how much it raises the class score, add them up, keep the positive part.
    Our heads are one linear layer on the averaged maps, so the gradient is
    simply the head's weights / 49 (Grad-CAM equals the classic CAM here) and
    nothing has to flow back through the body. All heads share the body, so a
    map shows where the model looked to DECIDE, not the outline of the part.
    """
    import torch
    import torch.nn.functional as F
    from classifier import TO_TENSOR

    x = TO_TENSOR(letterbox(img.convert("RGB"), SIZE)).unsqueeze(0).to(device)
    with torch.no_grad():
        maps = model.features(x).float()                       # 1 x 1280 x 7 x 7
    maps.requires_grad_(True)
    with torch.enable_grad():
        score = model.heads[head](torch.flatten(model.pool(maps), 1))[0, class_idx]
        grads, = torch.autograd.grad(score, maps)
    weights = grads.mean(dim=(2, 3), keepdim=True)            # one weight per feature map
    cam = F.relu((weights * maps).sum(dim=1, keepdim=True)).detach()
    cam = F.interpolate(cam, size=(SIZE, SIZE), mode="bilinear", align_corners=False)[0, 0]
    heat = cam.cpu().numpy().astype(np.float32)
    left, top, right, bottom = letterbox_box(img.width, img.height)
    outside = np.ones_like(heat, dtype=bool)
    outside[top:bottom, left:right] = False
    heat[outside] = 0                                           # the white padding is not the item
    return heat / heat.max() if heat.max() > 0 else heat


def overlay(img, heat):
    """The letterboxed photo with the heat painted on top (yellow = a little, red = a lot)."""
    base = np.asarray(letterbox(img.convert("RGB"), SIZE)).astype(float)
    colour = np.stack([np.full_like(heat, 255), 230 * (1 - heat), np.zeros_like(heat)], axis=-1)
    alpha = (0.6 * heat)[..., None]                              # cold areas show the plain photo
    return Image.fromarray((base * (1 - alpha) + colour * alpha).astype(np.uint8))
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_explain.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/phase4/explain.py backend/tests/test_explain.py
git commit -m "XAI: Grad-CAM heatmaps of the classifier"
```

---

### Task 4: Colour pixel map

**Files:**
- Modify: `src/phase4/explain.py`
- Modify: `backend/tests/test_explain.py`

**Interfaces:**
- Consumes: `estimate_colours.item_pixels_mask`, `colour_utils.Palette`, `colour_utils.PALETTE_PATH` (Task 1).
- Produces: `explain.colour_map(img: PIL.Image, colour: str, palette: Palette | None = None) -> (mask np.ndarray (224,224) bool, share: float, reliable: bool)`; `ValueError` for a colour not in `mappings/colour_palette.csv`.
- Produces: `explain.mask_overlay(img: PIL.Image, mask: np.ndarray) -> PIL.Image (224 x 224 RGB)`.

- [ ] **Step 1: Write the failing tests** (append)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_explain.py -v`
Expected: FAIL — `AttributeError: module 'explain' has no attribute 'colour_map'`.

- [ ] **Step 3: Implement in `src/phase4/explain.py`**

Add `from colour_utils import PALETTE_PATH, Palette` to the imports, then:

```python
LIGHT = {"white", "cream"}     # these blend into the white background: no reliable map
ALL_COLOURS = pd.read_csv(PALETTE_PATH, keep_default_na=False)["colour"].tolist()


def colour_map(img, colour, palette=None):
    """The item pixels whose nearest palette colour is `colour`.

    Returns (mask 224 x 224, share of the item's pixels, reliable). This is a
    picture to help the user: the colour model itself reads a histogram of all
    the item's colours, not single pixels. The item area uses the colour
    model's own background rule (estimate_colours.item_pixels_mask).
    """
    from estimate_colours import item_pixels_mask
    if colour not in ALL_COLOURS:
        raise ValueError(f"unknown colour {colour!r}")
    palette = palette or Palette()
    px = np.asarray(letterbox(img.convert("RGB"), SIZE)).astype(int)
    item = item_pixels_mask(px)
    reliable = colour not in LIGHT and colour in palette.names and item.mean() >= 0.03
    if item.mean() < 0.03:              # nothing but white found: look at the whole picture
        item = np.ones(item.shape, dtype=bool)
    if colour not in palette.names:     # "multicolour" has no single colour to look for
        return np.zeros(item.shape, dtype=bool), 0.0, False
    nearest = np.full(item.shape, -1)
    nearest[item] = palette.nearest_index(px[item])
    mask = nearest == palette.names.index(colour)
    return mask, round(float(mask.sum() / item.sum()), 3), bool(reliable)


def mask_overlay(img, mask):
    """The letterboxed photo with everything outside `mask` faded out."""
    base = np.asarray(letterbox(img.convert("RGB"), SIZE)).astype(float)
    faded = base * 0.25 + 255 * 0.75
    return Image.fromarray(np.where(mask[..., None], base, faded).astype(np.uint8))
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_explain.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add src/phase4/explain.py backend/tests/test_explain.py
git commit -m "XAI: colour pixel map"
```

---

### Task 5: Analyzer — alternatives at analysis time, `explain` on demand

**Files:**
- Modify: `backend/app/ml.py`
- Modify: `backend/tests/conftest.py` (`FakeAnalyzer`)
- Modify: `backend/tests/test_real_models.py`

**Interfaces:**
- Consumes: Tasks 1-4 (`decode(...)["top3"]`, `predict_top`, `is_unsure`, `load_settings`, `gradcam`, `class_index`, `colour_map`, `overlay`, `mask_overlay`).
- Produces: `Analyzer.analyze(img)[field]` = `{"value", "conf", "alternatives": [...], "unsure": bool}` for the 4 fields (`vector` unchanged).
- Produces: `Analyzer.explain(img, head: str | None = None, value: str | None = None) -> dict[field, entry]` where entry = `{"shown": str, "alternatives": [...], "heatmap": PIL.Image}` for classifier fields and `{"shown", "alternatives", "pixels": PIL.Image, "share": float, "reliable": bool}` for colour. `head=None` = all 4 fields at their best class. Raises `ValueError` for an unknown head / value.
- Produces: `app.ml.unsure(field, alternatives) -> bool` (reads the team settings each call).

- [ ] **Step 1: Give `FakeAnalyzer` an `explain`** (in `backend/tests/conftest.py`)

```python
    def explain(self, img, head=None, value=None):
        """Like the real one: fixed small pictures, alternatives from analyze()."""
        fields = ["category", "sub_category", "pattern", "colour"]
        if head is not None and head not in fields:
            raise ValueError(f"unknown field {head!r}")
        if value == "nonsense":
            raise ValueError(f"unknown {head} {value!r}")
        analysis = self.analyze(img)
        out = {}
        for f in [head] if head else fields:
            best = analysis[f]
            entry = {"shown": value or best["value"],
                     "alternatives": [{"value": best["value"], "conf": best["conf"]},
                                      {"value": "other", "conf": round(1 - best["conf"], 3)}]}
            picture = Image.new("RGB", (8, 8), (255, 0, 0))
            if f == "colour":
                entry.update(pixels=picture, share=0.5, reliable=True)
            else:
                entry["heatmap"] = picture
            out[f] = entry
        return out
```

- [ ] **Step 2: Add a real-model test** (append to `backend/tests/test_real_models.py`)

```python
def test_explain_on_a_test_photo(models):
    from item_images import DATA, load_item_image
    analyzer, _ = models
    df = pd.read_csv(DATA / "processed" / "fashion_product.csv", dtype=str, keep_default_na=False, nrows=50)
    img = load_item_image(df.iloc[0].to_dict())
    out = analyzer.analyze(img)
    for f in ("category", "sub_category", "pattern", "colour"):
        assert out[f]["alternatives"][0]["value"] == out[f]["value"]
        assert isinstance(out[f]["unsure"], bool)
    why = analyzer.explain(img)
    assert why["category"]["shown"] == out["category"]["value"]
    assert why["category"]["heatmap"].size == (224, 224)
    assert 0 <= why["colour"]["share"] <= 1
    other = analyzer.explain(img, head="pattern", value="striped")
    assert list(other) == ["pattern"] and other["pattern"]["shown"] == "striped"
```

- [ ] **Step 3: Implement in `backend/app/ml.py`**

In `Analyzer.__init__`, import and keep the explain module and the palette:

```python
        import explain
        from colour_utils import Palette
        ...
        self._explain, self._palette = explain, Palette()
```

Replace `analyze` and add the helpers:

```python
    def analyze(self, img):
        explain = self._explain
        p = self.classify_for_mask(img)
        out = {f: {"value": p[f], "conf": round(p[f + "_conf"], 3), "alternatives": p["top3"][f]}
               for f in ("category", "sub_category", "pattern")}
        colours = self.colour_alternatives(img, p["category"])
        out["colour"] = {"value": colours[0]["value"], "conf": colours[0]["conf"], "alternatives": colours}
        settings = explain.load_settings()
        for f, guess in out.items():
            guess["unsure"] = explain.is_unsure(f, guess["alternatives"], settings)
        fashionclip = self._modules[1]
        out["vector"] = fashionclip.embed_images([img], self._clip, self._processor, self.device)[0]
        return out

    def colour_alternatives(self, img, category):
        """Top 3 colours: same features and metal rule as the dataset estimates."""
        estimate_colours = self._modules[2]
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        X = estimate_colours.product_features(io.BytesIO(buf.getvalue())).reshape(1, -1)
        return estimate_colours.predict_top(self._colour, X, [category])[0]

    def explain(self, img, head=None, value=None):
        """Pictures of why each label was given (see src/phase4/explain.py). Without `head`:
        the 4 fields at their best answer; with `head` + `value`: that answer only."""
        explain = self._explain
        if head is not None and head not in explain.FIELDS:
            raise ValueError(f"unknown field {head!r}")
        p = self.classify_for_mask(img)
        out = {}
        for f in [head] if head else explain.FIELDS:
            alternatives = self.colour_alternatives(img, p["category"]) if f == "colour" else p["top3"][f]
            shown = value or alternatives[0]["value"]
            entry = {"shown": shown, "alternatives": alternatives}
            if f == "colour":
                mask, share, reliable = explain.colour_map(img, shown, self._palette)
                entry.update(pixels=explain.mask_overlay(img, mask), share=share, reliable=reliable)
            else:
                heat = explain.gradcam(self._classifier, img, f, explain.class_index(f, shown), self.device)
                entry["heatmap"] = explain.overlay(img, heat)
            out[f] = entry
        return out
```

Add a module-level helper next to `colour_min_confidence`:

```python
def unsure(field, alternatives):
    """The team's "not sure, check" rule (mappings/xai_settings.csv), for stored guesses."""
    import explain
    return explain.is_unsure(field, alternatives, explain.load_settings())
```

Update the module docstring's `Analyzer.analyze` example to show `"alternatives"` / `"unsure"` and add `Analyzer.explain(pil_image, head, value) -> pictures of why`.

Note: `predict_top` and the old `predict` give the same best colour (shared `probabilities`), so stored values do not change.

- [ ] **Step 4: Run all backend tests**

Run: `python -m pytest -q`
Expected: all pass (133 + 15 new). `test_items.py` still sees `predicted["category"] == {"value": "top", "conf": 0.95}` because the fake `analyze` is unchanged.

- [ ] **Step 5: Run the real-model tests**

Run: `DRESSME_SLOW=1 python -m pytest tests/test_real_models.py -v` (PowerShell: `$env:DRESSME_SLOW='1'; python -m pytest tests/test_real_models.py -v`)
Expected: all pass, including `test_explain_on_a_test_photo`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ml.py backend/tests/conftest.py backend/tests/test_real_models.py
git commit -m "XAI: the Analyzer stores top-3 answers and explains them on demand"
```

---

### Task 6: `/explain` endpoints

**Files:**
- Modify: `backend/app/routers/items.py` (`item_image`, `candidate_image` ~lines 129-146)
- Create: `backend/app/routers/explain.py`
- Modify: `backend/app/main.py` (router import + list)
- Create: `backend/tests/test_explain_api.py`

**Interfaces:**
- Consumes: `Analyzer.explain`, `app.ml.unsure` (Task 5); `own_item` (items.py); `as_data_url` (routers/tryon.py).
- Produces: `items.load_photo(request, user, doc) -> bytes | None` (the stored cleaned JPEG of an item or candidate).
- Produces: `GET /items/{id}/explain?head=&value=` and `GET /candidates/{id}/explain?head=&value=` →
  `{"fields": {field: {"shown", "value", "conf", "alternatives", "unsure", "corrected", "heatmap" | "pixels"+"share"+"reliable"}}}` (images as `data:image/jpeg;base64,...`). 404 not yours / no photo, 422 bad head / value / value without head.

- [ ] **Step 1: Write the failing API tests** — `backend/tests/test_explain_api.py`

```python
"""GET /items/{id}/explain and /candidates/{id}/explain (fake analyzer)."""

from tests.conftest import BLUE, RED, photo, sign_up, upload

FIELDS = {"category", "sub_category", "pattern", "colour"}


def test_explain_an_item(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    r = client.get(f"/items/{item['id']}/explain", headers=headers)
    assert r.status_code == 200
    fields = r.json()["fields"]
    assert set(fields) == FIELDS
    cat = fields["category"]
    assert (cat["value"], cat["conf"], cat["shown"]) == ("top", 0.95, "top")
    assert cat["heatmap"].startswith("data:image/jpeg;base64,")
    assert cat["alternatives"][0]["value"] == "top"          # old-style item: computed from the photo
    assert cat["unsure"] is False and cat["corrected"] is False
    colour = fields["colour"]
    assert colour["pixels"].startswith("data:image/jpeg;base64,") and colour["reliable"] is True


def test_explain_one_alternative(client):
    headers = sign_up(client)
    item = upload(client, headers, BLUE)
    r = client.get(f"/items/{item['id']}/explain?head=pattern&value=striped", headers=headers)
    assert r.status_code == 200
    fields = r.json()["fields"]
    assert list(fields) == ["pattern"] and fields["pattern"]["shown"] == "striped"
    assert fields["pattern"]["value"] == "solid"              # the stored answer is unchanged


def test_explain_bad_requests(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    base = f"/items/{item['id']}/explain"
    assert client.get(base + "?head=brand", headers=headers).status_code == 422
    assert client.get(base + "?head=pattern&value=nonsense", headers=headers).status_code == 422
    assert client.get(base + "?value=striped", headers=headers).status_code == 422


def test_explain_is_private(client):
    owner = sign_up(client)
    item = upload(client, owner, RED)
    other = sign_up(client, email="sami@example.com", name="Sami")
    assert client.get(f"/items/{item['id']}/explain", headers=other).status_code == 404


def test_explain_marks_corrected_fields(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    client.patch(f"/items/{item['id']}", json={"colour": "navy"}, headers=headers)
    fields = client.get(f"/items/{item['id']}/explain", headers=headers).json()["fields"]
    assert fields["colour"]["corrected"] is True and fields["colour"]["value"] == "red"


def test_explain_a_scan(client):
    headers = sign_up(client)
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    r = client.get(f"/candidates/{cand['id']}/explain?head=category", headers=headers)
    assert r.status_code == 200 and list(r.json()["fields"]) == ["category"]


def test_stored_alternatives_are_used(client):
    """An item analysed by the real Analyzer keeps its alternatives; explain uses those."""
    headers = sign_up(client)
    item = upload(client, headers, RED)
    from bson import ObjectId
    db = client.app.state.db
    stored = [{"value": "top", "conf": 0.55}, {"value": "dress", "conf": 0.45}]
    db.items.update_one({"_id": ObjectId(item["id"])},
                        {"$set": {"predicted.category.alternatives": stored}})
    cat = client.get(f"/items/{item['id']}/explain?head=category", headers=headers).json()["fields"]["category"]
    assert cat["alternatives"] == stored and cat["unsure"] is True     # 0.55 < 0.6 and a 0.10 lead
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest tests/test_explain_api.py -v`
Expected: FAIL — 404 on every `/explain` (route missing).

- [ ] **Step 3: Share the photo loading in `backend/app/routers/items.py`**

Add above `item_image`:

```python
def load_photo(request, user, doc):
    """The stored cleaned JPEG of an item or candidate (bytes), or None.
    Scans keep it in the document; items and shop-listing candidates as a file."""
    if doc.get("photo"):
        return bytes(doc["photo"])
    path = request.app.state.settings.storage_dir / str(user["_id"]) / f"{doc['_id']}.jpg"
    return path.read_bytes() if path.exists() else None
```

Rewrite both image routes with it:

```python
@router.get("/items/{item_id}/image")
def item_image(item_id: str, request: Request, user=Depends(current_user)):
    data = load_photo(request, user, own_item(request, user, item_id))
    if data is None:
        raise HTTPException(404, "Image missing")
    return Response(data, media_type="image/jpeg")


@router.get("/candidates/{candidate_id}/image")
def candidate_image(candidate_id: str, request: Request, user=Depends(current_user)):
    data = load_photo(request, user, own_item(request, user, candidate_id, collection="candidates"))
    if data is None:
        raise HTTPException(404, "Image missing")
    return Response(data, media_type="image/jpeg")
```

Remove the `FileResponse` import if nothing else uses it.

- [ ] **Step 4: Create `backend/app/routers/explain.py`**

```python
"""
Why did the models give these labels? (XAI, see src/phase4/explain.py)

    GET /items/{id}/explain         a wardrobe item
    GET /candidates/{id}/explain    a scan or shop listing (kept 24 h)
        ?head=pattern&value=striped -> only that field, for that answer ("why not striped?")

The stored answer (value, conf, alternatives) is what is explained; the
pictures are computed now from the stored photo and never saved.
"""

import io

from fastapi import APIRouter, Depends, HTTPException, Request
from PIL import Image

from ..ml import unsure
from ..security import current_user
from .items import load_photo, own_item
from .tryon import as_data_url

router = APIRouter(tags=["explain"])


def explanation(request, user, doc, head, value):
    if value is not None and head is None:
        raise HTTPException(422, "value needs head")
    data = load_photo(request, user, doc)
    if data is None:
        raise HTTPException(404, "Image missing")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    try:
        model = request.app.state.analyzer.explain(img, head=head, value=value)
    except ValueError as e:
        raise HTTPException(422, str(e))
    fields = {}
    for field, entry in model.items():
        stored = doc.get("predicted", {}).get(field) or {}
        # items saved before the XAI layer have no stored alternatives: use the fresh ones
        alternatives = stored.get("alternatives") or entry["alternatives"]
        out = {k: (as_data_url(v) if k in ("heatmap", "pixels") else v) for k, v in entry.items()}
        out.update(value=stored.get("value", entry["shown"]), conf=stored.get("conf"),
                   alternatives=alternatives, unsure=unsure(field, alternatives),
                   corrected=field in doc.get("corrected", []))
        fields[field] = out
    return {"fields": fields}


@router.get("/items/{item_id}/explain")
def explain_item(item_id: str, request: Request, head: str | None = None, value: str | None = None,
                 user=Depends(current_user)):
    return explanation(request, user, own_item(request, user, item_id), head, value)


@router.get("/candidates/{candidate_id}/explain")
def explain_candidate(candidate_id: str, request: Request, head: str | None = None,
                      value: str | None = None, user=Depends(current_user)):
    doc = own_item(request, user, candidate_id, collection="candidates")
    return explanation(request, user, doc, head, value)
```

- [ ] **Step 5: Register the router in `backend/app/main.py`**

Change line 23 to `from .routers import admin, auth, chat, explain, insights, items, listings, outfits, tryon, weather` and add `explain.router` to the list of routers included near line 54 (follow how the others are listed).

- [ ] **Step 6: Run the tests**

Run: `python -m pytest -q`
Expected: all pass (the image routes still pass `test_items.py`).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/items.py backend/app/routers/explain.py backend/app/main.py backend/tests/test_explain_api.py
git commit -m "XAI: /items/{id}/explain and /candidates/{id}/explain"
```

---

### Task 7: Frontend — "Why these labels?" panel and the "not sure" badge

**Files:**
- Modify: `frontend/src/api/types.ts` (`Guess` ~line 22, new types)
- Modify: `frontend/src/api/client.ts` (`api` object)
- Create: `frontend/src/ui/ExplainPanel.tsx`
- Modify: `frontend/src/ui/Field.tsx` (`FieldRow` badge)
- Modify: `frontend/src/pages/WardrobePage.tsx` (`ItemPage`), `frontend/src/pages/ScanPage.tsx` (check section)
- Modify: `frontend/src/i18n/strings.ts` (`en`, `fr`, `ar`)

**Interfaces:**
- Consumes: `GET /items/{id}/explain`, `GET /candidates/{id}/explain` (Task 6).
- Produces: `api.explain(ref: { itemId?: string; candidateId?: string }, head?: GuessField, value?: string): Promise<Explanation>`; `<ExplainPanel target={{ itemId } | { candidateId }} />`.

- [ ] **Step 1: Types** — in `types.ts` replace `Guess` and add the explanation types:

```ts
export interface Alternative {
  value: string
  conf: number
}

export interface Guess {
  value: string
  conf: number
  alternatives?: Alternative[]   // items analysed before the XAI layer have none
  unsure?: boolean
}

export type GuessField = 'category' | 'sub_category' | 'pattern' | 'colour'

export interface ExplainField {
  shown: string                  // the answer the picture is for
  value: string                  // the model's stored answer
  conf: number | null
  alternatives: Alternative[]
  unsure: boolean
  corrected: boolean
  heatmap?: string               // data URL (category / sub_category / pattern)
  pixels?: string                // data URL (colour)
  share?: number
  reliable?: boolean
}

export interface Explanation {
  fields: Partial<Record<GuessField, ExplainField>>
}
```

Change `Item.predicted` to `Partial<Record<GuessField, Guess>>`.

- [ ] **Step 2: API call** — in `client.ts` add `Explanation, GuessField` to the type import and, after `similar`:

```ts
  explain: (ref: { itemId?: string; candidateId?: string }, head?: GuessField, value?: string) => {
    const q = new URLSearchParams()
    if (head) q.set('head', head)
    if (value) q.set('value', value)
    const base = ref.itemId ? `/items/${ref.itemId}` : `/candidates/${ref.candidateId}`
    return request<Explanation>(`${base}/explain${q.toString() ? `?${q}` : ''}`)
  },
```

- [ ] **Step 3: Strings** — add to `en` (after `guessed`):

```ts
  whyLabels: 'Why these labels?',
  hideWhy: 'Hide the explanation',
  explainIntro: 'How the model read this photo. Tap another answer to see where it would look for it.',
  explainLooked: 'Where it looked to decide “{value}”',
  explainColour: 'Pixels that look {value}: {p}% of the piece',
  explainColourNote: 'A visual aid: the colour model reads the whole mix of colours, not single pixels.',
  explainColourUnreliable: 'Light pieces blend into the white background, so there is no pixel map here.',
  explainAlternatives: 'Other answers it considered',
  explainCorrected: 'You corrected this field; the picture shows what the model saw.',
  unsureBadge: 'not sure, check',
```

`fr`:

```ts
  whyLabels: 'Pourquoi ces étiquettes ?',
  hideWhy: 'Masquer l’explication',
  explainIntro: 'Comment le modèle a lu cette photo. Touche une autre réponse pour voir où il la chercherait.',
  explainLooked: 'Où il a regardé pour décider « {value} »',
  explainColour: 'Pixels qui semblent {value} : {p} % de la pièce',
  explainColourNote: 'Une aide visuelle : le modèle de couleur lit tout le mélange de couleurs, pas des pixels isolés.',
  explainColourUnreliable: 'Les pièces claires se confondent avec le fond blanc : pas de carte de pixels ici.',
  explainAlternatives: 'Autres réponses envisagées',
  explainCorrected: 'Tu as corrigé ce champ ; l’image montre ce que le modèle a vu.',
  unsureBadge: 'pas sûr, vérifie',
```

`ar`:

```ts
  whyLabels: 'لماذا هذه التسميات؟',
  hideWhy: 'إخفاء الشرح',
  explainIntro: 'هكذا قرأ النموذج هذه الصورة. اضغط على إجابة أخرى لترى أين كان سيبحث عنها.',
  explainLooked: 'أين نظر ليقرّر «{value}»',
  explainColour: 'البكسلات التي تبدو {value}: {p}٪ من القطعة',
  explainColourNote: 'مساعدة بصرية: نموذج الألوان يقرأ مزيج الألوان كله، لا بكسلات منفردة.',
  explainColourUnreliable: 'القطع الفاتحة تختلط بالخلفية البيضاء، لذلك لا توجد خريطة بكسلات هنا.',
  explainAlternatives: 'إجابات أخرى فكّر فيها',
  explainCorrected: 'لقد صحّحت هذا الحقل؛ الصورة تُظهر ما رآه النموذج.',
  unsureBadge: 'غير متأكد، تحقّق',
```

- [ ] **Step 4: Badge in `FieldRow`** (`ui/Field.tsx`) — replace the right-hand label span:

```tsx
          <span className={`ms-auto shrink-0 font-mono text-[11px] tabular ${!sure && guess?.unsure ? 'font-semibold text-stamp' : 'text-ink-soft'}`}>
            {sure ? t('confirmed') : guess ? (guess.unsure ? t('unsureBadge') : t('guessed', { p: Math.round(guess.conf * 100) })) : ''}
          </span>
```

(The row is already a button that opens the correction choices, so the badge leads to them.)

- [ ] **Step 5: Create `frontend/src/ui/ExplainPanel.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Explanation, ExplainField, GuessField } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import { CATEGORY_LABELS, COLOUR_LABELS, PATTERN_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { ErrorNote, Skeleton } from './states'

const ORDER: GuessField[] = ['category', 'sub_category', 'pattern', 'colour']
const TABLES = { category: CATEGORY_LABELS, sub_category: SUB_LABELS, pattern: PATTERN_LABELS, colour: COLOUR_LABELS }
const LABEL_KEY: Record<GuessField, StringKey> = { category: 'category', sub_category: 'type', pattern: 'pattern', colour: 'colour' }

/** "Why these labels?": where the classifier looked (heatmap), which pixels look
 *  like the colour, and the other answers it considered. Tapping another answer
 *  shows where the model would look for that one. Nothing is saved. */
export function ExplainPanel({ target }: { target: { itemId?: string; candidateId?: string } }) {
  const { t, lang } = useI18n()
  const [data, setData] = useState<Explanation | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState<GuessField | null>(null)

  useEffect(() => {
    let live = true
    api.explain(target).then((d) => live && setData(d)).catch((e) => live && setError(e))
    return () => { live = false }
  }, [target.itemId, target.candidateId])

  const showOther = async (field: GuessField, value: string) => {
    setBusy(field)
    try {
      const d = await api.explain(target, field, value)
      setData((old) => old && { fields: { ...old.fields, [field]: d.fields[field] } })
    } catch (e) {
      setError(e)
    } finally {
      setBusy(null)
    }
  }

  if (error) return <ErrorNote error={error} />
  if (!data) return <Skeleton className="h-[320px]" />

  const label = (field: GuessField, v: string) => vocab(TABLES[field], v, lang)
  return (
    <div className="space-y-5">
      <p className="text-[13px] text-carbon-soft">{t('explainIntro')}</p>
      {ORDER.map((field) => {
        const f: ExplainField | undefined = data.fields[field]
        if (!f) return null
        const picture = f.heatmap ?? (f.reliable ? f.pixels : undefined)
        return (
          <div key={field} className="flex gap-4 max-sm:flex-col" aria-busy={busy === field || undefined}>
            {picture
              ? <img src={picture} alt="" className="size-[140px] shrink-0 border border-perf/60 bg-paper object-contain" />
              : <div className="size-[140px] shrink-0 border border-dashed border-perf/60" aria-hidden />}
            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t(LABEL_KEY[field])}</p>
              <p className="text-[15px] text-carbon">
                {field === 'colour'
                  ? f.reliable
                    ? t('explainColour', { value: label(field, f.shown), p: Math.round((f.share ?? 0) * 100) })
                    : t('explainColourUnreliable')
                  : t('explainLooked', { value: label(field, f.shown) })}
              </p>
              {field === 'colour' && f.reliable && <p className="text-[12px] text-carbon-soft">{t('explainColourNote')}</p>}
              {f.corrected && <p className="text-[12px] text-carbon-soft">{t('explainCorrected')}</p>}
              <p className="mt-2 text-[12px] text-carbon-soft">{t('explainAlternatives')}</p>
              <ul className="mt-1 space-y-1">
                {f.alternatives.map((a) => (
                  <li key={a.value}>
                    <button
                      type="button"
                      onClick={() => void showOther(field, a.value)}
                      aria-pressed={a.value === f.shown}
                      className={`flex w-full items-center gap-2 text-start text-[14px] ${a.value === f.shown ? 'font-semibold text-ink' : 'text-carbon'}`}
                    >
                      <span className="w-28 truncate">{label(field, a.value)}</span>
                      <span className="h-2 flex-1 bg-stock-deep" aria-hidden>
                        <span className="block h-2 bg-ink" style={{ width: `${Math.round(a.conf * 100)}%` }} />
                      </span>
                      <span className="w-10 text-end font-mono text-[11px] tabular">{Math.round(a.conf * 100)}%</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 6: Toggle on the item page** (`WardrobePage.tsx`, `ItemPage`) — add `const [why, setWhy] = useState(false)`, import `Lightbulb` from `lucide-react` and `ExplainPanel` from `../ui/ExplainPanel`, and insert after the fields `<section>` (before the `{error ? ...}` line):

```tsx
            <Button variant="quiet" className="mt-3" onClick={() => setWhy(!why)} aria-expanded={why}>
              <Lightbulb className="size-4" aria-hidden /> {why ? t('hideWhy') : t('whyLabels')}
            </Button>
            {why && <section className="ticket mt-2 px-4 py-4"><ExplainPanel target={{ itemId: it.id }} /></section>}
```

- [ ] **Step 7: Toggle on the scan page** (`ScanPage.tsx`) — same state, imports, and inside the `{candidate && !advice && (...)}` section, right before the `askVerdict` `<Button>`:

```tsx
            <Button variant="quiet" className="mt-3" onClick={() => setWhy(!why)} aria-expanded={why}>
              <Lightbulb className="size-4" aria-hidden /> {why ? t('hideWhy') : t('whyLabels')}
            </Button>
            {why && <div className="mt-2 border-t border-perf/40 pt-4"><ExplainPanel target={{ candidateId: candidate.id }} /></div>}
```

Reset `why` to `false` wherever the page starts a new scan (where `setCandidate(null)` is called).

- [ ] **Step 8: Build and lint**

Run: `npm --prefix frontend run build` then `npm --prefix frontend run lint`
Expected: no TypeScript errors, no lint errors.

- [ ] **Step 9: Check it in the browser**

Start MongoDB-backed `api` and `web` with `preview_start` (`.claude/launch.json` names `api`, `web`; the real models take ~1 min). Log in with a test account created for this check (record its credentials in `backend/.env.example` comments only if the project already does so; otherwise make one through the sign-up page with generated test values), add a wardrobe photo, open the item, click "Why these labels?". Check: 4 rows, heatmaps visible, clicking an alternative reloads that row only, Arabic layout mirrors, no console errors, phone width (375 px) has no horizontal scroll. Take a screenshot as proof.

- [ ] **Step 10: Commit**

```bash
git add frontend/src
git commit -m "XAI: 'Why these labels?' panel and 'not sure, check' badge"
```

---

### Task 8: Offline evaluation report

**Files:**
- Create: `src/phase4/evaluate_explanations.py`
- Generated: `reports/phase4/explanations_evaluation.md`, `reports/phase4/figures/gradcam_examples.png`

**Interfaces:**
- Consumes: `train_classifier.load_table`, `train_classifier.batches`, `build_image_cache.PACK`, `classifier.load_classifier / predict_tensors / decode / TO_TENSOR / HEADS`, `explain.gradcam / overlay / is_unsure / load_settings`, `estimate_colours.item_pixels_mask`.

- [ ] **Step 1: Write `src/phase4/evaluate_explanations.py`**

```python
"""
Are the item-label explanations honest? (XAI sub-project 1)

On the test split of the image cache:
  1. calibration of the "unsure" flag (mappings/xai_settings.csv): accuracy of
     sure vs unsure answers, and accuracy per confidence bucket, per field;
  2. deletion test: whiten the hottest 10 / 20 / 40% of the item's pixels
     (Grad-CAM) vs the same share of random item pixels. If the heatmap shows
     what the model uses, its confidence drops faster with the heatmap;
  3. a figure of Grad-CAM examples, right and wrong answers.
-> reports/phase4/explanations_evaluation.md + reports/phase4/figures/gradcam_examples.png

    python src/phase4/evaluate_explanations.py [--limit 2000]

Colour is not here: its cut was chosen in reports/phase3/colour_estimation.md.
"""

import argparse
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from PIL import Image

import src_path  # noqa: F401
import explain
from build_image_cache import PACK
from classifier import HEADS, TO_TENSOR, decode, load_classifier, predict_tensors
from estimate_colours import item_pixels_mask
from item_images import ROOT
from train_classifier import batches, load_table

REPORT = ROOT / "reports" / "phase4" / "explanations_evaluation.md"
FIGURE = ROOT / "reports" / "phase4" / "figures" / "gradcam_examples.png"
SHARES = [0.1, 0.2, 0.4]
BUCKETS = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]


def calibration(test, model, device):
    """Accuracy of sure / unsure answers, per field, on the whole test split."""
    answers = []
    for x, _ in batches(test, device, train=False, batch=128):     # same order as `test`
        answers += decode(predict_tensors(x, model, device))
    settings = explain.load_settings()
    rows, buckets = [], []
    for head in HEADS:
        truth = test[head].to_numpy()
        has = truth != ""
        pred = np.array([a[head] for a in answers])
        conf = np.array([a["top3"][head][0]["conf"] if a["top3"][head] else 0 for a in answers])
        unsure = np.array([explain.is_unsure(head, a["top3"][head], settings) for a in answers])
        ok = pred == truth
        for name, keep in (("sure", has & ~unsure), ("unsure", has & unsure)):
            rows.append({"field": head, "group": name, "pictures": int(keep.sum()),
                         "share": keep.sum() / max(has.sum(), 1), "accuracy": ok[keep].mean() if keep.any() else np.nan})
        for lo, hi in zip(BUCKETS[:-1], BUCKETS[1:]):
            keep = has & (conf >= lo) & (conf < hi)
            buckets.append({"field": head, "confidence": f"{lo:.1f}-{min(hi, 1):.1f}", "pictures": int(keep.sum()),
                            "accuracy": ok[keep].mean() if keep.any() else np.nan})
    return pd.DataFrame(rows), pd.DataFrame(buckets), answers


def whitened(px, pixels):
    out = px.copy()
    out[pixels] = 255
    return Image.fromarray(out.astype(np.uint8))


def deletion(sample, pictures, model, device, rng):
    """Mean confidence drop of the predicted class: heatmap pixels vs random pixels."""
    rows = []
    for img in pictures:
        px = np.asarray(img.convert("RGB")).astype(int)
        item = item_pixels_mask(px)
        if item.sum() < 100:
            continue
        x = TO_TENSOR(img.convert("RGB")).unsqueeze(0)
        base = predict_tensors(x, model, device)
        for head in HEADS:
            cls = int(base[head][0].argmax())
            heat = explain.gradcam(model, img, head, cls, device)
            order = np.argsort(-heat[item])                         # hottest item pixels first
            coords = np.argwhere(item)
            variants = []
            for share in SHARES:
                n = int(share * len(coords))
                hot = np.zeros_like(item)
                hot[tuple(coords[order[:n]].T)] = True
                rand = np.zeros_like(item)
                rand[tuple(coords[rng.choice(len(coords), n, replace=False)].T)] = True
                variants += [whitened(px, hot), whitened(px, rand)]
            p = predict_tensors(torch.stack([TO_TENSOR(v) for v in variants]), model, device)[head][:, cls]
            p0 = base[head][0, cls]
            for i, share in enumerate(SHARES):
                rows.append({"field": head, "share": share,
                             "heatmap": p0 - p[2 * i], "random": p0 - p[2 * i + 1]})
    return pd.DataFrame(rows).groupby(["field", "share"])[["heatmap", "random"]].mean().reset_index()


def examples_figure(sample, pictures, answers, model, device):
    """Two rows: right answers, wrong answers (category head), one per category when possible."""
    right, wrong = [], []
    for i, (row, a) in enumerate(zip(sample.itertuples(), answers)):
        if row.category == "":
            continue
        target = right if a["category"] == row.category else wrong
        if len(target) < 6 and all(sample.iloc[j].category != row.category for j in target):
            target.append(i)
    fig, axes = plt.subplots(2, 6, figsize=(16, 6))
    for ax_row, chosen, title in zip(axes, (right, wrong), ("right", "wrong")):
        for ax, i in zip(ax_row, chosen + [None] * 6):
            ax.axis("off")
            if i is None:
                continue
            cls = HEADS["category"].index(answers[i]["category"])
            heat = explain.gradcam(model, pictures[i], "category", cls, device)
            ax.imshow(explain.overlay(pictures[i], heat))
            ax.set_title(f"{title}: {answers[i]['category']}\n(true {sample.iloc[i].category})", fontsize=9)
    fig.suptitle("Grad-CAM, category head: where the model looked")
    fig.tight_layout()
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, dpi=100)
    plt.close(fig)


def table(df):
    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join("---" if df[c].dtype == object else "---:" for c in df.columns) + "|"
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)
    return "\n".join([head, sep] + ["| " + " | ".join(fmt(v) for v in r) + " |" for r in df.itertuples(index=False)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2000, help="pictures for the deletion test")
    args = parser.parse_args()
    rng = np.random.default_rng(0)
    model, device = load_classifier()
    df = load_table()
    test = df[df["split"] == "test"].reset_index(drop=True)
    print(f"calibration on {len(test):,} test pictures ...", flush=True)
    sure, buckets, _ = calibration(test, model, device)

    sample = test.sample(min(args.limit, len(test)), random_state=0).reset_index(drop=True)
    pack = np.memmap(PACK, dtype=np.uint8, mode="r")
    pictures = [Image.open(io.BytesIO(pack[o:o + n].tobytes())).convert("RGB")
                for o, n in zip(sample["offset"], sample["length"])]
    print(f"deletion test on {len(sample):,} pictures ...", flush=True)
    drops = deletion(sample, pictures, model, device, rng)
    answers = decode(predict_tensors(torch.stack([TO_TENSOR(p) for p in pictures[:256]]), model, device))
    examples_figure(sample.head(256), pictures[:256], answers, model, device)

    lines = ["# Item-label explanations: evaluation", "",
             f"Test split of the image cache. Calibration on {len(test):,} pictures, "
             f"deletion test on {len(sample):,}. Thresholds from `mappings/xai_settings.csv` (REVIEW).", "",
             "## 1. Is the \"not sure, check\" flag honest?", "",
             "Accuracy of the answers the app shows as sure vs unsure (pictures with a label only).", "",
             table(sure), "", "Accuracy per confidence bucket:", "", table(buckets), "",
             "## 2. Deletion test", "",
             "Mean drop of the predicted class's confidence after whitening a share of the item's "
             "pixels: the hottest Grad-CAM pixels vs random pixels. A bigger drop with the heatmap "
             "means the heatmap points at what the model really uses.", "",
             table(drops), "",
             "## 3. Examples", "", "![Grad-CAM examples](figures/gradcam_examples.png)", "",
             "All three heads share one body, so a heatmap shows where the model looked to decide, "
             "not the outline of a part."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke run**

Run (repo root): `python src/phase4/evaluate_explanations.py --limit 50`
Expected: prints the two progress lines and `-> reports/phase4/explanations_evaluation.md`; the report has 3 sections and the figure exists. (Calibration still uses the full test split: ~2-3 min at ~200 img/s.) Fix any error before the full run.

- [ ] **Step 3: Full run as a separate process with a log**

PowerShell (repo root):
```powershell
Start-Process python -ArgumentList "src/phase4/evaluate_explanations.py","--limit","2000" -RedirectStandardOutput reports/explanations_eval.log -RedirectStandardError reports/explanations_eval.err -NoNewWindow
```
Wait for `-> ...` in the log (expected ~10-15 min). Read the report: the heatmap column must drop more than the random column for every field at 10%; if not, say so in the report's text and tell the user (do not tune anything to make it pass).

- [ ] **Step 4: Commit**

```bash
git add src/phase4/evaluate_explanations.py reports/phase4/explanations_evaluation.md reports/phase4/figures/gradcam_examples.png
git commit -m "XAI: evaluation of the explanations (calibration, deletion test, examples)"
```

(Do not commit the `.log` / `.err` files.)

---

### Task 9: Documentation

**Files:**
- Modify: `CLAUDE.md` (Phase 4 list)
- Modify: `docs/superpowers/specs/2026-10-04-item-label-xai-design.md`

- [ ] **Step 1: Add the XAI item to `CLAUDE.md`** after item 6 (Listings):

```markdown
7. **XAI layer (sub-project 1 of 4 done: item labels):** spec / plan in `docs/superpowers/`. `src/phase4/explain.py`: `is_unsure` (team cuts in `mappings/xai_settings.csv`, all REVIEW), `gradcam` (EfficientNet heads are linear on pooled maps, so Grad-CAM = CAM; padding zeroed), `colour_map` (item pixels nearest to the colour, using the colour model's own background rule; not reliable for white / cream), overlays. Analysis stores `alternatives` (top 3) and `unsure` in `predicted` (old items have none: readers use `.get`). `GET /items/{id}/explain`, `/candidates/{id}/explain` (`?head=&value=` for "why not X?"), computed on demand, never stored. App: "Why these labels?" (`ui/ExplainPanel.tsx`) on the item and scan pages, "not sure, check" badge in `FieldRow`. `src/phase4/evaluate_explanations.py` → `reports/phase4/explanations_evaluation.md` (calibration of the unsure flag, deletion test, examples). Next: 2 outfit score + buy advice, 3 similarity + chat, 4 jury report + Admin > Explainability.
```

Add the new row count to the backend tests line (`110 tests` → the real number printed by `python -m pytest -q`).

- [ ] **Step 2: Update the spec** — set `Status: implemented` and add a short "Changes while planning" section copying the five bullets of this plan's "Deviations from the spec".

- [ ] **Step 3: Final check**

Run (from `backend/`): `python -m pytest -q` and (repo root) `npm --prefix frontend run build`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-04-item-label-xai-design.md
git commit -m "Docs: XAI sub-project 1 (item labels)"
```
