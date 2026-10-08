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
