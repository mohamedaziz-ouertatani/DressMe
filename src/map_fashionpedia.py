"""
Map Fashionpedia annotations to the DressMe unified schema.

One output row = one whole item (a garment, shoe, bag... worn in a photo),
with its bounding box so it can be cropped later. Items from the same photo
share an `outfit_id` (useful for outfit compatibility).

The rules live in editable CSV files in mappings/ (no rule is hard-coded here):
    fashionpedia_category.csv   category_id -> keep?, category, default sub_category
    fashionpedia_nickname.csv   nickname attribute -> sub_category, category (optional
                                move, e.g. kaftan -> traditional), usage, coverage
    fashionpedia_pattern.csv    textile pattern attribute -> pattern (with priority)
    fashionpedia_coverage.csv   length / sleeve / neckline attribute -> coverage score
    sub_category_vocabulary.csv allowed sub_category values (shared by all datasets)

How `coverage` (1 = very revealing ... 5 = fully covered) is computed:
  - scores come from the item's own length, its nickname (e.g. tank top),
    and the 'sleeve' / 'neckline' part objects linked to it;
  - a part is linked to a garment only if exactly ONE upper-body garment of
    the same photo contains it (>= 80% of the part's box). If several
    garments could own it (e.g. jacket over a top), it is not used;
  - final coverage = the LOWEST score found (the most revealing part decides);
  - `coverage_from` lists which sources were used, so the team can filter.

Not available in Fashionpedia (left empty): colour, season, style.

Output (inside data/, so never committed):
    data/processed/fashionpedia.csv

Run from the project root (needs ~6 GB RAM):
    python src/map_fashionpedia.py
"""

import sys

import numpy as np
import pandas as pd

from eda_fashionpedia import SPLITS, load_split
from eda_fashion_product import ROOT

MAP_DIR = ROOT / "mappings"
OUT_PATH = ROOT / "data" / "processed" / "fashionpedia.csv"

SLEEVE_ID, NECKLINE_ID = 31, 33
# garments that can own a sleeve / neckline: shirt, top, sweater, cardigan,
# jacket, vest, coat, dress, jumpsuit, cape
UPPER_IDS = [0, 1, 2, 3, 4, 5, 9, 10, 11, 12]
MIN_INSIDE = 0.8  # share of the part's box that must be inside the garment's box

PATTERNS = {"solid", "striped", "checked", "floral", "printed"}
CATEGORIES = {"top", "bottom", "dress", "outerwear", "shoes", "bag", "accessory", "traditional"}
USAGES = {"casual", "formal", "sport", "wedding", "eid", "work"}


def read_map(name):
    """Read a mapping CSV as text (empty cells stay empty strings)."""
    return pd.read_csv(MAP_DIR / name, dtype=str, keep_default_na=False)


def fail(msg):
    sys.exit(f"ERROR: {msg}")


def link_parts(anns, part_id):
    """Link each part (sleeve or neckline) to the one garment that contains it.

    Returns a DataFrame (part ann_id, garment ann_id) with only the parts
    that have exactly one possible owner.
    """
    parts = anns[anns["category_id"] == part_id]
    garments = anns[anns["category_id"].isin(UPPER_IDS)]
    pairs = parts.merge(garments, on="image_id", suffixes=("", "_g"))

    # intersection of the two boxes, as a share of the part's box area
    x1 = np.maximum(pairs["bbox_x"], pairs["bbox_x_g"])
    y1 = np.maximum(pairs["bbox_y"], pairs["bbox_y_g"])
    x2 = np.minimum(pairs["bbox_x"] + pairs["bbox_w"], pairs["bbox_x_g"] + pairs["bbox_w_g"])
    y2 = np.minimum(pairs["bbox_y"] + pairs["bbox_h"], pairs["bbox_y_g"] + pairs["bbox_h_g"])
    inter = (x2 - x1).clip(lower=0) * (y2 - y1).clip(lower=0)
    pairs["inside"] = inter / (pairs["bbox_w"] * pairs["bbox_h"]).clip(lower=1)

    pairs = pairs[pairs["inside"] >= MIN_INSIDE]
    n_owners = pairs.groupby("ann_id")["ann_id_g"].transform("size")
    linked = pairs[n_owners == 1][["ann_id", "ann_id_g", "attribute_ids"]]
    stats = {"parts": len(parts), "linked": len(linked),
             "ambiguous": pairs.loc[n_owners > 1, "ann_id"].nunique()}
    return linked, stats


