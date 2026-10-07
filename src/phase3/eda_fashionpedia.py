"""
EDA for Fashionpedia (street / runway photos, COCO-style annotations).

Important differences with the Kaggle dataset:
  - One image contains SEVERAL objects (a whole outfit), each with a mask + bbox.
  - Categories 0-26 are whole items (shirt, pants, shoe...), 27-45 are garment
    PARTS (sleeve, pocket, zipper...) that we will not classify.
  - Each object has fine-grained attributes (pattern, length, silhouette...).
  - There is NO colour label: we estimate colour from the pixels on a sample.

What it does:
  1. Size and quality per split (train / val), images present on disk.
  2. Class balance of items and parts, items per image.
  3. Attribute coverage, with focus on the groups we can map:
     textile pattern -> pattern, length -> coverage, nickname -> sub_category.
  4. Bounding-box sizes (tiny crops are useless for classification).
  5. Estimated colour distribution on a sample of item masks.
  6. Writes reports/phase3/eda_fashionpedia.md + figures in reports/phase3/figures/fashionpedia/.

Run from the project root (needs ~6 GB RAM, the train JSON is 542 MB):
    python src/phase3/eda_fashionpedia.py
"""

import json
import random
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save figures to files, no window needed
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
from plot_style import DARK, RUST, apply

apply()  # DressMe chart colours

from colour_utils import Palette
from dataset_roles import role_markdown

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw" / "Fashionpedia"
SPLITS = {
    # split name: (annotation file, image folder)
    "train": ("instances_attributes_train2020.json", DATA_DIR / "train2020" / "train"),
    # the validation images are stored in the "test" folder of the val/test zip
    "val": ("instances_attributes_val2020.json",
            DATA_DIR / "validation_and_test_images_2020" / "test"),
}
TEST_INFO = DATA_DIR / "info_test2020.json"  # image list only, no labels
FIG_DIR = ROOT / "reports" / "phase3" / "figures" / "fashionpedia"
REPORT_PATH = ROOT / "reports" / "phase3" / "eda_fashionpedia.md"
FIG_DIR.mkdir(parents=True, exist_ok=True)

LAST_ITEM_ID = 26         # category ids 0..26 are whole items, 27..45 are parts
COLOUR_SAMPLE = 2000      # number of item masks used for the colour estimate
MIN_SIDE = 64             # crops smaller than this (px) are too small to classify
random.seed(42)


# ---------------------------------------------------------------- loading
def load_split(split, json_name, img_dir, keep_seg_prob=0.0):
    """Load one annotation file into two DataFrames (images, annotations).

    Segmentation masks are huge, so we only keep them for a random fraction
    of whole-item annotations (keep_seg_prob), used later for the colour estimate.
    """
    print(f"Loading {json_name} ...")
    with open(DATA_DIR / json_name, encoding="utf-8") as f:
        raw = json.load(f)

    # ids restart at 0 in each JSON file, so we prefix them with the split
    # name ("train_12", "val_12") to keep them unique after concatenation
    on_disk = {p.name for p in img_dir.glob("*.jpg")}
    images = pd.DataFrame([{
        "split": split, "image_id": f"{split}_{im['id']}", "file_name": im["file_name"],
        "width": im["width"], "height": im["height"],
        "on_disk": im["file_name"] in on_disk,
    } for im in raw["images"]])

    rows, segs = [], {}
    for a in raw["annotations"]:
        x, y, w, h = a["bbox"]
        rows.append({
            "split": split, "ann_id": f"{split}_{a['id']}", "image_id": f"{split}_{a['image_id']}",
            "category_id": a["category_id"], "attribute_ids": a["attribute_ids"],
            "bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h, "area": a["area"], "iscrowd": a["iscrowd"],
            "seg_is_polygon": isinstance(a["segmentation"], list),
        })
        # keep a few polygon masks for the colour estimate: clothes only
        # (ids 0-12), large enough, since small crops (glasses, open shoes)
        # are mostly skin or background
        if (a["category_id"] <= 12 and min(w, h) >= MIN_SIDE
                and isinstance(a["segmentation"], list)
                and random.random() < keep_seg_prob):
            segs[f"{split}_{a['id']}"] = (f"{split}_{a['image_id']}", a["segmentation"])

    anns = pd.DataFrame(rows)
    return images, anns, raw["categories"], raw["attributes"], segs


# ---------------------------------------------------------------- helpers
def bar_plot(counts, title, filename, xlabel="Number of objects"):
    """Save a horizontal bar chart of a value_counts() Series."""
    counts.index = counts.index.astype(str)
    fig, ax = plt.subplots(figsize=(10, max(4, 0.3 * len(counts))))
    counts[::-1].plot.barh(ax=ax, color=RUST)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=120)
    plt.close(fig)


