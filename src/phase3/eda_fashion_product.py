"""
EDA for the Kaggle "Fashion Product Images (Small)" dataset.

What it does:
  1. Loads styles.csv (the metadata table, one row per product).
  2. Reports size, missing values and duplicates.
  3. Checks that every row has an image (and every image has a row).
  4. Plots class balance (gender, categories, season, usage) and colour distribution.
  5. Samples images to check their resolution.
  6. Writes a short Markdown summary to reports/phase3/eda_fashion_product.md.

Run from the project root:
    python src/phase3/eda_fashion_product.py
"""

import csv
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save figures to files, no window needed
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
from plot_style import RUST, apply
from dataset_roles import role_markdown

apply()  # DressMe chart colours

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw" / "FashionProduct"
CSV_PATH = DATA_DIR / "styles.csv"
IMG_DIR = DATA_DIR / "images"
FIG_DIR = ROOT / "reports" / "phase3" / "figures" / "fashion_product"
REPORT_PATH = ROOT / "reports" / "phase3" / "eda_fashion_product.md"

FIG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- loading
def load_styles(path):
    """Load styles.csv.

    Some product names contain commas, which breaks a few rows (too many
    columns). We keep the first 9 columns and glue the rest back together
    as the product name, so no row is lost.
    """
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows, repaired = [], 0
        for row in reader:
            if len(row) > len(header):
                row = row[: len(header) - 1] + [",".join(row[len(header) - 1 :])]
                repaired += 1
            rows.append(row)
    df = pd.DataFrame(rows, columns=header)
    df = df.replace(["", "NA"], pd.NA)  # empty cells and the text "NA" both mean missing
    df["id"] = df["id"].astype(int)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    return df, repaired


def bar_plot(series, title, filename, top=None, horizontal=False):
    """Save a bar chart of value counts (optionally only the top N)."""
    counts = series.value_counts(dropna=False)
    if top:
        counts = counts.head(top)
    counts.index = counts.index.astype(str)
    height = max(4, 0.3 * len(counts)) if horizontal else 5
    fig, ax = plt.subplots(figsize=(10, height))
    if horizontal:
        counts[::-1].plot.barh(ax=ax, color=RUST)
        ax.set_xlabel("Number of products")
    else:
        counts.plot.bar(ax=ax, color=RUST)
        ax.set_ylabel("Number of products")
        plt.xticks(rotation=45, ha="right")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=120)
    plt.close(fig)
    return counts


def md_table(counts, n_total, name):
    """Turn value counts into a small Markdown table with percentages."""
    lines = [f"| {name} | count | % |", "|---|---:|---:|"]
    for value, c in counts.items():
        lines.append(f"| {value} | {c} | {100 * c / n_total:.1f} |")
    return "\n".join(lines)


