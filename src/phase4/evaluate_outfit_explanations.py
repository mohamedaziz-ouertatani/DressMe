"""
Does "weakest piece" find the piece that does not belong? (XAI sub-project 2)

On the clean PolyVore and Fashionpedia test outfits (the data of
evaluate_compatibility.py): replace one piece by a random test item of the same
category (the intruder); the swap analysis, with a pool of POOL random test items
per category as the "wardrobe", should name the intruder as the weakest piece.
Reported: top-1 accuracy vs chance (1 / number of pieces), per dataset. Also
checks that the points per part add up to the score on every outfit.
-> reports/phase4/outfit_explanations_evaluation.md

    python src/phase4/evaluate_outfit_explanations.py [--limit 500]
"""

import argparse

import numpy as np

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
import explain_outfit as X
from compatibility import RULES, score_outfit
from evaluate_compatibility import load_items, outfit_lists
from item_images import ROOT

REPORT = ROOT / "reports" / "phase4" / "outfit_explanations_evaluation.md"
POOL = 30          # random candidates per category for the swaps (keeps it fast)
SEED = 0


def run(outfits, pool_df, items, rng, limit):
    pool = pool_df.groupby("category")["id"].apply(list).to_dict()
    hits, chance, sums_ok, n = [], [], 0, 0
    for outfit in outfits[:limit]:
        pos = int(rng.integers(len(outfit)))
        cat = items[outfit[pos]]["category"]
        others = [i for i in pool[cat] if i not in outfit]
        if not others:
            continue
        intruder = str(rng.choice(others))
        fake = outfit[:pos] + [intruder] + outfit[pos + 1:]
        fake_items = [items[i] for i in fake]
        # the "wardrobe" for the swaps: random test items of the outfit's categories
        # (never the piece that was taken out: that would make it too easy)
        cands = []
        for c in sorted({items[i]["category"] for i in fake}):
            ids = [i for i in pool[c] if i not in fake and i != outfit[pos]]
            cands += [items[i] for i in rng.choice(ids, min(POOL, len(ids)), replace=False)]
        swaps = X.swaps(fake_items, cands, RULES)
        hits.append(X.weakest(swaps, positive_only=False) == intruder)
        chance.append(1 / len(fake))
        result = score_outfit(fake_items)
        sums_ok += round(sum(c["points"] for c in X.contributions(result, RULES.weights)), 1) == result["score"]
        n += 1
    return np.array(hits, float), np.array(chance), sums_ok, n


def ci(x):
    """Mean and 95% normal interval, in %."""
    m = x.mean()
    h = 1.96 * np.sqrt(m * (1 - m) / len(x)) if len(x) else 0
    return f"{100 * m:.1f}% [{100 * (m - h):.1f}, {100 * (m + h):.1f}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500, help="test outfits per dataset")
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    df, items = load_items()
    lines = ["# Outfit explanations: evaluation", "",
             "Made by `src/phase4/evaluate_outfit_explanations.py`. One piece of each test outfit is "
             f"replaced by a random test item of the same category; the swap analysis (pool: {POOL} random "
             "test items per category) should name that intruder as the weakest piece.", "",
             "| dataset | outfits | weakest = intruder | chance | points add up |", "|---|---:|---:|---:|---:|"]
    for name, (outfits, pool_df) in outfit_lists(df).items():
        print(f"{name}: {min(args.limit, len(outfits)):,} outfits ...", flush=True)
        hits, chance, sums_ok, n = run(outfits, pool_df, items, rng, args.limit)
        lines.append(f"| {name} | {n:,} | {ci(hits)} | {100 * chance.mean():.1f}% | {sums_ok:,} / {n:,} |")
    lines += ["", "Chance = 1 / number of pieces (mean over the outfits). The intruder is random, "
              "so it can fit by luck: 100% is not expected. A result well above chance means the "
              "swap analysis points at the piece that breaks the outfit.", "",
              "How to read it: the swap analysis only re-uses the score, so it can point at an intruder "
              "only as well as the score itself tells a real outfit from one with a swapped piece "
              "(AUC in `reports/phase4/compatibility_evaluation.md`). A modest gain over chance here means "
              "the explanation is faithful to the formula, and that the formula's own signal is limited; "
              "improving it is a team decision on the weights and rules, not a change to the explanation."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
