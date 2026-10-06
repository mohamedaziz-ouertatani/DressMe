"""
How good is the compatibility formula (with the team's weights)? Measured on
real outfits the formula never influenced:

  - PolyVore test outfits (clean ones only: no picture shared with train);
  - Fashionpedia test photos with 3+ worn items (real street outfits).

Two classic checks:
  AUC   real outfit vs the same outfit with ONE item swapped for a random
        item of the same category: how often does the real one score higher?
        0.5 = coin flip, 1 = always right.
  FITB  "fill in the blank": hide one item, offer it among 4 items of the same
        category; how often does the formula pick the real one? (chance = 25%)

Each part is also scored alone, so the team sees which part carries signal.
Structure cannot tell real from fake here (a swap keeps the category), so its
AUC is 0.5 by design: it matters when building outfits, not in this test.

A "learned reference" (logistic regression on the parts) shows which weights
the data would pick. It is a hint for the team, never applied automatically.

Try other weights quickly (nothing is saved; the report keeps the CSV weights):
    python src/phase4/evaluate_compatibility.py --weights style=0.5,colour=0.3,pattern=0.1,structure=0.1

Output:
    reports/phase4/compatibility_evaluation.md
    reports/phase4/figures/compatibility/suggested_outfits.png

Needs: dressme.csv, embeddings (embed_fashionclip.py), predicted_attributes.csv.
"""

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
import plot_style
from compatibility import PARTS, RULES, buy_advice, score_outfit, suggest_outfits
from evaluate_colour_labels import wilson
from item_images import DATA, ROOT, load_item_image
from similarity import EMB_DIR

REPORT = ROOT / "reports" / "phase4" / "compatibility_evaluation.md"
FIG_DIR = ROOT / "reports" / "phase4" / "figures" / "compatibility"
SEED = 0


# ------------------------------------------------------------------ items
def load_items():
    """Every PolyVore / Fashionpedia row as a compatibility item, plus its metadata.

    Labels come from the dataset; pattern falls back to the classifier's
    prediction when the dataset has none (PolyVore never has one).
    """
    cols = ["id", "dataset", "image_path", "bbox_x", "bbox_y", "bbox_w", "bbox_h", "category",
            "primary_colour", "pattern", "coverage", "outfit_id", "split", "outfit_split",
            "outfit_clean"]
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=cols)
    df = df[df["dataset"].isin(["polyvore", "fashionpedia"]) & (df["outfit_id"] != "")
            & ((df["split"] == "test") | (df["outfit_split"] == "test"))]   # test rows only (RAM)
    pred = pd.read_csv(DATA / "processed" / "predicted_attributes.csv", dtype=str,
                       keep_default_na=False, usecols=["id", "pred_pattern", "pred_pattern_conf"])
    df = df.merge(pred, on="id", how="left").fillna("")
    ids = pd.read_csv(EMB_DIR / "fashionclip_ids.csv", dtype=str)["id"]
    row_of = pd.Series(np.arange(len(ids)), index=ids)
    df = df[df["id"].isin(row_of.index)].reset_index(drop=True)   # items need a vector
    vecs = np.load(EMB_DIR / "fashionclip.npy", mmap_mode="r")
    V = np.asarray(vecs[np.sort(row_of[df["id"]].to_numpy())], np.float32)
    V = V[np.argsort(np.argsort(row_of[df["id"]].to_numpy()))]

    items = {}
    for k, r in enumerate(df.itertuples()):
        labelled = r.pattern != ""
        items[r.id] = {
            "id": r.id, "category": r.category, "colour": r.primary_colour,
            "pattern": r.pattern if labelled else r.pred_pattern,
            "pattern_conf": 1.0 if labelled else float(r.pred_pattern_conf or 0),
            "vector": V[k], "coverage": int(r.coverage) if r.coverage else None,
        }
    return df, items


def outfit_lists(df):
    """Test outfits as lists of item ids."""
    pv = df[(df["dataset"] == "polyvore") & (df["outfit_split"] == "test")
            & (df["outfit_clean"] == "True")]
    fpd = df[(df["dataset"] == "fashionpedia") & (df["split"] == "test")]
    out = {}
    for name, d, min_items in [("PolyVore", pv, 2), ("Fashionpedia", fpd, 3)]:
        groups = d.groupby("outfit_id")["id"].apply(list)
        out[name] = (groups[groups.str.len() >= min_items].tolist(), d)
    return out