def main():
    report = ["# EDA — Fashion Product Images (Small)\n"]
    report += role_markdown("fashion_product")  # what it brings + how DressMe uses it (dataset_roles.py)

    # 1. Size, missing values, duplicates ------------------------------
    df, repaired = load_styles(CSV_PATH)
    n = len(df)
    print(f"Rows: {n}  (repaired rows with commas in name: {repaired})")

    missing = df.isna().sum()
    missing = missing[missing > 0]
    dup_ids = df["id"].duplicated().sum()

    report.append("## Size and quality\n")
    report.append(f"- Products (rows): **{n}**")
    report.append(f"- Columns: {', '.join(df.columns)}")
    report.append(f"- Rows repaired (commas inside product name): {repaired}")
    report.append(f"- Duplicate ids: {dup_ids}")
    report.append("- Missing values: " + (
        ", ".join(f"`{c}` = {v}" for c, v in missing.items()) if len(missing) else "none"
    ))

    # 2. CSV rows vs image files ---------------------------------------
    image_ids = {int(p.stem) for p in IMG_DIR.glob("*.jpg")}
    csv_ids = set(df["id"])
    no_image = csv_ids - image_ids
    no_row = image_ids - csv_ids
    df = df[df["id"].isin(image_ids)]  # keep only usable products from here on
    report.append(f"- Image files: {len(image_ids)}")
    report.append(f"- Rows without image: {len(no_image)} {sorted(no_image)[:10]}")
    report.append(f"- Images without row: {len(no_row)}")
    report.append(f"- Usable products (row + image): **{len(df)}**\n")
    n = len(df)

    # 3. Class balance -------------------------------------------------
    report.append("## Class balance\n")
    for col in ["gender", "masterCategory", "season", "usage"]:
        counts = bar_plot(df[col], f"{col} distribution", f"{col}.png")
        report.append(f"### {col}\n\n![{col}](figures/fashion_product/{col}.png)\n")
        report.append(md_table(counts, n, col) + "\n")

    sub = bar_plot(df["subCategory"], "subCategory (all)", "subCategory.png", horizontal=True)
    art = bar_plot(df["articleType"], "articleType (top 40)", "articleType_top40.png",
                   top=40, horizontal=True)
    n_art = df["articleType"].nunique()
    rare = (df["articleType"].value_counts() < 50).sum()
    report.append("### subCategory\n\n![subCategory](figures/fashion_product/subCategory.png)\n")
    report.append(f"- {df['subCategory'].nunique()} sub-categories; "
                  f"largest: {sub.index[0]} ({sub.iloc[0]}), smallest: {sub.index[-1]} ({sub.iloc[-1]})\n")
    report.append("### articleType\n\n![articleType](figures/fashion_product/articleType_top40.png)\n")
    report.append(f"- {n_art} article types, {rare} of them have fewer than 50 images "
                  "(too few to train on alone: merge or drop when mapping).")
    report.append("- Top 10: " + ", ".join(f"{k} ({v})" for k, v in art.head(10).items()) + "\n")

    # Personal Care (make-up, perfume) is not clothing: drop it.
    # "Free Items" are promo gifts but still real watches, bags, sarees...
    # so they should be re-mapped using articleType instead of dropped.
    off_topic = df[df["masterCategory"].isin(["Personal Care", "Home", "Sporting Goods"])]
    free = df[df["masterCategory"] == "Free Items"]
    report.append(f"- Off-topic rows (Personal Care, Home, Sporting Goods): "
                  f"**{len(off_topic)}**: candidates to drop.")
    report.append(f"- 'Free Items' rows: {len(free)}: real clothes/accessories "
                  f"(e.g. {', '.join(free['articleType'].value_counts().head(4).index)}), "
                  "map them by articleType.\n")

    # 4. Colour distribution -------------------------------------------
    colours = bar_plot(df["baseColour"], "baseColour distribution", "baseColour.png",
                       horizontal=True)
    report.append("## Colour distribution\n")
    report.append("![baseColour](figures/fashion_product/baseColour.png)\n")
    report.append(f"- {df['baseColour'].nunique()} distinct colour names "
                  "(our unified palette has ~20, so they must be grouped).")
    report.append("- Top 10: " + ", ".join(f"{k} ({100 * v / n:.1f}%)"
                                           for k, v in colours.head(10).items()))
    report.append(f"- Black share here: {100 * (df['baseColour'] == 'Black').mean():.1f}% "
                  "(survey: black present in 84% of wardrobes).\n")

    # Year (just to know how old the catalogue is)
    years = df["year"].value_counts().sort_index()
    report.append("## Year\n")
    report.append("- " + ", ".join(f"{int(y)}: {c}" for y, c in years.items()) + "\n")

    # 5. Image resolution (sample) -------------------------------------
    random.seed(42)
    sample_ids = random.sample(sorted(df["id"]), 500)
    sizes = pd.Series([Image.open(IMG_DIR / f"{i}.jpg").size for i in sample_ids])
    modes = pd.Series([Image.open(IMG_DIR / f"{i}.jpg").mode for i in sample_ids])
    report.append("## Images (random sample of 500)\n")
    report.append("- Sizes (w x h): " + ", ".join(f"{w}x{h}: {c}"
                                                  for (w, h), c in sizes.value_counts().items()))
    report.append("- Colour modes: " + ", ".join(f"{m}: {c}" for m, c in modes.value_counts().items()))
    report.append("- All images are catalogue shots on white background: very different from "
                  "friperie phone photos, so our own photos stay in the test set.\n")

    # Grid of example images per masterCategory
    cats = df["masterCategory"].value_counts().index[:5]
    fig, axes = plt.subplots(len(cats), 6, figsize=(9, 2 * len(cats)))
    for r, cat in enumerate(cats):
        ids = df[df["masterCategory"] == cat]["id"].sample(6, random_state=0)
        for c, i in enumerate(ids):
            # convert("RGB") so grayscale images are not shown in false colours
            axes[r, c].imshow(Image.open(IMG_DIR / f"{i}.jpg").convert("RGB"))
            axes[r, c].axis("off")
        axes[r, 0].set_title(cat, loc="left", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "samples.png", dpi=120)
    plt.close(fig)
    report.append("![samples](figures/fashion_product/samples.png)\n")

    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")
    print(f"Figures saved in {FIG_DIR}")


if __name__ == "__main__":
    main()