def md_table(counts, total, name):
    """Value counts -> Markdown table with percentages."""
    lines = [f"| {name} | count | % |", "|---|---:|---:|"]
    for value, c in counts.items():
        lines.append(f"| {value} | {c} | {100 * c / total:.1f} |")
    return "\n".join(lines)


def estimate_colours(segs, images, cat_names):
    """Median colour inside each sampled mask -> nearest palette colour.

    This is only an ESTIMATE: lighting, shadows and multicolour items all
    push the median towards grey/brown. Good enough to see the distribution.
    """
    palette = Palette()

    files = images.set_index("image_id")["file_name"]
    img_dir = SPLITS["train"][1]
    results = []
    for ann_id, (image_id, polygons) in list(segs.items())[:COLOUR_SAMPLE]:
        img = Image.open(img_dir / files[image_id]).convert("RGB")
        mask = Image.new("L", img.size, 0)
        for poly in polygons:
            if len(poly) >= 6:  # at least 3 points
                ImageDraw.Draw(mask).polygon(poly, fill=255)
        pixels = np.asarray(img)[np.asarray(mask) > 0]
        if len(pixels) < 100:  # mask too small to trust
            continue
        median = np.median(pixels, axis=0)
        results.append({"ann_id": ann_id, "image_id": image_id,
                        "colour": palette.nearest(median),
                        "median_rgb": median.astype(int)})
    return pd.DataFrame(results)


