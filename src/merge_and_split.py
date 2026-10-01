"""
Merge the three processed datasets into one file and add train / val / test splits.

Inputs (made by the map_*.py scripts):
    data/processed/fashion_product.csv
    data/processed/fashionpedia.csv
    data/processed/polyvore.csv
Output (inside data/, so never committed):
    data/processed/dressme.csv

Two split columns, because we train two kinds of models:

  `split`         for CLASSIFICATION (one row = one image / crop).
                  All copies of the same picture (same `image_group`) are in
                  the same split, so the test set never leaks into training.
  `outfit_split`  for OUTFIT COMPATIBILITY (only rows with an `outfit_id`).
                  All items of an outfit share the same outfit_split.

Why two columns? In PolyVore the same product is reused in many outfits, and
those outfits share other products, and so on: 61% of PolyVore rows form one
long chain. Keeping every chain inside one split is impossible, so:
  - outfits are split first (80 / 10 / 10);
  - a picture used in a test outfit goes to test, else in a val outfit -> val,
    else train. So every test outfit is 100% test pictures;
  - a train outfit may still contain a picture that is in val / test
    (the same product styled in two outfits). `outfit_clean` = False marks
    those outfits; use only clean val / test outfits for a strict evaluation.

Other rules:
  - the split of a group is decided by a hash of its id, so it never changes
    when the script is re-run or when new rows are added;
  - local photos (source = wardrobe / friperie) always go to test;
  - `duplicate` = True for the 2nd, 3rd... copy of the same picture: drop those
    rows when training a classifier (they add nothing);
  - colours estimated by estimate_colours.py (PolyVore, Fashionpedia) are
    filled in if data/processed/colour_estimates.csv exists. `colour_source`
    says where each colour comes from: label (real) or estimated.

Run:
    python src/estimate_colours.py   (optional, fills the missing colours)
    python src/merge_and_split.py
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT_PATH = PROCESSED / "dressme.csv"
COLOUR_PATH = PROCESSED / "colour_estimates.csv"

SEED = "dressme-2026"          # change it only if the team wants a new random split
SHARES = {"train": 80, "val": 10}  # percent; the rest (10) goes to test
LOCAL_SOURCES = {"wardrobe", "friperie"}  # our own photos: test only
CATEGORIES = {"top", "bottom", "dress", "outerwear", "shoes", "bag", "accessory",
              "traditional", "swimwear"}

# the unified schema first, then the extra columns, in this order
COLUMNS = ["id", "dataset", "image_path", "bbox_x", "bbox_y", "bbox_w", "bbox_h",
           "category", "sub_category", "primary_colour", "colour_source", "colour_confidence",
           "secondary_colour", "pattern",
           "season", "usage", "style", "coverage", "coverage_from", "source", "gender",
           "outfit_id", "position", "image_group", "duplicate",
           "split", "outfit_split", "outfit_clean", "original_split", "original_label"]


def bucket(key):
    """Deterministic split for a group id: same key -> same split, every run."""
    n = int(hashlib.md5(f"{SEED}:{key}".encode()).hexdigest()[:8], 16) % 100
    if n < SHARES["train"]:
        return "train"
    if n < SHARES["train"] + SHARES["val"]:
        return "val"
    return "test"


def load():
    """Read the three processed files and give every row an image_group."""
    read = lambda name: pd.read_csv(PROCESSED / f"{name}.csv", dtype=str,
                                    keep_default_na=False)

    # Fashion Product: image_group (file MD5) is made by map_fashion_product.py
    fp = read("fashion_product")

    # Fashionpedia: all items cropped from one photo share that photo
    fpd = read("fashionpedia")
    fpd["image_group"] = fpd["outfit_id"]

    # PolyVore: image_group is already the file MD5
    pv = read("polyvore")
    pv["image_group"] = "pv_" + pv["image_group"]

    df = pd.concat([fp, fpd, pv], ignore_index=True).fillna("")

    # colours: real labels first, then the estimates (if they were computed)
    df["colour_source"] = (df["primary_colour"] != "").map({True: "label", False: ""})
    df["colour_confidence"] = ""
    if COLOUR_PATH.exists():
        est = pd.read_csv(COLOUR_PATH, dtype=str, keep_default_na=False).set_index("id")
        todo = (df["primary_colour"] == "") & df["id"].isin(est.index)
        df.loc[todo, "primary_colour"] = df.loc[todo, "id"].map(est["primary_colour"])
        df.loc[todo, "colour_confidence"] = df.loc[todo, "id"].map(est["colour_confidence"])
        df.loc[todo & (df["primary_colour"] != ""), "colour_source"] = "estimated"
    else:
        print(f"  no {COLOUR_PATH.name}: PolyVore / Fashionpedia colours stay empty")
    for col in COLUMNS:
        if col not in df:
            df[col] = ""
    return df


def assign_splits(df):
    rank = {"train": 0, "val": 1, "test": 2}   # stricter split wins
    name = {v: k for k, v in rank.items()}

    # 1) outfits
    has_outfit = df["outfit_id"] != ""
    outfits = pd.Series(df.loc[has_outfit, "outfit_id"].unique())
    outfit_split = dict(zip(outfits, outfits.map(bucket)))
    df["outfit_split"] = df["outfit_id"].map(outfit_split).fillna("")

    # 2) pictures: strictest split among their outfits, else their own hash
    in_outfits = (df[has_outfit].assign(r=df["outfit_split"].map(rank))
                  .groupby("image_group")["r"].max().map(name))
    groups = pd.Series(df["image_group"].unique())
    group_split = dict(zip(groups, groups.map(bucket)))
    group_split.update(in_outfits.to_dict())
    df["split"] = df["image_group"].map(group_split)

    # 3) our own photos: test only
    df.loc[df["source"].isin(LOCAL_SOURCES), "split"] = "test"

    # 4) clean outfit = none of its pictures is used by an outfit of another split
    used = df[has_outfit].groupby("image_group")["outfit_split"].nunique()
    shared = set(used[used > 1].index)
    dirty = set(df.loc[has_outfit & df["image_group"].isin(shared), "outfit_id"])
    df["outfit_clean"] = ""
    df.loc[has_outfit, "outfit_clean"] = ~df.loc[has_outfit, "outfit_id"].isin(dirty)

    # 5) duplicates (same file twice); Fashionpedia groups are photos, not copies
    same_file = df["dataset"] != "fashionpedia"
    df["duplicate"] = same_file & df.duplicated("image_group")
    return df


def check(df):
    """Stop if a rule is broken, so a bad file is never saved."""
    if df["id"].duplicated().any():
        sys.exit(f"ERROR: duplicate ids: {df.loc[df['id'].duplicated(), 'id'].head().tolist()}")
    if bad := set(df["category"]) - CATEGORIES:
        sys.exit(f"ERROR: categories outside the schema: {sorted(bad)}")
    if (df.groupby("image_group")["split"].nunique() > 1).any():
        sys.exit("ERROR: a picture is in two splits (leak)")
    with_outfit = df[df["outfit_id"] != ""]
    if (with_outfit.groupby("outfit_id")["outfit_split"].nunique() > 1).any():
        sys.exit("ERROR: an outfit is in two outfit splits")
    test_outfits = with_outfit[with_outfit["outfit_split"] == "test"]
    if (test_outfits["split"] != "test").any():
        sys.exit("ERROR: a test outfit contains a non-test picture")
    if (df.loc[df["source"].isin(LOCAL_SOURCES), "split"] != "test").any():
        sys.exit("ERROR: a local photo is outside the test set")


def summary(df):
    pct = lambda s: (s * 100).round(1)
    print(f"\nSaved {len(df)} rows to {OUT_PATH}")
    print(f"Duplicate copies (drop for classification): {df['duplicate'].sum()}")

    print("\nColour source per dataset (% of rows):")
    print((pd.crosstab(df["dataset"], df["colour_source"].replace("", "(empty)"),
                       normalize="index") * 100).round(1).to_string())

    print("\nRows per dataset and split (all rows):")
    print(pd.crosstab(df["dataset"], df["split"], margins=True).to_string())

    uniq = df[~df["duplicate"]]
    print("\nSplit share per category (% of unique pictures / crops):")
    print(pct(pd.crosstab(uniq["category"], uniq["split"], normalize="index")).to_string())

    o = df[df["outfit_id"] != ""].drop_duplicates("outfit_id")
    print("\nOutfits per outfit_split (clean = shares no picture with another split):")
    print(pd.crosstab((o["dataset"] + " / " + o["outfit_split"]).rename("outfits"),
                      o["outfit_clean"].map({True: "clean", False: "shared"}))
          .rename_axis(columns=None).to_string())


def main():
    df = assign_splits(load())
    df = df[COLUMNS]
    check(df)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    summary(df)


if __name__ == "__main__":
    main()
