"""
EDA for Maryland PolyVore (the "Re-PolyVore" version, sorted into category folders).

How the data is organised:
    data/raw/MarylandPolyVore/Re-PolyVore/<category>/<outfit_id>_<position>.jpg
  - one folder per item category (top, pants, shoes, bag, ...)
  - <outfit_id> = the Polyvore outfit ("set") the item comes from, so items
    from different folders with the same outfit_id were styled together
  - <position> = rank of the item inside the original outfit (gaps = items
    that were removed, e.g. non-fashion items)
  - no text labels, no colours, and no official train/val/test split here

What it does:
  1. File inventory: images per category, junk files, bad file names.
  2. Reads every image once: size, colour mode, unreadable files, exact
     duplicates (same bytes = same MD5 hash).
  3. Rebuilds outfits: items per outfit, which categories appear together,
     share of "complete" outfits (clothes + shoes).
  4. Estimated colour distribution on a sample (product shots on white:
     we ignore near-white background pixels).
  5. Writes reports/phase3/eda_polyvore.md + figures in reports/phase3/figures/polyvore/.

Run from the project root (first run reads ~127k images and takes several
minutes; later runs use the cache in data/interim/):
    python src/phase3/eda_polyvore.py
"""

import hashlib
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save figures to files, no window needed
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
from plot_style import CMAP, RUST, apply

apply()  # DressMe chart colours

from colour_utils import Palette

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw" / "MarylandPolyVore" / "Re-PolyVore"
FIG_DIR = ROOT / "reports" / "phase3" / "figures" / "polyvore"
REPORT_PATH = ROOT / "reports" / "phase3" / "eda_polyvore.md"
CACHE_PATH = ROOT / "data" / "interim" / "polyvore_image_info.csv"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# <outfit_id>_<position>.jpg ; a few files are just <number>.jpg (no outfit link)
NAME_RE = re.compile(r"^(\d+)(?:_(\d+))?\.jpg$")
COLOUR_SAMPLE = 2000
WHITE = 235  # a pixel with R, G and B all above this counts as background

# Preview of how folders will map to our unified `category` (final rules
# will go in mappings/polyvore_*.csv)
FOLDER_TO_CATEGORY = {
    "top": "top", "pants": "bottom", "skirt": "bottom",
    "dress": "dress", "jumpsuit": "dress", "outwear": "outerwear",
    "shoes": "shoes", "bag": "bag",
    "bracelet": "accessory", "brooch": "accessory", "earrings": "accessory",
    "eyewear": "accessory", "gloves": "accessory", "hairwear": "accessory",
    "hats": "accessory", "necklace": "accessory", "neckwear": "accessory",
    "rings": "accessory", "watches": "accessory", "legwear": "accessory",
}
random.seed(42)


# ---------------------------------------------------------------- helpers
def bar_plot(counts, title, filename, xlabel="Number of images"):
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


def scan_files():
    """List every file; split real images from junk (desktop.ini, shortcuts, "- Copy" files)."""
    rows, junk = [], []
    for folder in sorted(p for p in DATA_DIR.iterdir() if p.is_dir()):
        for f in folder.iterdir():
            m = NAME_RE.match(f.name)
            if m and m.group(2):  # normal file, part of an outfit
                rows.append({"category": folder.name, "file": f.name,
                             "outfit_id": m.group(1), "position": int(m.group(2)),
                             "path": f})
            elif m:  # real image, but we cannot tell which outfit it belongs to
                rows.append({"category": folder.name, "file": f.name,
                             "outfit_id": None, "position": None, "path": f})
            else:
                junk.append(f"{folder.name}/{f.name}")
    return pd.DataFrame(rows), junk


def read_image_info(path):
    """Size, mode and MD5 of one image, or an error message if unreadable."""
    data = path.read_bytes()
    info = {"md5": hashlib.md5(data).hexdigest(), "bytes": len(data)}
    try:
        with Image.open(path) as im:
            im.load()  # decodes the whole image: fails on corrupt / truncated files
            info.update(width=im.size[0], height=im.size[1], mode=im.mode, error=None)
    except Exception as e:  # corrupt / truncated file
        info.update(width=None, height=None, mode=None, error=str(e)[:60])
    return info


