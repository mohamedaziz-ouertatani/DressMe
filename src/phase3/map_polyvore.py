"""
Map Maryland PolyVore (Re-PolyVore) to the DressMe unified schema.

One output row = one product image. The only label PolyVore gives is its
category folder, so the rules are short:
    mappings/polyvore_folder.csv       folder -> keep?, category, sub_category
    mappings/sub_category_vocabulary.csv  allowed sub_category values (shared)

Also handled here:
  - outfits: items with the same <outfit_id> in their file name were styled
    together; kept in `outfit_id` (empty for the few files without one);
  - exact duplicates: `image_group` = MD5 hash of the file. Rows with the same
    image_group are the same picture and MUST end up in the same
    train / val / test split;
  - label conflicts: the same picture found in two different category
    folders. We cannot know which folder is right, so all copies are dropped.

Not available in PolyVore (left empty): colour, pattern, season, usage,
style, coverage.

Needs the image info cache written by the EDA (hash of every image):
    python src/phase3/eda_polyvore.py      (once)
    python src/phase3/map_polyvore.py

Output (inside data/, so never committed):
    data/processed/polyvore.csv
"""

import sys

import pandas as pd

from eda_polyvore import CACHE_PATH, ROOT, scan_files

MAP_DIR = ROOT / "mappings"
OUT_PATH = ROOT / "data" / "processed" / "polyvore.csv"


def read_map(name):
    """Read a mapping CSV as text (empty cells stay empty strings)."""
    return pd.read_csv(MAP_DIR / name, dtype=str, keep_default_na=False)


def main():
    # --- files + cached hashes ----------------------------------------
    df, junk = scan_files()
    if not CACHE_PATH.exists():
        sys.exit(f"ERROR: {CACHE_PATH} not found. Run: python src/phase3/eda_polyvore.py")
    info = pd.read_csv(CACHE_PATH, dtype={"md5": str})
    df = df.merge(info[["category", "file", "md5", "error"]], on=["category", "file"], how="left")
    if df["md5"].isna().any():
        sys.exit("ERROR: some images are not in the cache (files changed?). "
                 "Re-run: python src/phase3/eda_polyvore.py")
    df = df.rename(columns={"category": "folder"})
    print(f"{len(df)} images ({len(junk)} junk files ignored)")

    n_broken = df["error"].notna().sum()
    df = df[df["error"].isna()]

    # --- load rules and check they are complete and valid ----------------
    rules = read_map("polyvore_folder.csv").set_index("folder")
    vocab = read_map("sub_category_vocabulary.csv")
    vocab_cat = dict(zip(vocab["sub_category"], vocab["category"]))
    if missing := set(df["folder"]) - set(rules.index):
        sys.exit(f"ERROR: folders with no rule: {sorted(missing)}")
    kept = rules[rules["keep"] == "yes"]
    if wrong := set(kept["sub_category"]) - set(vocab_cat) - {""}:
        sys.exit(f"ERROR: sub_categories not in sub_category_vocabulary.csv: {sorted(wrong)}")
    for folder, r in kept.iterrows():
        if r["sub_category"] and vocab_cat[r["sub_category"]] != r["category"]:
            sys.exit(f"ERROR: folder '{folder}': sub_category '{r['sub_category']}' "
                     f"belongs to '{vocab_cat[r['sub_category']]}', not '{r['category']}'")

    # --- apply rules -----------------------------------------------------
    n_before = len(df)
    df = df[df["folder"].map(rules["keep"]) == "yes"].copy()
    n_dropped_folder = n_before - len(df)
    df["category"] = df["folder"].map(rules["category"])
    df["sub_category"] = df["folder"].map(rules["sub_category"])

    # label conflicts: same picture, different unified categories -> drop all copies.
    # (same picture in 'pants' and 'skirt' is also a conflict: sub_category differs)
    labels = df.groupby("md5")[["category", "sub_category"]].nunique()
    conflict = labels[(labels["category"] > 1) | (labels["sub_category"] > 1)].index
    n_conflict = df["md5"].isin(conflict).sum()
    df = df[~df["md5"].isin(conflict)]

    out = pd.DataFrame({
        "id": "pv_" + df["folder"] + "_" + df["file"].str.removesuffix(".jpg"),
        "image_path": [str(p.relative_to(ROOT / "data")).replace("\\", "/") for p in df["path"]],
        "category": df["category"],
        "sub_category": df["sub_category"],
        "primary_colour": "",   # not in PolyVore
        "secondary_colour": "",
        "pattern": "",
        "season": "",
        "usage": "",
        "style": "",
        "coverage": "",
        "source": "public_dataset",
        # extra columns (not in the schema)
        "outfit_id": ("pv_" + df["outfit_id"]).where(df["outfit_id"].notna(), ""),
        "position": df["position"].astype("Int64"),
        "image_group": df["md5"],  # same value = same picture: keep in one split
        "dataset": "polyvore",
        "original_label": df["folder"],
    })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    # --- summary ---------------------------------------------------------
    outfits = out[out["outfit_id"] != ""].groupby("outfit_id")
    sizes = outfits.size()
    print(f"Dropped: {n_broken} unreadable, {n_dropped_folder} by folder rule (legwear), "
          f"{n_conflict} in label conflicts ({len(conflict)} pictures)")
    print(f"\nSaved {len(out)} rows to {OUT_PATH}")
    print(f"Unique pictures (image_group): {out['image_group'].nunique()}")
    print(f"Outfits: {len(sizes)} ({(sizes >= 2).sum()} with 2+ items); "
          f"rows without outfit: {(out['outfit_id'] == '').sum()}")
    print("\ncategory:\n" + out["category"].value_counts().to_string())
    print("\nsub_category:\n" + out["sub_category"].replace("", "(empty)").value_counts().to_string())


if __name__ == "__main__":
    main()
