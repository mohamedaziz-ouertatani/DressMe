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
from PIL import Image

from colour_utils import PALETTE_PATH, Palette
from item_images import ROOT, letterbox

SETTINGS_PATH = ROOT / "mappings" / "xai_settings.csv"
FIELDS = ["category", "sub_category", "pattern", "colour"]
SIZE = 224          # the classifier's input size (classifier.SIZE)


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
