"""
Map the H&M product catalogue (Kaggle "H&M Personalized Fashion
Recommendations", articles.csv) to the DressMe unified schema.

H&M is our "shop" catalogue: real retail products the app can suggest
("buy something like this"). It replaces scraping, which the shops block
(team decision 2026-10-03). It is NOT merged into dressme.csv: it is not
training data, it is what the user could buy.

The rules live in editable CSV files in mappings/ (no rule is hard-coded here):
    hm_index_group.csv       index_group_name  -> keep?, usage, gender (Baby/Children dropped)
    hm_product_type.csv      product_type_name -> keep?, category, sub_category
    hm_refine_rules.csv      another column fixes the label (denim trousers -> jeans)
    hm_colour.csv            colour_group_name -> primary_colour
    hm_pattern.csv           graphical_appearance_name -> pattern, use_keywords?
    hm_pattern_keywords.csv  words in the name / description -> pattern
                             (only where hm_pattern.csv says use_keywords=yes)

One row per article (= one product in one colour). `product_code` groups the
colours of the same product. There is no price in articles.csv.

Input:  data/raw/HM/articles.csv (download: see the "H&M" section of CLAUDE.md)
Output: data/processed/hm.csv

Run from the project root:
    python src/phase3/map_hm.py
"""

import re

import pandas as pd

from map_fashion_product import (CATEGORIES, PATTERNS, ROOT, USAGES, check_allowed,
                                 check_covered, read_map)

HM_DIR = ROOT / "data" / "raw" / "HM"
OUT_PATH = ROOT / "data" / "processed" / "hm.csv"


def image_path(article_id):
    """Where src/phase3/fetch_hm_images.py saves the (resized) picture of an article."""
    return f"raw/HM/images/{article_id}.jpg"


def find_pattern(text, keywords):
    """Pattern of the first keyword (by priority) found in the text, else empty."""
    words = text.lower()
    for kw, pattern in keywords:
        if re.search(rf"\b{kw}\b", words):
            return pattern
    return ""


def main():
    df = pd.read_csv(HM_DIR / "articles.csv", dtype=str, keep_default_na=False)
    print(f"{len(df)} articles in articles.csv")

    # --- load rules and check they are complete and valid ---------------
    groups = read_map("hm_index_group.csv").set_index("index_group_name")
    types = read_map("hm_product_type.csv").set_index("product_type_name")
    refine = read_map("hm_refine_rules.csv")
    colour = read_map("hm_colour.csv").set_index("colour_group_name")["primary_colour"]
    pattern = read_map("hm_pattern.csv").set_index("graphical_appearance_name")
    kw = read_map("hm_pattern_keywords.csv")
    kw = kw.sort_values("priority", key=lambda s: s.astype(int))
    keywords = list(zip(kw["keyword"].str.lower(), kw["pattern"]))
    palette = set(read_map("colour_palette.csv")["colour"])
    vocab = set(read_map("sub_category_vocabulary.csv")["sub_category"])

    check_covered(df["index_group_name"], groups.index, "index_group_name")
    df = df[df["index_group_name"].map(groups["keep"]) == "yes"].copy()
    print(f"{len(df)} after the index group rules (children dropped)")

    check_covered(df["product_type_name"], types.index, "product_type_name")
    check_covered(df["colour_group_name"], colour.index, "colour_group_name")
    check_covered(df["graphical_appearance_name"], pattern.index, "graphical_appearance_name")
    for rules in (types, refine):
        check_allowed(rules["category"], CATEGORIES, "category")
        check_allowed(rules["sub_category"], vocab, "sub_category")
    check_allowed(colour, palette, "colour")
    check_allowed(pattern["pattern"], PATTERNS, "pattern")
    check_allowed(kw["pattern"], PATTERNS, "pattern")
    check_allowed(groups["usage"], USAGES, "usage")

    # --- apply rules ---------------------------------------------------
    df = df[df["product_type_name"].map(types["keep"]) == "yes"].copy()
    print(f"{len(df)} after the product type rules")
    df["category"] = df["product_type_name"].map(types["category"])
    df["sub_category"] = df["product_type_name"].map(types["sub_category"])
    for r in refine.itertuples():
        hit = (df["product_type_name"] == r.product_type_name) & (df[r.column] == r.value)
        df.loc[hit, ["category", "sub_category"]] = [r.category, r.sub_category]
        print(f"  refine rule '{r.product_type_name} + {r.value}': {hit.sum()} rows")

    # pattern: from the appearance, or from words in the text where it is unclear
    df["pattern"] = df["graphical_appearance_name"].map(pattern["pattern"])
    unclear = df["graphical_appearance_name"].map(pattern["use_keywords"]) == "yes"
    from_text = (df["prod_name"] + " " + df["detail_desc"]).map(
        lambda t: find_pattern(t, keywords))
    df.loc[unclear & (from_text != ""), "pattern"] = from_text

    out = pd.DataFrame({
        "id": "hm_" + df["article_id"],     # prefix avoids id clashes between datasets
        "image_path": df["article_id"].map(image_path),
        "category": df["category"],
        "sub_category": df["sub_category"],
        "primary_colour": df["colour_group_name"].map(colour),
        "secondary_colour": "",          # not in this dataset
        "pattern": df["pattern"],
        "season": "",                    # not in this dataset
        "usage": df["index_group_name"].map(groups["usage"]),
        "style": "",                     # not in this dataset
        "coverage": "",                  # not in this dataset
        "source": "",                    # no value for shop items yet (team decision)
        # Ladieswear / Menswear; empty (Divided, Sport) = decided later by the team's
        # table of men's / women's pieces (src/phase4/genders.py)
        "gender": df["index_group_name"].map(groups["gender"]),
        # extra columns, shown in the app or kept for debugging
        "name": df["prod_name"],
        "description": df["detail_desc"],
        "product_code": df["product_code"],
        "department": df["index_group_name"] + " / " + df["section_name"],
        "dataset": "hm",
        "original_label": df["product_type_name"],
        "original_colour": df["colour_group_name"],
        "original_pattern": df["graphical_appearance_name"],
    })
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    # --- summary -------------------------------------------------------
    print(f"\nSaved {len(out)} rows to {OUT_PATH}\n")
    print("category:\n" + out["category"].value_counts().to_string() + "\n")
    print(f"sub_category: {out['sub_category'].nunique()} values, "
          f"{(out['sub_category'] == '').sum()} empty")
    print("\nprimary_colour:\n" + out["primary_colour"].value_counts().to_string())
    print("\npattern:\n" + out["pattern"].value_counts().to_string())


if __name__ == "__main__":
    main()
