"""
Are the item-label explanations honest? (XAI sub-project 1)

On the test split of the image cache:
  1. calibration of the "unsure" flag (mappings/xai_settings.csv): accuracy of
     sure vs unsure answers, and accuracy per confidence bucket, per field;
  2. deletion test: whiten the hottest 10 / 20 / 40% of the item's pixels
     (Grad-CAM) vs the same share of random item pixels. If the heatmap shows
     what the model uses, its confidence drops faster with the heatmap;
  3. a figure of Grad-CAM examples, right and wrong answers.
-> reports/phase4/explanations_evaluation.md + reports/phase4/figures/gradcam_examples.png

    python src/phase4/evaluate_explanations.py [--limit 2000]

Colour is not here: its cut was chosen in reports/phase3/colour_estimation.md.
"""

import argparse
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from PIL import Image

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
import explain
import plot_style
from build_image_cache import PACK
from classifier import HEADS, TO_TENSOR, decode, load_classifier, predict_tensors
from estimate_colours import item_pixels_mask
from item_images import ROOT
from train_classifier import batches, load_table

REPORT = ROOT / "reports" / "phase4" / "explanations_evaluation.md"
FIGURE = ROOT / "reports" / "phase4" / "figures" / "gradcam_examples.png"
SHARES = [0.1, 0.2, 0.4]
BUCKETS = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]


def calibration(test, model, device):
    """Accuracy of sure / unsure answers, per field, on the whole test split."""
    answers = []
    for x, _ in batches(test, device, train=False, batch=128):     # same order as `test`
        answers += decode(predict_tensors(x, model, device))
    settings = explain.load_settings()
    rows, buckets = [], []
    for head in HEADS:
        truth = test[head].to_numpy()
        has = truth != ""
        pred = np.array([a[head] for a in answers])
        conf = np.array([a["top3"][head][0]["conf"] if a["top3"][head] else 0 for a in answers])
        unsure = np.array([explain.is_unsure(head, a["top3"][head], settings) for a in answers])
        ok = pred == truth
        for name, keep in (("sure", has & ~unsure), ("unsure", has & unsure)):
            rows.append({"field": head, "group": name, "pictures": int(keep.sum()),
                         "share": float(keep.sum() / max(has.sum(), 1)),
                         "accuracy": float(ok[keep].mean()) if keep.any() else float("nan")})
        for lo, hi in zip(BUCKETS[:-1], BUCKETS[1:]):
            keep = has & (conf >= lo) & (conf < hi)
            buckets.append({"field": head, "confidence": f"{lo:.1f}-{min(hi, 1):.1f}", "pictures": int(keep.sum()),
                            "accuracy": float(ok[keep].mean()) if keep.any() else float("nan")})
    return pd.DataFrame(rows), pd.DataFrame(buckets)


def whitened(px, pixels):
    out = px.copy()
    out[pixels] = 255
    return Image.fromarray(out.astype(np.uint8))


def deletion(pictures, model, device, rng):
    """Mean confidence drop of the predicted class: heatmap pixels vs random pixels."""
    rows = []
    for k, img in enumerate(pictures):
        if k % 500 == 0:
            print(f"  deletion {k:,} / {len(pictures):,}", flush=True)
        px = np.asarray(img).astype(int)
        item = item_pixels_mask(px)
        if item.sum() < 100:             # nearly all white: nothing to remove
            continue
        base = predict_tensors(TO_TENSOR(img).unsqueeze(0), model, device)
        coords = np.argwhere(item)
        for head in HEADS:
            cls = int(base[head][0].argmax())
            heat = explain.gradcam(model, img, head, cls, device)
            order = np.argsort(-heat[item])                         # hottest item pixels first
            # fair baseline: the same smooth heatmap moved by half the picture, so a
            # solid region of the same size in the wrong place (scattered random pixels
            # look like noise, which this model never saw: see the report)
            shifted = np.argsort(-np.roll(heat, (112, 112), axis=(0, 1))[item])
            variants = []
            for share in SHARES:
                n = int(share * len(coords))
                masks = [np.zeros_like(item) for _ in range(3)]
                masks[0][tuple(coords[order[:n]].T)] = True
                masks[1][tuple(coords[shifted[:n]].T)] = True
                masks[2][tuple(coords[rng.choice(len(coords), n, replace=False)].T)] = True
                variants += [whitened(px, m) for m in masks]
            p = predict_tensors(torch.stack([TO_TENSOR(v) for v in variants]), model, device)[head][:, cls]
            p0 = base[head][0, cls]
            for i, share in enumerate(SHARES):
                rows.append({"field": head, "share": share, "heatmap": float(p0 - p[3 * i]),
                             "shifted_region": float(p0 - p[3 * i + 1]),
                             "scattered_pixels": float(p0 - p[3 * i + 2])})
    cols = ["heatmap", "shifted_region", "scattered_pixels"]
    out = pd.DataFrame(rows).groupby(["field", "share"])[cols].mean().reset_index()
    out["beats_shifted"] = out["heatmap"] > out["shifted_region"]
    out["beats_scattered"] = out["heatmap"] > out["scattered_pixels"]
    return out


