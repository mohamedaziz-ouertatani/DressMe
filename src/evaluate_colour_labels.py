"""
Real accuracy of the colour model on PolyVore and Fashionpedia, measured on the
hand-labelled items made by make_colour_labelling_sheet.py.

Input:
    data/interim/colour_labelling/colour_labels.csv   (filled: true_colour column)
    data/processed/colour_estimates.csv               (model output)
Output:
    reports/colour_validation.csv   one row per dataset x confidence cut
                                    (read by build_phase3_report.py)
    reports/colour_validation.md    readable summary, with the main confusions

Items labelled "unsure" (or left empty) are left out of the accuracy.
Accuracy comes with a 95% confidence interval (Wilson): with ~200 items per
dataset it is about ±6 points, so small differences between cuts are noise.

Run (only once the labels are done):
    python src/evaluate_colour_labels.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data" / "interim" / "colour_labelling" / "colour_labels.csv"
ESTIMATES = ROOT / "data" / "processed" / "colour_estimates.csv"
OUT_CSV = ROOT / "reports" / "colour_validation.csv"
OUT_MD = ROOT / "reports" / "colour_validation.md"

CUTS = [0.0, 0.5, 0.6, 0.7]
NAMES = {"polyvore": "PolyVore", "fashionpedia": "Fashionpedia"}


def wilson(k, n, z=1.96):
    """95% confidence interval of a proportion k / n."""
    if n == 0:
        return np.nan, np.nan
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def main():
    if not LABELS.exists():
        sys.exit(f"ERROR: {LABELS} not found (label the items first)")
    lab = pd.read_csv(LABELS, dtype=str, keep_default_na=False)
    palette = set(pd.read_csv(ROOT / "mappings" / "colour_palette.csv")["colour"])
    if bad := set(lab["true_colour"]) - palette - {"unsure", ""}:
        sys.exit(f"ERROR: labels not in the palette: {sorted(bad)}")

    est = pd.read_csv(ESTIMATES, dtype=str, keep_default_na=False)
    df = lab.merge(est, on="id", how="left")
    if df["predicted_colour"].isna().any():
        sys.exit("ERROR: some labelled items have no estimate (re-run estimate_colours.py?)")
    n_all = len(df)
    df = df[~df["true_colour"].isin(["unsure", ""])].copy()
    df["conf"] = df["colour_confidence"].astype(float)
    df["ok"] = df["predicted_colour"] == df["true_colour"]
    print(f"{len(df)} usable labels ({n_all - len(df)} unsure or empty)")

    rows = []
    for ds, g in df.groupby("dataset"):
        for cut in CUTS:
            kept = g[g["conf"] >= cut]
            lo, hi = wilson(kept["ok"].sum(), len(kept))
            rows.append({"dataset": NAMES[ds], "cut": cut, "labelled": len(g),
                         "kept": len(kept), "coverage": 100 * len(kept) / len(g),
                         "accuracy": 100 * kept["ok"].mean() if len(kept) else np.nan,
                         "ci_low": 100 * lo, "ci_high": 100 * hi})
    res = pd.DataFrame(rows).round(1)
    res.to_csv(OUT_CSV, index=False)
    print(res.to_string(index=False))

    md = ["# Colour model: accuracy on hand-labelled items\n",
          f"{len(df)} items labelled by hand (val / test, crops >= 64 px), "
          "compared with the model's best colour.\n",
          "| dataset | min. confidence | colour kept | accuracy (95% CI) |", "|---|---:|---:|---:|"]
    md += [f"| {r.dataset} | {r.cut} | {r.coverage:.0f}% ({r.kept}) | "
           f"{r.accuracy:.1f}% ({r.ci_low:.0f}–{r.ci_high:.0f}) |" for r in res.itertuples()]
    wrong = df[~df["ok"]]
    conf_pairs = (wrong["true_colour"] + " → " + wrong["predicted_colour"]).value_counts()
    md += ["\n## Most frequent mistakes (true → predicted, all confidences)\n"]
    md += [f"- {pair}: {n}" for pair, n in conf_pairs.head(10).items()]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"\nSaved {OUT_CSV} and {OUT_MD}")


if __name__ == "__main__":
    main()
