"""
Allowed values of every field, read from the same CSVs as the data pipeline
(mappings/), so the app and the models always speak the same schema.
"""

import csv

from .config import ROOT

MAP_DIR = ROOT / "mappings"


def _rows(name):
    with open(MAP_DIR / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


CATEGORIES = ["top", "bottom", "dress", "outerwear", "shoes", "bag", "accessory",
              "traditional", "swimwear"]
SUB_PARENT = {r["sub_category"]: r["category"] for r in _rows("sub_category_vocabulary.csv")}
PATTERNS = ["solid", "striped", "checked", "floral", "printed"]
COLOURS = [r["colour"] for r in _rows("colour_palette.csv")]
SEASONS = ["summer", "winter", "mid-season"]
USAGES = ["casual", "formal", "sport", "wedding", "eid", "work"]
LANGUAGES = ["fr", "ar", "en"]
