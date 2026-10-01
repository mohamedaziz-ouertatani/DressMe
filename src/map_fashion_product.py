"""
Map the Kaggle "Fashion Product Images (Small)" labels to the DressMe unified schema.

The rules live in editable CSV files in mappings/ (no rule is hard-coded here):
    fashion_product_articletype.csv       articleType -> keep?, category, sub_category
    fashion_product_colour.csv            baseColour  -> primary_colour
    fashion_product_season.csv            season      -> season
    fashion_product_usage.csv             usage       -> usage
    fashion_product_pattern_keywords.csv  words in productDisplayName -> pattern
    colour_palette.csv                    the ~20 allowed colours (shared by all datasets)
    sub_category_vocabulary.csv           allowed sub_category values (shared by all datasets)

Duplicates: some pictures appear under two product ids. `image_group` = MD5
hash of the file (same value = same picture, must stay in one split). A
picture found twice with a different category / sub_category is a label
conflict: all its copies are dropped (same rule as PolyVore).

Output (inside data/, so never committed):
    data/processed/fashion_product.csv

Run from the project root:
    python src/map_fashion_product.py
"""

import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

from eda_fashion_product import CSV_PATH, IMG_DIR, ROOT, load_styles

MAP_DIR = ROOT / "mappings"
OUT_PATH = ROOT / "data" / "processed" / "fashion_product.csv"

# Whole master categories that are never clothing: dropped before mapping
DROP_MASTER = ["Personal Care", "Home", "Sporting Goods"]

# Allowed values of the unified schema (see CLAUDE.md)
CATEGORIES = {"top", "bottom", "dress", "outerwear", "shoes", "bag", "accessory", "traditional"}
PATTERNS = {"solid", "striped", "checked", "floral", "printed"}
SEASONS = {"summer", "winter", "mid-season"}
USAGES = {"casual", "formal", "sport", "wedding", "eid", "work"}


def read_map(name):
    """Read a mapping CSV as text (so 'NA' etc. stay as plain strings)."""
    return pd.read_csv(MAP_DIR / name, dtype=str, keep_default_na=False)


def check_covered(values, mapping_keys, what):
    """Stop with a clear message if a source value has no mapping rule."""
    missing = sorted(set(values.dropna()) - set(mapping_keys))
    if missing:
        sys.exit(f"ERROR: {what} values with no rule in mappings/: {missing}")


def check_allowed(values, allowed, what):
    """Stop if a mapping file uses a value that is not in the unified schema."""
    wrong = sorted(set(values) - allowed - {""})
    if wrong:
        sys.exit(f"ERROR: {what} values not in the unified schema: {wrong}")


def find_pattern(name, keywords):
    """Return the pattern of the first keyword (by priority) found in the product name."""
    if pd.isna(name):
        return pd.NA
    words = name.lower()
    for kw, pattern in keywords:
        if re.search(rf"\b{kw}\b", words):
            return pattern
    return pd.NA  # unknown: do NOT assume solid


def main():
    df, _ = load_styles(CSV_PATH)

    # Keep only rows that have an image
    image_ids = {int(p.stem) for p in IMG_DIR.glob("*.jpg")}
    df = df[df["id"].isin(image_ids)]
    n_start = len(df)
    df = df[~df["masterCategory"].isin(DROP_MASTER)]
    print(f"{n_start} products with image, {len(df)} after dropping {DROP_MASTER}")

    # --- load rules and check they are complete and valid ---------------
    art = read_map("fashion_product_articletype.csv").set_index("articleType")
    colour = read_map("fashion_product_colour.csv").set_index("baseColour")["primary_colour"]
    season = read_map("fashion_product_season.csv").set_index("season_source")["season"]
    usage = read_map("fashion_product_usage.csv").set_index("usage_source")["usage"]
    kw = read_map("fashion_product_pattern_keywords.csv")
    kw = kw.sort_values("priority", key=lambda s: s.astype(int))
    keywords = list(zip(kw["keyword"].str.lower(), kw["pattern"]))
    palette = set(read_map("colour_palette.csv")["colour"])

    check_covered(df["articleType"], art.index, "articleType")
    check_covered(df["baseColour"], colour.index, "baseColour")
    check_covered(df["season"], season.index, "season")
    check_covered(df["usage"], usage.index, "usage")
    check_allowed(art["category"], CATEGORIES, "category")
    vocab = read_map("sub_category_vocabulary.csv")
    check_allowed(art["sub_category"], set(vocab["sub_category"]), "sub_category")
    check_allowed(colour, palette, "colour")
    check_allowed(season, SEASONS, "season")
    check_allowed(usage, USAGES, "usage")
    check_allowed(kw["pattern"], PATTERNS, "pattern")

    # --- apply rules ---------------------------------------------------
    df = df[df["articleType"].map(art["keep"]) == "yes"].copy()
    print(f"{len(df)} products kept after the articleType rules")

    out = pd.DataFrame({
        "id": "fp_" + df["id"].astype(str),  # prefix avoids id clashes between datasets
        "image_path": "raw/FashionProduct/images/" + df["id"].astype(str) + ".jpg",
        "category": df["articleType"].map(art["category"]),
        "sub_category": df["articleType"].map(art["sub_category"]),
        "primary_colour": df["baseColour"].map(colour),
        "secondary_colour": pd.NA,       # not in this dataset
        "pattern": df["productDisplayName"].map(lambda s: find_pattern(s, keywords)),
        "season": df["season"].map(season),   # multi-value fields use "|" as separator
        "usage": df["usage"].map(usage),
        "style": pd.NA,                  # not in this dataset
        "coverage": pd.NA,               # not in this dataset
        "source": "public_dataset",
        # extra columns (not in the schema) kept for splits and debugging
        "gender": df["gender"],
        "dataset": "fashion_product",
        "original_label": df["articleType"],
    })

    # --- duplicates and label conflicts ------------------------------------
    out["image_group"] = ["fp_" + hashlib.md5((ROOT / "data" / p).read_bytes()).hexdigest()
                          for p in out["image_path"]]
    labels = out.groupby("image_group")[["category", "sub_category"]].nunique()
    conflict = labels[(labels > 1).any(axis=1)].index
    n_conflict = out["image_group"].isin(conflict).sum()
    out = out[~out["image_group"].isin(conflict)]
    print(f"Dropped {n_conflict} rows: same picture with different labels "
          f"({len(conflict)} pictures)")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    # --- summary -------------------------------------------------------
    print(f"\nSaved {len(out)} rows to {OUT_PATH}\n")
    print("category:\n" + out["category"].value_counts().to_string() + "\n")
    print(f"sub_category: {out['sub_category'].nunique()} values")
    print("\nprimary_colour:\n" + out["primary_colour"].value_counts(dropna=False).to_string())
    print("\npattern:\n" + out["pattern"].value_counts(dropna=False).to_string())
    print("\nmissing per column:\n" + out.isna().sum().to_string())


if __name__ == "__main__":
    main()