# ---------------------------------------------------------------- main
def main():
    report = ["# EDA — Fashionpedia\n"]
    report += role_markdown("fashionpedia")  # what it brings + how DressMe uses it (dataset_roles.py)

    # Load train (with a sample of masks for colours) and val
    keep_prob = 1.5 * COLOUR_SAMPLE / 80_000  # ~80k large clothes in train; a bit more than needed
    img_tr, ann_tr, categories, attributes, segs = load_split(
        "train", *SPLITS["train"], keep_seg_prob=keep_prob)
    img_va, ann_va, _, _, _ = load_split("val", *SPLITS["val"])
    images = pd.concat([img_tr, img_va], ignore_index=True)
    anns = pd.concat([ann_tr, ann_va], ignore_index=True)
    del ann_tr, ann_va

    cat = {c["id"]: c for c in categories}
    att = {a["id"]: a for a in attributes}
    anns["category"] = anns["category_id"].map(lambda i: cat[i]["name"])
    anns["is_item"] = anns["category_id"] <= LAST_ITEM_ID
    items = anns[anns["is_item"]]
    parts = anns[~anns["is_item"]]

    # 1. Size and quality ----------------------------------------------
    with open(TEST_INFO, encoding="utf-8") as f:
        n_test = len(json.load(f)["images"])
    report.append("## Size and quality\n")
    report.append("| split | images | images on disk | objects | whole items | parts |")
    report.append("|---|---:|---:|---:|---:|---:|")
    for split in ["train", "val"]:
        im = images[images["split"] == split]
        an = anns[anns["split"] == split]
        report.append(f"| {split} | {len(im)} | {im['on_disk'].sum()} | {len(an)} | "
                      f"{an['is_item'].sum()} | {(~an['is_item']).sum()} |")
    report.append(f"| test | {n_test} | – | no labels (public test set) | – | – |\n")

    no_ann = set(images["image_id"]) - set(anns["image_id"])
    no_item = set(images["image_id"]) - set(items["image_id"])
    no_attr = (items["attribute_ids"].str.len() == 0).mean()
    report.append(f"- Categories: {len(categories)} "
                  f"({LAST_ITEM_ID + 1} whole items, {len(categories) - LAST_ITEM_ID - 1} parts); "
                  f"attributes: {len(attributes)} in "
                  f"{len(set(a['supercategory'] for a in attributes))} groups.")
    report.append(f"- Images with no annotation: {len(no_ann)}; with no whole item: {len(no_item)}.")
    report.append(f"- Whole items with no attribute at all: {100 * no_attr:.1f}% "
                  "(mostly shoes and accessories; clothes are well annotated, see below).")
    report.append(f"- Masks stored as compressed RLE (crowd) instead of polygons: "
                  f"{(~anns['seg_is_polygon']).sum()} ({100 * (~anns['seg_is_polygon']).mean():.1f}%).")
    report.append("- **No colour label** in Fashionpedia: colour must be estimated from pixels "
                  "(see below) or predicted by a model.\n")

    # Image sizes
    report.append(f"- Image size: median {int(images['width'].median())}x"
                  f"{int(images['height'].median())} px, "
                  f"min short side {int(images[['width', 'height']].min(axis=1).min())} px, "
                  f"max long side {int(images[['width', 'height']].max(axis=1).max())} px.\n")

    # 2. Class balance --------------------------------------------------
    item_counts = items["category"].value_counts()
    bar_plot(item_counts, "Whole items per category (train + val)", "items.png")
    bar_plot(parts["category"].value_counts(), "Garment parts per category", "parts.png")
    img_per_cat = items.groupby("category")["image_id"].nunique().sort_values(ascending=False)
    report.append("## Class balance\n")
    report.append("### Whole items\n\n![items](figures/fashionpedia/items.png)\n")
    table = pd.DataFrame({"objects": item_counts, "images": img_per_cat})
    report.append("| category | objects | % | images containing it |")
    report.append("|---|---:|---:|---:|")
    for name, r in table.iterrows():
        report.append(f"| {name} | {r['objects']} | {100 * r['objects'] / len(items):.1f} "
                      f"| {r['images']} |")
    report.append("")
    report.append("### Garment parts\n\n![parts](figures/fashionpedia/parts.png)\n")
    report.append(f"- Shoes are labelled one per foot ({item_counts['shoe']} shoe objects in "
                  f"{img_per_cat['shoe']} images), so they look bigger than they are.\n")
    neck = parts[parts["category"] == "neckline"]
    report.append(f"- {len(parts)} part objects (sleeve, neckline, pocket...). Not classes for "
                  "DressMe, but useful for `coverage`: neckline types (v-neck, off-the-shoulder...) "
                  f"are attached to the {len(neck)} 'neckline' part objects, not to the garment "
                  "itself, and 'sleeve' parts carry the sleeve length. They must be linked back "
                  "to their garment (same image, overlapping box) during mapping.\n")

    # Items per image
    per_img = items.groupby("image_id").size()
    fig, ax = plt.subplots(figsize=(8, 4))
    per_img.clip(upper=15).value_counts().sort_index().plot.bar(ax=ax, color=RUST)
    ax.set_xlabel("Whole items per image (15 = 15 or more)")
    ax.set_ylabel("Images")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "items_per_image.png", dpi=120)
    plt.close(fig)
    report.append("### Items per image\n\n![items per image](figures/fashionpedia/items_per_image.png)\n")
    report.append(f"- Median {per_img.median():.0f}, mean {per_img.mean():.1f}, max {per_img.max()} "
                  "items per image: each image is a full outfit, useful for outfit compatibility.\n")

    # 3. Attributes -----------------------------------------------------
    report.append("## Attributes\n")
    exploded = items[["ann_id", "category", "attribute_ids"]].explode("attribute_ids").dropna()
    exploded["attribute"] = exploded["attribute_ids"].map(lambda i: att[i]["name"])
    exploded["group"] = exploded["attribute_ids"].map(lambda i: att[i]["supercategory"])

    # How many items have at least one attribute of each group
    cover = exploded.groupby("group")["ann_id"].nunique().sort_values(ascending=False)
    report.append("Share of whole items with at least one attribute of each group:\n")
    report.append(md_table(cover, len(items), "attribute group") + "\n")

    # Groups that map to our schema
    for group, fname, schema in [
        ("textile pattern", "pattern.png", "`pattern`"),
        ("length", "length.png", "`coverage` (with neckline / sleeve)"),
        ("nickname", "nickname_top30.png", "`sub_category`"),
        ("silhouette", "silhouette.png", "style hints (fit)"),
    ]:
        counts = exploded[exploded["group"] == group]["attribute"].value_counts()
        bar_plot(counts.head(30), f"{group} attributes (whole items)", fname)
        n_items = exploded[exploded["group"] == group]["ann_id"].nunique()
        report.append(f"### {group} → {schema}\n\n![{group}](figures/fashionpedia/{fname})\n")
        report.append(f"- {len(counts)} values used, on {n_items} items "
                      f"({100 * n_items / len(items):.1f}% of whole items).")
        report.append("- Top 10: " + ", ".join(f"{k} ({v})" for k, v in counts.head(10).items()) + "\n")

    # Pattern coverage for clothes only (shoes/bags rarely get a pattern)
    clothes_ids = set(range(0, 13))  # shirt ... cape
    clothes = items[items["category_id"].isin(clothes_ids)]
    with_pattern = exploded[(exploded["group"] == "textile pattern")
                            & exploded["ann_id"].isin(clothes["ann_id"])]["ann_id"].nunique()
    report.append(f"- Clothes (categories 0-12) with a textile pattern attribute: "
                  f"{100 * with_pattern / len(clothes):.1f}%. The others have no pattern info.\n")

    # 4. Bounding-box sizes ---------------------------------------------
    short_side = items[["bbox_w", "bbox_h"]].min(axis=1)
    small = (short_side < MIN_SIDE).mean()
    small_by_cat = (items.assign(small=short_side < MIN_SIDE)
                    .groupby("category")["small"].mean().sort_values(ascending=False))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(short_side.clip(upper=600), bins=60, color=RUST)
    ax.axvline(MIN_SIDE, color=DARK, linestyle="--", label=f"{MIN_SIDE} px")
    ax.set_xlabel("Shorter side of the item's bounding box (px, clipped at 600)")
    ax.set_ylabel("Items")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "bbox_short_side.png", dpi=120)
    plt.close(fig)
    report.append("## Item crop sizes\n")
    report.append("![bbox](figures/fashionpedia/bbox_short_side.png)\n")
    report.append(f"- Items with a crop shorter than {MIN_SIDE} px: **{100 * small:.1f}%**: "
                  "probably too small to classify, candidates to drop.")
    report.append("- Most affected: " + ", ".join(f"{k} ({100 * v:.0f}%)"
                                                  for k, v in small_by_cat.head(6).items()) + "\n")

    # 5. Estimated colours ----------------------------------------------
    print(f"Estimating colours on {min(len(segs), COLOUR_SAMPLE)} item masks ...")
    colours = estimate_colours(segs, img_tr, cat)
    col_counts = colours["colour"].value_counts()
    bar_plot(col_counts, f"Estimated colour of {len(colours)} sampled items", "colour_estimate.png",
             xlabel="Number of items")
    report.append("## Colour distribution (estimated)\n")
    report.append("![colours](figures/fashionpedia/colour_estimate.png)\n")
    report.append(f"- Median pixel colour inside {len(colours)} random masks of clothes "
                  f"(categories 0-12, crop ≥ {MIN_SIDE} px), "
                  "snapped to the nearest colour of `mappings/colour_palette.csv` (Lab distance).")
    report.append("- Top: " + ", ".join(f"{k} ({100 * v / len(colours):.1f}%)"
                                        for k, v in col_counts.head(8).items()))
    report.append(f"- Black share: {100 * col_counts.get('black', 0) / len(colours):.1f}% "
                  "(Kaggle catalogue: 21.9%; survey: black in 84% of wardrobes).")
    report.append("- Only an estimate: shadows and prints push colours towards grey/brown, "
                  "white in shadow often becomes 'silver' or 'grey', "
                  "and 'multicolour' can never be predicted this way. "
                  "Check the sample grid below before trusting it.\n")

    # Visual check: crops with their estimated colour
    files = img_tr.set_index("image_id")["file_name"]
    boxes = anns.set_index("ann_id")
    check = colours.sample(min(24, len(colours)), random_state=0)
    fig, axes = plt.subplots(4, 6, figsize=(12, 9))
    for ax, (_, r) in zip(axes.flat, check.iterrows()):
        b = boxes.loc[r["ann_id"]]
        img = Image.open(SPLITS["train"][1] / files[r["image_id"]]).convert("RGB")
        ax.imshow(img.crop((b["bbox_x"], b["bbox_y"],
                            b["bbox_x"] + b["bbox_w"], b["bbox_y"] + b["bbox_h"])))
        # small swatch in the corner = the median colour measured inside the mask
        ax.add_patch(mpatches.Rectangle((0.8, 0.8), 0.2, 0.2, transform=ax.transAxes,
                                        color=np.array(r["median_rgb"]) / 255))
        ax.set_title(f"{cat[b['category_id']]['name'].split(',')[0]}\n→ {r['colour']}", fontsize=8)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "colour_check.png", dpi=110)
    plt.close(fig)
    report.append("![colour check](figures/fashionpedia/colour_check.png)\n")

    # Example images
    fig, axes = plt.subplots(2, 5, figsize=(14, 7))
    for ax, fname in zip(axes.flat, img_tr.sample(10, random_state=1)["file_name"]):
        ax.imshow(Image.open(SPLITS["train"][1] / fname).convert("RGB"))
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "samples.png", dpi=100)
    plt.close(fig)
    report.append("## Example images\n\n![samples](figures/fashionpedia/samples.png)\n")
    report.append("- Street and runway photos of people wearing outfits: much closer to real "
                  "life than the Kaggle catalogue shots, but items must be cropped out first.\n")

    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