def main():
    # --- load both labelled splits (test has no labels) ------------------
    frames, images = [], []
    for split in ["train", "val"]:
        img, ann, categories, attributes, _ = load_split(split, *SPLITS[split])
        img["image_path"] = [str((SPLITS[split][1] / f).relative_to(ROOT / "data")).replace("\\", "/")
                             for f in img["file_name"]]
        frames.append(ann)
        images.append(img)
    anns = pd.concat(frames, ignore_index=True)
    images = pd.concat(images, ignore_index=True).set_index("image_id")
    att = {a["id"]: a for a in attributes}

    # attribute names per annotation, by group
    def names(ids, group):
        return [att[i]["name"] for i in ids if att[i]["supercategory"] == group]

    # --- load rules and check they are complete and valid ----------------
    cat_map = read_map("fashionpedia_category.csv")
    cat_map["category_id"] = cat_map["category_id"].astype(int)
    cat_map = cat_map.set_index("category_id")
    nick = read_map("fashionpedia_nickname.csv").set_index("nickname")
    pat = read_map("fashionpedia_pattern.csv").set_index("attribute")
    cov = read_map("fashionpedia_coverage.csv")
    vocab = read_map("sub_category_vocabulary.csv")
    vocab_cat = dict(zip(vocab["sub_category"], vocab["category"]))

    all_nick = {a["name"] for a in attributes if a["supercategory"] == "nickname"}
    all_pat = {a["name"] for a in attributes if a["supercategory"] == "textile pattern"}
    all_len = {a["name"] for a in attributes if a["supercategory"] == "length"}
    all_neck = {a["name"] for a in attributes if a["supercategory"] == "neckline type"}
    if missing := set(range(len(categories))) - set(cat_map.index):
        fail(f"category ids with no rule: {sorted(missing)}")
    if missing := all_nick - set(nick.index):
        fail(f"nicknames with no rule: {sorted(missing)}")
    if missing := all_pat - set(pat.index):
        fail(f"textile patterns with no rule: {sorted(missing)}")
    for src, needed in [("bottom_dress", all_len), ("top", all_len),
                        ("sleeve", all_len), ("neckline", all_neck)]:
        if missing := needed - set(cov.loc[cov["applies_to"] == src, "attribute"]):
            fail(f"coverage rules for '{src}' missing: {sorted(missing)}")
    if wrong := set(pat["pattern"]) - PATTERNS:
        fail(f"patterns not in the schema: {wrong}")
    if wrong := set(nick["category"]) - CATEGORIES - {""}:
        fail(f"nickname categories not in the schema: {wrong}")
    for n, r in nick[nick["category"] != ""].iterrows():
        if vocab_cat.get(r["sub_category"]) != r["category"]:
            fail(f"nickname '{n}': sub_category '{r['sub_category']}' is not in '{r['category']}'")
    if wrong := set(nick["usage"]) - USAGES - {""}:
        fail(f"usages not in the schema: {wrong}")
    subs = set(cat_map["sub_category"]) | set(nick["sub_category"])
    if wrong := subs - set(vocab_cat) - {""}:
        fail(f"sub_categories not in sub_category_vocabulary.csv: {sorted(wrong)}")

    cov_score = {(r.applies_to, r.attribute): int(r.coverage)
                 for r in cov.itertuples() if r.coverage != ""}
    pat_rank = {a: (int(p), name) for a, p, name in
                zip(pat.index, pat["priority"], pat["pattern"])}

    # --- link sleeve and neckline parts to their garment -----------------
    sleeves, s_stats = link_parts(anns, SLEEVE_ID)
    necks, n_stats = link_parts(anns, NECKLINE_ID)
    part_scores = {}  # garment ann_id -> list of (source, score)
    for links, group, source in [(sleeves, "length", "sleeve"),
                                 (necks, "neckline type", "neckline")]:
        for r in links.itertuples():
            for name in names(r.attribute_ids, group):
                if (source, name) in cov_score:
                    part_scores.setdefault(r.ann_id_g, []).append((source, cov_score[(source, name)]))

    # --- map every whole item --------------------------------------------
    items = anns[anns["category_id"].map(cat_map["keep"]) == "yes"]
    rows, dropped_by_nick, nick_conflicts = [], 0, 0
    for a in items.itertuples():
        rule = cat_map.loc[a.category_id]
        category, sub = rule["category"], rule["sub_category"]
        usage, scores = set(), []

        # nickname: can refine sub_category, add usage / coverage, or drop the item
        garment_nicks = [n for n in names(a.attribute_ids, "nickname") if nick.loc[n, "keep"] != "ignore"]
        if any(nick.loc[n, "keep"] == "no" for n in garment_nicks):
            dropped_by_nick += 1
            continue
        nick_subs = {nick.loc[n, "sub_category"] for n in garment_nicks} - {""}
        if len(nick_subs) == 1:
            sub = nick_subs.pop()
        elif len(nick_subs) > 1:  # contradicting nicknames: unknown
            sub, nick_conflicts = "", nick_conflicts + 1
        for n in garment_nicks:
            if nick.loc[n, "usage"]:
                usage.add(nick.loc[n, "usage"])
            if nick.loc[n, "coverage"]:
                scores.append(("nickname", int(nick.loc[n, "coverage"])))

        # a nickname may move the item to another category only when its rule says
        # so (column 'category', e.g. kaftan -> traditional); otherwise a nickname
        # from another category is ignored (e.g. 'jeans' on a dress)
        moves = {nick.loc[n, "category"] for n in garment_nicks} - {""}
        if len(moves) == 1 and sub and vocab_cat.get(sub) == next(iter(moves)):
            category = moves.pop()
        if sub and vocab_cat[sub] != category:
            sub = ""

        # pattern: lowest priority number wins ('plain + floral' -> floral)
        found = [pat_rank[p] for p in names(a.attribute_ids, "textile pattern")]
        pattern = min(found)[1] if found else ""

        # coverage from the item's own length
        length_src = {"bottom": "bottom_dress", "dress": "bottom_dress",
                      "traditional": "bottom_dress", "top": "top"}.get(category)
        if length_src:
            for name in names(a.attribute_ids, "length"):
                if (length_src, name) in cov_score:
                    scores.append(("length", cov_score[(length_src, name)]))
        scores += part_scores.get(a.ann_id, [])

        img = images.loc[a.image_id]
        rows.append({
            "id": "fpd_" + a.ann_id,              # e.g. fpd_train_1234
            "image_path": img["image_path"],
            "bbox_x": round(a.bbox_x), "bbox_y": round(a.bbox_y),
            "bbox_w": round(a.bbox_w), "bbox_h": round(a.bbox_h),
            "category": category,
            "sub_category": sub,
            "primary_colour": "",                 # not in Fashionpedia
            "secondary_colour": "",
            "pattern": pattern,
            "season": "",                         # not in Fashionpedia
            "usage": "|".join(sorted(usage)),
            "style": "",                          # not in Fashionpedia
            "coverage": min(s for _, s in scores) if scores else "",
            "source": "public_dataset",
            # extra columns (not in the schema)
            "coverage_from": "|".join(sorted({src for src, _ in scores})),
            "outfit_id": "fpd_" + a.image_id,     # items of the same photo
            "dataset": "fashionpedia",
            "original_split": a.split,
            "original_label": categories[a.category_id]["name"]
                              + ("" if not garment_nicks else " / " + ", ".join(garment_nicks)),
        })

    out = pd.DataFrame(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    # --- summary ---------------------------------------------------------
    print(f"\nSaved {len(out)} items to {OUT_PATH}")
    print(f"Dropped by nickname (nightwear, swimwear...): {dropped_by_nick}; "
          f"contradicting nicknames (sub_category left empty): {nick_conflicts}")
    for label, st in [("sleeves", s_stats), ("necklines", n_stats)]:
        print(f"{label}: {st['parts']} parts, {st['linked']} linked to one garment "
              f"({100 * st['linked'] / st['parts']:.0f}%), {st['ambiguous']} ambiguous")
    print("\ncategory:\n" + out["category"].value_counts().to_string())
    clothes = out[out["category"].isin(["top", "bottom", "dress", "outerwear"])]
    for col in ["sub_category", "pattern", "usage", "coverage"]:
        known = (out[col].astype(str) != "").mean()
        known_c = (clothes[col].astype(str) != "").mean()
        print(f"{col}: known for {100 * known:.1f}% of items, {100 * known_c:.1f}% of clothes")
    print("\nsub_category:\n" + out["sub_category"].replace("", "(empty)").value_counts().to_string())
    print("\npattern:\n" + out["pattern"].replace("", "(empty)").value_counts().to_string())
    print("\ncoverage (clothes):\n" + clothes["coverage"].astype(str).replace("", "(empty)")
          .value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
