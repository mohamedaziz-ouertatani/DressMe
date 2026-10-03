"""
Estimate `primary_colour` for PolyVore and Fashionpedia (they have no colour label).

Why a small model and not "snap the pixels to the nearest palette colour"?
We tested the simple rule on Fashion Product, which HAS colour labels: it was
right only 25-36% of the time (black fabric photographs as dark blue-grey and
became 'navy', white in soft shadow became 'cream' / 'silver', denim became
'grey'). So we LEARN the colours instead:

  1. features = a colour histogram (in Lab space) + a few percentiles of the
     item's pixels (background removed / segmentation mask only);
  2. a gradient-boosting classifier is trained on Fashion Product images of
     the train split, with their real colour labels;
  3. it is evaluated on Fashion Product val + test (accuracy printed and saved
     to reports/colour_estimation.md);
  4. it predicts the colour of every PolyVore picture and every Fashionpedia
     item mask.

"Never guess" rule: the colour stays EMPTY when
  - the model's confidence is below MIN_CONFIDENCE, or
  - the Fashionpedia item is too small (crop < 64 px) or has no polygon mask.
`colour_confidence` is always kept, so the team can choose a stricter cut.

Open team decision (REVIEW): metallic colours (gold, silver) are not allowed
for clothes: the model's next best colour is used instead (METAL_FREE below).

Output (inside data/, so never committed):
    models/checkpoints/colour_model.joblib (the trained model, for the backend)
    data/processed/colour_estimates.csv   id, primary_colour, colour_confidence,
                                          predicted_colour (best colour before the cut)
It is read by merge_and_split.py, which fills `primary_colour` and sets
`colour_source` = estimated. Run:
    python src/estimate_colours.py      (~6 GB RAM, a few minutes)
    python src/merge_and_split.py
"""

import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
from scipy import ndimage
import joblib
from sklearn.ensemble import HistGradientBoostingClassifier

from colour_utils import rgb_to_lab
from plot_style import apply
from eda_fashionpedia import DATA_DIR as FPD_DIR, MIN_SIDE, SPLITS
from merge_and_split import bucket

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_PATH = DATA / "processed" / "colour_estimates.csv"
MODEL_PATH = ROOT / "models" / "checkpoints" / "colour_model.joblib"
REPORT_PATH = ROOT / "reports" / "colour_estimation.md"
FIG_DIR = ROOT / "reports" / "figures" / "colour"

MIN_CONFIDENCE = 0.7   # below this the colour stays empty (decided 2026-10-01: 0.7 beat 0.6 on the hand labels, 78% / 69% vs 73% / 64%)
METAL_FREE = {"top", "bottom", "dress", "outerwear", "traditional", "swimwear"}
METALS = {"gold", "silver"}
WHITE = 235            # R, G and B above this = near-white (background candidate)
THUMB = 80             # product shots are shrunk to Fashion Product's size (60x80)
MAX_PIXELS = 4000      # pixels sampled per Fashionpedia mask (speed)
# parallel processes; lower it if you get MemoryError (e.g. set DRESSME_WORKERS=4)
WORKERS = int(os.environ.get("DRESSME_WORKERS", 12))

# Lab histogram: 6 bins for lightness x 6 x 6 for the two colour axes
L_EDGES = np.linspace(0, 100, 7)
AB_EDGES = np.linspace(-80, 80, 7)


# ------------------------------------------------------------ features
def features(rgb_pixels):
    """Fixed-length colour description of a set of pixels (N x 3, RGB)."""
    lab = rgb_to_lab(rgb_pixels)
    hist, _ = np.histogramdd(lab, bins=(L_EDGES, AB_EDGES, AB_EDGES))
    hist = hist.ravel() / len(lab)
    pct = np.percentile(lab, [10, 25, 50, 75, 90], axis=0).ravel()
    return np.concatenate([hist, pct, lab.mean(axis=0), lab.std(axis=0)])