# ------------------------------------------------------------------ checks
def part_weights(part):
    """Weights that keep only one part."""
    return {p: (1.0 if p == part else 0.0) for p in PARTS}


def make_tests(outfits, pool_df, items, rng):
    """For each outfit: a fake (one item swapped) and a FITB question (4 candidates)."""
    pool = pool_df.groupby("category")["id"].apply(list).to_dict()
    tests = []
    for outfit in outfits:
        pos = rng.integers(len(outfit))
        cat = items[outfit[pos]]["category"]
        others = [i for i in pool[cat] if i not in outfit]
        if len(others) < 3:
            continue
        wrong = list(rng.choice(others, 3, replace=False))
        fake = outfit[:pos] + [wrong[0]] + outfit[pos + 1:]
        rest = outfit[:pos] + outfit[pos + 1:]
        tests.append({"real": outfit, "fake": fake, "rest": rest,
                      "candidates": [outfit[pos]] + wrong})       # the right one is first
    return tests


def run_checks(tests, items, weights):
    """AUC (real vs fake) and FITB accuracy for one set of weights.
    Pairs where the score cannot be computed (e.g. no colours) are skipped."""
    win, fitb = [], []
    for t in tests:
        real = score_outfit([items[i] for i in t["real"]], weights=weights)
        fake = score_outfit([items[i] for i in t["fake"]], weights=weights)
        used = [p for p in PARTS if weights[p] > 0]
        if all(real["parts"][p] is None or fake["parts"][p] is None for p in used):
            continue
        win.append(1.0 if real["score"] > fake["score"] else 0.5 if real["score"] == fake["score"] else 0.0)
        scores = [score_outfit([items[i] for i in t["rest"] + [c]], weights=weights)["score"]
                  for c in t["candidates"]]
        best = max(scores)
        # ties are shared: the right answer gets 1 / (number of tied best candidates)
        fitb.append((scores[0] == best) / scores.count(best))
    return np.array(win), np.array(fitb)


def fmt(x):
    lo, hi = wilson(x.sum(), len(x))
    return f"{100 * x.mean():.1f}% ({100 * lo:.0f}–{100 * hi:.0f})"


def learned_reference(tests, items):
    """Logistic regression on part(real) - part(fake): the weights the data prefers.
    Parts that cannot be computed count as 0.5 here (reference only)."""
    rows = []
    for t in tests:
        a = score_outfit([items[i] for i in t["real"]])["parts"]
        b = score_outfit([items[i] for i in t["fake"]])["parts"]
        d = [(a[p] if a[p] is not None else 0.5) - (b[p] if b[p] is not None else 0.5) for p in PARTS]
        rows += [(d, 1), ([-x for x in d], 0)]
    X, y = np.array([r[0] for r in rows]), np.array([r[1] for r in rows])
    coef = LogisticRegression(fit_intercept=False).fit(X, y).coef_[0]
    coef = np.clip(coef, 0, None)
    return {p: round(float(c / coef.sum()), 2) if coef.sum() else 0.0 for p, c in zip(PARTS, coef)}