def item_colour(path):
    """Median colour of the non-background pixels of a product shot."""
    img = np.asarray(Image.open(path).convert("RGB").resize((100, 100)))
    pixels = img.reshape(-1, 3)
    pixels = pixels[~(pixels > WHITE).all(axis=1)]  # drop white background
    if len(pixels) < 200:  # almost only white: the item itself is white
        return np.array([245, 245, 245])
    return np.median(pixels, axis=0)


def has_white_background(path):
    """True if the 4 corners of the image are near-white."""
    img = np.asarray(Image.open(path).convert("RGB"))
    corners = [img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]]
    return all((c > WHITE).all() for c in corners)


# ---------------------------------------------------------------- main
def main():
    report = ["# EDA — Maryland PolyVore (Re-PolyVore)\n"]

    # 1. Inventory -----------------------------------------------------
    df, junk = scan_files()
    n = len(df)
    print(f"{n} images, {len(junk)} junk files. Reading all images ...")

    # 2. Read every image (size, mode, hash) -----------------------------
    # This takes ~15 min, so the result is cached in data/interim/.
    # Delete the cache file to force a full re-read (e.g. after adding images).
    keys = list(zip(df["category"], df["file"]))
    cache = pd.read_csv(CACHE_PATH, dtype={"md5": str}) if CACHE_PATH.exists() else None
    if cache is not None and set(zip(cache["category"], cache["file"])) == set(keys):
        print(f"Using cached image info from {CACHE_PATH}")
        info = cache.set_index(["category", "file"]).loc[keys].reset_index(drop=True)
    else:  # no cache yet, or the files changed since it was written
        # 8 threads read files in parallel (disk access is the slow part)
        with ThreadPoolExecutor(max_workers=8) as pool:
            info = pd.DataFrame(pool.map(read_image_info, df["path"]))
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.concat([df[["category", "file"]].reset_index(drop=True), info], axis=1) \
            .to_csv(CACHE_PATH, index=False)
    df = pd.concat([df.reset_index(drop=True), info], axis=1)

    broken = df[df["error"].notna()]
    dup_groups = df[df.duplicated("md5", keep=False)].groupby("md5")
    n_dup_files = len(df) - df["md5"].nunique()  # extra copies beyond the first
    same_cat = dup_groups["category"].nunique().eq(1).sum()
    cross_cat = dup_groups["category"].nunique().gt(1).sum()

    report.append("## Size and quality\n")
    report.append(f"- Images: **{n}** in {df['category'].nunique()} category folders.")
    n_ini = sum(j.endswith("desktop.ini") for j in junk)
    others = [j for j in junk if not j.endswith("desktop.ini")]
    no_outfit = df[df["outfit_id"].isna()]
    report.append(f"- Junk files to ignore: {len(junk)}: {n_ini} Windows `desktop.ini`, "
                  + ", ".join(f"`{j}`" for j in others) + ".")
    report.append(f"- Images named without a position (`<number>.jpg`), so not linked to any "
                  f"outfit: {len(no_outfit)} ("
                  + ", ".join(f"{c}: {v}" for c, v in no_outfit["category"].value_counts().items())
                  + "). Usable for classification only.")
    report.append(f"- Unreadable / corrupt images: {len(broken)}")
    report.append(f"- Exact duplicates (same bytes): {n_dup_files} extra copies in "
                  f"{dup_groups.ngroups} groups. {same_cat} groups stay in one category "
                  "(the same product reused in several outfits); "
                  f"{cross_cat} groups span different categories (label conflicts).")
    report.append("- ⚠ When splitting train / val / test, all copies of an image must go to the "
                  "same split, otherwise the test set leaks into training.")
    report.append("- No text metadata (names, descriptions, prices), no colour labels, and no "
                  "official train/val/test split in this version.\n")

    ok = df[df["error"].isna()]
    report.append(f"- Image size: median {int(ok['width'].median())}x{int(ok['height'].median())} px; "
                  f"height is 400 px for {100 * (ok['height'] == 400).mean():.0f}% of images, "
                  f"width from {int(ok['width'].min())} to {int(ok['width'].max())} px.")
    report.append("- Colour modes: " + ", ".join(f"{m}: {c}" for m, c in ok["mode"].value_counts().items()))
    sample_paths = ok["path"].sample(500, random_state=0)
    white_bg = np.mean([has_white_background(p) for p in sample_paths])
    report.append(f"- White background (4 near-white corners, sample of 500): {100 * white_bg:.0f}%.\n")

    # Class balance
    counts = df["category"].value_counts()
    bar_plot(counts, "Images per category folder", "categories.png")
    report.append("## Class balance\n")
    report.append("![categories](figures/polyvore/categories.png)\n")
    report.append(md_table(counts, n, "folder") + "\n")
    unified = df["category"].map(FOLDER_TO_CATEGORY).value_counts()
    report.append("Preview in our unified `category` (folder → category, to be confirmed in "
                  "the mapping step):\n")
    report.append(md_table(unified, n, "category") + "\n")
    report.append("- No `traditional` items, and folder names are coarse: no sub-category "
                  "(t-shirt vs shirt, jeans vs trousers) is given. Folders also mix types: "
                  "`pants` holds shorts too, `top` holds shirt-jackets.\n")

    # 3. Outfits -------------------------------------------------------
    outfits = df.dropna(subset=["outfit_id"]).groupby("outfit_id")
    size = outfits.size()
    fig, ax = plt.subplots(figsize=(8, 4))
    size.clip(upper=12).value_counts().sort_index().plot.bar(ax=ax, color=RUST)
    ax.set_xlabel("Items per outfit (12 = 12 or more)")
    ax.set_ylabel("Outfits")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "items_per_outfit.png", dpi=120)
    plt.close(fig)

    cats_per_outfit = outfits["category"].agg(set)
    clothes = cats_per_outfit.map(
        lambda s: bool(("top" in s and {"pants", "skirt"} & s) or {"dress", "jumpsuit"} & s))
    complete = clothes & cats_per_outfit.map(lambda s: "shoes" in s)
    repeated_cat = outfits["category"].agg(lambda c: c.duplicated().any())

    report.append("## Outfits\n")
    report.append("![items per outfit](figures/polyvore/items_per_outfit.png)\n")
    report.append(f"- Outfits (unique outfit ids): **{len(size)}**")
    report.append(f"- Items per outfit: median {size.median():.0f}, mean {size.mean():.1f}, "
                  f"min {size.min()}, max {size.max()}. Outfits with a single item: "
                  f"{(size == 1).sum()} (useless for compatibility).")
    report.append(f"- Outfits with a full set of clothes (top + bottom, or dress / jumpsuit): "
                  f"{100 * clothes.mean():.1f}%; with clothes **and** shoes: "
                  f"**{100 * complete.mean():.1f}%** ({complete.sum()} outfits).")
    report.append(f"- Outfits with 2+ items of the same category (e.g. 2 bags): "
                  f"{100 * repeated_cat.mean():.1f}%.\n")

    # Co-occurrence: share of outfits containing both categories
    cats = counts.index.tolist()
    has = pd.DataFrame({c: cats_per_outfit.map(lambda s, c=c: c in s) for c in cats})
    co = (has.T.astype(int) @ has.astype(int)) / len(has)
    fig, ax = plt.subplots(figsize=(10, 9))
    im = ax.imshow(co.values * 100, cmap=CMAP)
    ax.set_xticks(range(len(cats)), cats, rotation=90)
    ax.set_yticks(range(len(cats)), cats)
    fig.colorbar(im, ax=ax, label="% of outfits containing both")
    ax.set_title("Which categories appear together in an outfit")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "cooccurrence.png", dpi=120)
    plt.close(fig)
    presence = has.mean().sort_values(ascending=False)
    report.append("![co-occurrence](figures/polyvore/cooccurrence.png)\n")
    report.append("- Share of outfits containing each category: "
                  + ", ".join(f"{c} {100 * v:.0f}%" for c, v in presence.head(8).items()) + "\n")

    # 4. Estimated colours ----------------------------------------------
    print(f"Estimating colours on {COLOUR_SAMPLE} images ...")
    palette = Palette()
    sample = ok.sample(COLOUR_SAMPLE, random_state=1).copy()
    sample["median_rgb"] = [item_colour(p) for p in sample["path"]]
    sample["colour"] = sample["median_rgb"].map(palette.nearest)
    col_counts = sample["colour"].value_counts()
    bar_plot(col_counts, f"Estimated colour of {COLOUR_SAMPLE} sampled items",
             "colour_estimate.png", xlabel="Number of items")
    clothes_cats = ["top", "pants", "skirt", "dress", "jumpsuit", "outwear"]
    cloth_sample = sample[sample["category"].isin(clothes_cats)]
    report.append("## Colour distribution (estimated)\n")
    report.append("![colours](figures/polyvore/colour_estimate.png)\n")
    report.append(f"- Median colour of the non-white pixels of {COLOUR_SAMPLE} random images, "
                  "snapped to the nearest colour of `mappings/colour_palette.csv`.")
    report.append("- All items: " + ", ".join(f"{k} ({100 * v / len(sample):.1f}%)"
                                              for k, v in col_counts.head(8).items()))
    cc = cloth_sample["colour"].value_counts()
    report.append(f"- Clothes only ({len(cloth_sample)} items): "
                  + ", ".join(f"{k} ({100 * v / len(cloth_sample):.1f}%)" for k, v in cc.head(8).items()))
    report.append("- Product shots on white give cleaner estimates than Fashionpedia's street "
                  "photos, but white items are hard to separate from the background, and "
                  "jewellery comes out as gold/silver/grey. Check the grid below.")
    report.append("- Main systematic error: white and very light items (white sandals, light "
                  "blue socks) land on `silver`, which inflates silver. Metallic colours "
                  "(silver, gold) should probably only be allowed for shoes, bags and "
                  "jewellery: a team decision for the colour step.\n")

    check = sample.sample(24, random_state=0)
    fig, axes = plt.subplots(4, 6, figsize=(12, 9))
    for ax, (_, r) in zip(axes.flat, check.iterrows()):
        ax.imshow(Image.open(r["path"]).convert("RGB"))
        # small swatch in the corner = the median colour measured
        ax.add_patch(mpatches.Rectangle((0.8, 0.8), 0.2, 0.2, transform=ax.transAxes,
                                        color=np.array(r["median_rgb"]) / 255))
        ax.set_title(f"{r['category']}\n→ {r['colour']}", fontsize=8)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "colour_check.png", dpi=110)
    plt.close(fig)
    report.append("![colour check](figures/polyvore/colour_check.png)\n")

    # 5. Example outfits -----------------------------------------------
    examples = complete[complete].sample(5, random_state=3).index
    width = int(size[examples].max())
    fig, axes = plt.subplots(5, width, figsize=(1.6 * width, 9))
    for r, oid in enumerate(examples):
        items = df[df["outfit_id"] == oid].sort_values("position")
        for c in range(width):
            ax = axes[r, c]
            ax.axis("off")
            if c < len(items):
                it = items.iloc[c]
                ax.imshow(Image.open(it["path"]).convert("RGB"))
                ax.set_title(it["category"], fontsize=8)
    fig.suptitle("Example complete outfits (one row = one outfit)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "example_outfits.png", dpi=100)
    plt.close(fig)
    report.append("## Example outfits\n\n![outfits](figures/polyvore/example_outfits.png)\n")
    report.append("- Polyvore outfits were composed by users, so they are real examples of "
                  "items that go together: the main training source for outfit compatibility.\n")

    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