def product_features(path):
    """Product shot on white: drop the white background, keep the item."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((THUMB, THUMB))
    px = np.asarray(img).astype(int)
    near_white = (px > WHITE).all(axis=2)
    # background = near-white regions touching the border (so white parts
    # INSIDE the item, e.g. a white shirt with a dark outline, are kept)
    regions, _ = ndimage.label(near_white)
    border = np.unique(np.concatenate([regions[0], regions[-1], regions[:, 0], regions[:, -1]]))
    item = px[~np.isin(regions, border[border > 0])]
    if len(item) < 30:  # nothing left: the item itself is white-ish
        item = px.reshape(-1, 3)
    return features(item)


def photo_features(args):
    """All items of one Fashionpedia photo: pixels inside each polygon mask."""
    path, items = args
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img)
    rng = np.random.default_rng(0)
    out = []
    for item_id, polygons in items:
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        for poly in polygons:
            if len(poly) >= 6:  # at least 3 points
                draw.polygon(poly, fill=255)
        px = arr[np.asarray(mask) > 0]
        if len(px) < 100:
            continue
        if len(px) > MAX_PIXELS:
            px = px[rng.choice(len(px), MAX_PIXELS, replace=False)]
        out.append((item_id, features(px)))
    return out


def run_parallel(func, jobs, chunksize):
    with ProcessPoolExecutor(WORKERS) as ex:
        return list(ex.map(func, jobs, chunksize=chunksize))


def cached(name, compute):
    """Features take minutes: keep them in data/interim/ and reuse them.

    Delete data/interim/colour_features_*.pkl after changing features().
    Only the pixel features are reused: the rows and their labels are always
    taken from the current data/processed/<name>.csv (a mapping may have
    changed a category or dropped rows since the cache was made).
    """
    path = DATA / "interim" / f"colour_features_{name}.pkl"
    if not path.exists():
        df, X = compute()
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle((df, X), path)
        return df, X
    print(f"{name}: features read from {path.name}")
    # safe: this file is only ever written by this script, on this machine
    # (never load a .pkl that comes from someone else: it can run code)
    df, X = pd.read_pickle(path)
    current = read_processed(name, None).set_index("id")
    keep = df["id"].isin(current.index).to_numpy()
    df, X = df[keep].reset_index(drop=True), X[keep]
    for col in ["category", "primary_colour"]:   # labels may have changed
        if col in df:
            df[col] = df["id"].map(current[col])
    if name == "fashion_product":                # rows without a colour label
        has_label = (df["primary_colour"] != "").to_numpy()
        df, X = df[has_label].reset_index(drop=True), X[has_label]
    if not (current.index.isin(df["id"]) | ~needs_features(name, current)).all():
        sys.exit(f"ERROR: {name} has rows missing from {path.name}: delete it and re-run")
    return df, X


def needs_features(name, current):
    """Rows of a processed file that the cache must contain."""
    if name == "fashion_product":
        return (current["primary_colour"] != "").to_numpy()
    if name == "polyvore":
        return np.ones(len(current), bool)
    # fashionpedia: only big items; some of those have no polygon (crowd mask),
    # so a missing big item is not an error here
    return np.zeros(len(current), bool)


# ------------------------------------------------------------ datasets
def read_processed(name, cols):
    return pd.read_csv(DATA / "processed" / f"{name}.csv", dtype=str,
                       keep_default_na=False, usecols=cols)


def fashion_product_features():
    fp = read_processed("fashion_product", ["id", "image_path", "category", "primary_colour"])
    fp = fp[fp["primary_colour"] != ""].reset_index(drop=True)
    # same split as merge_and_split.py (by picture), so val/test are unseen
    md5 = [hashlib.md5((DATA / p).read_bytes()).hexdigest() for p in fp["image_path"]]
    fp["split"] = [bucket("fp_" + m) for m in md5]
    print(f"Fashion Product: features of {len(fp)} labelled images ...")
    X = np.array(run_parallel(product_features, [DATA / p for p in fp["image_path"]], 200))
    return fp, X


def polyvore_features():
    pv = read_processed("polyvore", ["id", "image_path", "category", "image_group"])
    first = pv.drop_duplicates("image_group")   # same picture -> computed once
    print(f"PolyVore: features of {len(first)} unique pictures ...")
    X = np.array(run_parallel(product_features, [DATA / p for p in first["image_path"]], 200))
    row = pd.Series(range(len(first)), index=first["image_group"])
    return pv, X[row[pv["image_group"]].to_numpy()]


def fashionpedia_features():
    fpd = read_processed("fashionpedia", ["id", "image_path", "category", "bbox_w", "bbox_h"])
    wanted = set(fpd["id"])
    big = set(fpd.loc[np.minimum(fpd["bbox_w"].astype(float),
                                 fpd["bbox_h"].astype(float)) >= MIN_SIDE, "id"])
    paths = dict(zip(fpd["id"], fpd["image_path"]))

    per_photo = {}
    for split in ["train", "val"]:
        print(f"Fashionpedia: reading {SPLITS[split][0]} ...")
        with open(FPD_DIR / SPLITS[split][0], encoding="utf-8") as f:
            anns = json.load(f)["annotations"]
        for a in anns:
            item_id = f"fpd_{split}_{a['id']}"
            # only kept items, big enough, with a polygon mask (not crowd RLE)
            if item_id in big and isinstance(a["segmentation"], list):
                per_photo.setdefault(paths[item_id], []).append((item_id, a["segmentation"]))
        del anns
    n_items = sum(len(v) for v in per_photo.values())
    print(f"Fashionpedia: features of {n_items} items in {len(per_photo)} photos "
          f"({len(wanted) - n_items} too small or without polygon: colour left empty) ...")
    jobs = [(DATA / p, items) for p, items in per_photo.items()]
    results = [r for photo in run_parallel(photo_features, jobs, 20) for r in photo]
    ids = [i for i, _ in results]
    X = np.array([x for _, x in results])
    return fpd.set_index("id").loc[ids].reset_index(), X


# ------------------------------------------------------------ model
def predict(clf, X, categories):
    """Best colour per row; metallic colours are skipped for clothes."""
    proba = clf.predict_proba(X)
    classes = np.array(clf.classes_)
    no_metal = np.isin(np.asarray(categories), list(METAL_FREE))
    proba[np.ix_(no_metal, np.isin(classes, list(METALS)))] = 0
    proba = proba / proba.sum(axis=1, keepdims=True)
    best = proba.argmax(axis=1)
    return classes[best], proba[np.arange(len(best)), best]


def check_grid(df, title, filename, n=24):
    """Crops with their estimated colour, to eyeball the quality."""
    sample = df[df["primary_colour"] != ""].sample(n, random_state=0)
    fig, axes = plt.subplots(3, 8, figsize=(16, 7))
    for ax, r in zip(axes.ravel(), sample.itertuples()):
        img = Image.open(DATA / r.image_path).convert("RGB")
        if hasattr(r, "bbox_x") and r.bbox_x != "":
            x, y, w, h = (float(v) for v in (r.bbox_x, r.bbox_y, r.bbox_w, r.bbox_h))
            img = img.crop((x, y, x + w, y + h))
        ax.imshow(img)
        ax.set_title(f"{r.category}\n→ {r.primary_colour} ({float(r.colour_confidence):.2f})",
                     fontsize=8)
        ax.axis("off")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=100)
    plt.close(fig)


def main():
    apply()  # DressMe chart colours
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    report = ["# Colour estimation (PolyVore, Fashionpedia)\n",
              "Model: gradient boosting on Lab colour histograms, trained on Fashion Product "
              "images (train split) with their real colour labels. Script: "
              "`src/estimate_colours.py`.\n"]

    # 1) train and evaluate on Fashion Product
    fp, X_fp = cached("fashion_product", fashion_product_features)
    train = (fp["split"] == "train").to_numpy()
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                         class_weight="balanced", random_state=0)
    clf.fit(X_fp[train], fp.loc[train, "primary_colour"])
    # saved for the backend (colour of uploaded photos); git-ignored
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODEL_PATH)
    truth = fp.loc[~train, "primary_colour"].to_numpy()
    pred, conf = predict(clf, X_fp[~train], fp.loc[~train, "category"])
    acc = (pred == truth).mean()
    print(f"\nFashion Product val+test accuracy: {acc:.3f} ({len(truth)} images)")
    report += ["## Accuracy on Fashion Product (val + test, unseen images)\n",
               f"- All predictions: **{100 * acc:.1f}%** on {len(truth)} images.\n",
               "| minimum confidence | colour filled | accuracy |", "|---:|---:|---:|"]
    for t in (0.0, 0.4, 0.5, 0.6, 0.7):
        keep = conf >= t
        mark = " ← used" if t == MIN_CONFIDENCE else ""
        report.append(f"| {t}{mark} | {100 * keep.mean():.0f}% | "
                      f"{100 * (pred[keep] == truth[keep]).mean():.1f}% |")
    per_colour = pd.DataFrame({"truth": truth, "ok": pred == truth, "keep": conf >= MIN_CONFIDENCE})
    per_colour = per_colour[per_colour["keep"]].groupby("truth")["ok"].agg(["mean", "size"])
    report += ["\nAccuracy per true colour (confidence ≥ "
               f"{MIN_CONFIDENCE}):\n", "| colour | images | accuracy |", "|---|---:|---:|"]
    report += [f"| {c} | {int(r['size'])} | {100 * r['mean']:.0f}% |"
               for c, r in per_colour.sort_values("size", ascending=False).iterrows()]
    report.append("\nFashion Product photos are tiny (60x80) and often show a model, so "
                  "these numbers are a rough guide. PolyVore (product shots on white) should "
                  "be similar; Fashionpedia (street photos, shadows) is probably lower: check "
                  "the grids below.\n")

    # 2) predict for PolyVore and Fashionpedia
    frames = []
    for name, (df, X) in [("PolyVore", cached("polyvore", polyvore_features)),
                          ("Fashionpedia", cached("fashionpedia", fashionpedia_features))]:
        colour, conf = predict(clf, X, df["category"])
        df["primary_colour"] = np.where(conf >= MIN_CONFIDENCE, colour, "")
        df["colour_confidence"] = conf.round(3)
        df["predicted_colour"] = colour  # before the cut: used to validate any cut later
        frames.append(df[["id", "primary_colour", "colour_confidence", "predicted_colour"]])

        filled = df["primary_colour"] != ""
        dist = df.loc[filled, "primary_colour"].value_counts(normalize=True) * 100
        print(f"{name}: colour filled for {filled.mean():.1%} of items")
        report += [f"## {name}\n",
                   f"- Colour filled for **{100 * filled.mean():.1f}%** of the "
                   f"{len(df)} items with pixels (confidence ≥ {MIN_CONFIDENCE}).",
                   "- Top colours: " + ", ".join(f"{c} {v:.1f}%" for c, v in dist.head(10).items())
                   + "\n"]
        fname = f"check_{name.lower()}.png"
        extra = read_processed(name.lower(), None)
        both = [c for c in df.columns if c in extra.columns and c != "id"]
        full = df.merge(extra.drop(columns=both), on="id")
        check_grid(full, f"{name}: estimated colour (confidence)", fname)
        report.append(f"![{name} check](figures/colour/{fname})\n")

    out = pd.concat(frames, ignore_index=True)
    out.to_csv(OUT_PATH, index=False)
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print(f"\nSaved {len(out)} rows to {OUT_PATH}\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