def examples_figure(sample, pictures, answers, model, device):
    """Two rows: right answers, wrong answers (category head), one per category when possible."""
    right, wrong = [], []
    for i, (truth, a) in enumerate(zip(sample["category"], answers)):
        if truth == "":
            continue
        target = right if a["category"] == truth else wrong
        if len(target) < 6 and all(sample["category"].iloc[j] != truth for j in target):
            target.append(i)
    plot_style.apply()
    fig, axes = plt.subplots(2, 6, figsize=(16, 6.5))
    for ax_row, chosen, title in zip(axes, (right, wrong), ("right", "wrong")):
        for ax, i in zip(ax_row, chosen + [None] * 6):
            ax.axis("off")
            if i is None:
                continue
            cls = HEADS["category"].index(answers[i]["category"])
            heat = explain.gradcam(model, pictures[i], "category", cls, device)
            ax.imshow(explain.overlay(pictures[i], heat))
            ax.set_title(f"{title}: {answers[i]['category']}\n(true {sample['category'].iloc[i]})", fontsize=9)
    fig.suptitle("Grad-CAM, category head: where the model looked")
    fig.tight_layout()
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, dpi=100)
    plt.close(fig)


def table(df):
    def fmt(v):
        return f"{v:.3f}" if isinstance(v, float) else str(v)
    lines = ["| " + " | ".join(df.columns) + " |",
             "|" + "|".join("---" if df[c].dtype == object else "---:" for c in df.columns) + "|"]
    return "\n".join(lines + ["| " + " | ".join(fmt(v) for v in r) + " |" for r in df.itertuples(index=False)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2000, help="pictures for the deletion test")
    args = parser.parse_args()
    rng = np.random.default_rng(0)
    model, device = load_classifier()
    df = load_table()
    test = df[df["split"] == "test"].reset_index(drop=True)
    print(f"calibration on {len(test):,} test pictures ...", flush=True)
    sure, buckets = calibration(test, model, device)

    sample = test.sample(min(args.limit, len(test)), random_state=0).reset_index(drop=True)
    pack = np.memmap(PACK, dtype=np.uint8, mode="r")
    pictures = [Image.open(io.BytesIO(pack[o:o + n].tobytes())).convert("RGB")
                for o, n in zip(sample["offset"], sample["length"])]
    print(f"deletion test on {len(sample):,} pictures ...", flush=True)
    drops = deletion(pictures, model, device, rng)
    head = min(256, len(pictures))
    answers = decode(predict_tensors(torch.stack([TO_TENSOR(p) for p in pictures[:head]]), model, device))
    examples_figure(sample.head(head), pictures[:head], answers, model, device)

    lines = ["# Item-label explanations: evaluation", "",
             f"Test split of the image cache. Calibration on {len(test):,} pictures, "
             f"deletion test on {len(sample):,}. Thresholds from `mappings/xai_settings.csv` (REVIEW). "
             "Made by `src/phase4/evaluate_explanations.py`.", "",
             "## 1. Is the \"not sure, check\" flag honest?", "",
             "Accuracy of the answers the app shows as sure vs unsure (pictures with a label only). "
             "A useful flag catches answers that are much less accurate than the sure ones.", "",
             table(sure), "", "Accuracy per confidence bucket:", "", table(buckets), "",
             "## 2. Deletion test", "",
             "Mean drop of the predicted class's confidence after whitening a share of the item's "
             "pixels, three ways: the hottest Grad-CAM pixels (`heatmap`); the same heatmap moved by "
             "half the picture, i.e. a solid region of the same size in the wrong place "
             "(`shifted_region`); and scattered random item pixels (`scattered_pixels`). A bigger drop "
             "with the heatmap means it points at what the model really uses.", "",
             table(drops), "",
             "How to read it: whitening a solid region leaves a smaller item on white, which looks like "
             "the product shots the model was trained on; scattered white pixels cover the whole item "
             "with noise it never saw, so they lower the confidence for a reason unrelated to WHERE the "
             "model looks. `shifted_region` is the fair comparison; `scattered_pixels` is kept because it "
             "was the test planned first, and it shows that the model is sensitive to pixel noise.", "",
             "## 3. Examples", "", "![Grad-CAM examples](figures/gradcam_examples.png)", "",
             "All three heads share one body, so a heatmap shows where the model looked to decide, "
             "not the outline of a part."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