# ------------------------------------------------------------------ demo
def demo(df, items, rng):
    """A mock wardrobe of 40 PolyVore test items: best outfits and 'should I buy'."""
    pv = df[(df["dataset"] == "polyvore") & (df["split"] == "test")]
    plan = {"top": 10, "bottom": 7, "dress": 4, "outerwear": 4, "shoes": 7, "bag": 4, "accessory": 4}
    picked = {c: rng.choice(pv.loc[pv["category"] == c, "id"].unique(), n, replace=False)
              for c, n in plan.items()}
    wardrobe = [items[i] for ids in picked.values() for i in ids]
    meta = df.set_index("id")
    outfits = suggest_outfits(wardrobe, n=4)

    fig, axes = plt.subplots(len(outfits), 6, figsize=(9, 1.8 * len(outfits)))
    for r, o in enumerate(outfits):
        for c in range(6):
            ax = axes[r, c]
            ax.axis("off")
            if c < len(o["items"]):
                ax.imshow(load_item_image(meta.loc[o["items"][c]["id"]].to_dict()))
                ax.set_title(o["items"][c]["category"], fontsize=7)
        axes[r, 0].text(-0.15, 0.5, f"{o['score']:.0f}", transform=axes[r, 0].transAxes,
                        fontsize=13, ha="right", va="center", weight="bold")
    fig.suptitle("Mock wardrobe of 40 items: the 4 best suggested outfits (score / 100)", fontsize=10)
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "suggested_outfits.png", dpi=110)
    plt.close(fig)

    lines = ["\n## Demo: mock wardrobe\n",
             "40 PolyVore test items (10 tops, 7 bottoms, 4 dresses, 4 outerwear, 7 shoes, "
             "4 bags, 4 accessories).\n",
             "![suggested outfits](figures/compatibility/suggested_outfits.png)\n",
             "**Should I buy this?** Random test items as friperie candidates:\n",
             "| candidate | colour | verdict | good outfits where it beats what you own | best score |", "|---|---|---|---:|---:|"]
    taken = {i["id"] for i in wardrobe}
    for cat in ["top", "bottom", "shoes", "bag", "outerwear"]:
        cid = rng.choice([i for i in pv.loc[pv["category"] == cat, "id"] if i not in taken])
        adv = buy_advice(items[cid], wardrobe)
        best = adv["best"][0]["score"] if adv["best"] else 0
        lines.append(f"| {cat} | {items[cid]['colour'] or '?'} | **{adv['verdict']}** | "
                     f"{adv['good_outfits']} | {best:.0f} |")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", help="e.g. style=0.5,colour=0.3,pattern=0.1,structure=0.1")
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    df, items = load_items()
    sets = outfit_lists(df)
    tests = {name: make_tests(o, pool, items, rng) for name, (o, pool) in sets.items()}

    if args.weights:       # quick try for the team: print and stop
        w = {k: float(v) for k, v in (kv.split("=") for kv in args.weights.split(","))}
        for name, t in tests.items():
            auc, fitb = run_checks(t, items, w)
            print(f"{name}: AUC {fmt(auc)}, FITB {fmt(fitb)}")
        return

    plot_style.apply()
    report = ["# Compatibility formula: evaluation\n",
              "Weights and rules from `mappings/` (team values): "
              + ", ".join(f"{p} {RULES.weights[p]}" for p in PARTS) + ".\n",
              "AUC = how often a real outfit beats the same outfit with one item swapped for a "
              "random item of the same category (0.5 = chance). FITB = picking the hidden item "
              "among 4 of the same category (25% = chance). 95% intervals in brackets.\n"]
    for name, t in tests.items():
        report += [f"\n## {name} ({len(t):,} test outfits)\n",
                   "| weights | AUC | FITB |", "|---|---:|---:|"]
        auc, fitb = run_checks(t, items, RULES.weights)
        report.append(f"| **team weights** | **{fmt(auc)}** | **{fmt(fitb)}** |")
        for p in PARTS:
            auc, fitb = run_checks(t, items, part_weights(p))
            report.append(f"| {p} alone ({len(auc):,} outfits where it applies) | {fmt(auc)} | {fmt(fitb)} |")
        ref = learned_reference(t, items)
        auc, fitb = run_checks(t, items, ref)
        report.append(f"| learned reference: {', '.join(f'{p} {v}' for p, v in ref.items())} "
                      f"| {fmt(auc)} | {fmt(fitb)} |")
        print(f"{name} done", flush=True)

    # help for setting style_low / style_high
    sims = []
    for outfit in sets["PolyVore"][0]:
        v = np.array([items[i]["vector"] for i in outfit])
        s = v @ v.T
        sims.append(s[np.triu_indices(len(outfit), 1)].mean())
    q = np.percentile(sims, [5, 50, 95])
    report += ["\n## Style scale\n",
               f"Average FashionCLIP similarity inside real PolyVore test outfits: 5th percentile "
               f"{q[0]:.2f}, median {q[1]:.2f}, 95th percentile {q[2]:.2f}. The CSV maps "
               f"{RULES.settings['style_low']} → 0 and {RULES.settings['style_high']} → 1."]
    report += demo(df, items, rng)
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Saved {REPORT}")


if __name__ == "__main__":
    main()
