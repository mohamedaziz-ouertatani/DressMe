"""
Do the concept probes read the picture vectors? (XAI sub-project 3)

The Similar page says "both read as denim, party": the concepts FashionCLIP
associates with two pictures (src/phase4/explain_similarity.py, team list in
mappings/style_concepts.csv). For every concept with a `check` label
(usage=formal, sub_category=jeans, pattern=floral...), this measures on the
test split how well the concept's score separates pictures WITH that label
from pictures WITHOUT it (AUC: 0.5 = chance, 1 = perfect). Only pictures whose
field is known count. Concepts without a label are listed as not checkable.
-> reports/phase4/concepts_evaluation.md

    python src/phase4/evaluate_concepts.py [--limit 20000]
"""

import argparse

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
import explain_similarity
import fashionclip
from item_images import DATA, ROOT
from similarity import EMB_DIR

REPORT = ROOT / "reports" / "phase4" / "concepts_evaluation.md"
SEED = 0


def load_test(limit):
    """Test-split pictures that have a vector, with their labels (one row per picture)."""
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=["id", "dataset", "category", "sub_category", "pattern", "usage", "split",
                              "duplicate"])
    df = df[(df["split"] == "test") & (df["duplicate"] != "True")
            & df["dataset"].isin(["fashion_product", "polyvore"])]
    ids = pd.read_csv(EMB_DIR / "fashionclip_ids.csv", dtype=str)["id"]
    row_of = pd.Series(np.arange(len(ids)), index=ids)
    df = df[df["id"].isin(row_of.index)]
    df = df.sample(min(limit, len(df)), random_state=SEED).reset_index(drop=True)
    vecs = np.load(EMB_DIR / "fashionclip.npy", mmap_mode="r")
    rows = row_of[df["id"]].to_numpy()
    order = np.argsort(rows)                        # read the memmap in file order
    V = np.empty((len(rows), vecs.shape[1]), np.float32)
    V[order] = vecs[rows[order]].astype(np.float32)
    return df, V


def has_value(column, value):
    """True where the (multi-value, '|'-separated) field contains `value`."""
    return column.str.split("|").apply(lambda vs: value in vs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20000, help="test pictures to use")
    args = ap.parse_args()
    df, V = load_test(args.limit)
    concepts = explain_similarity.load_concepts()
    model, processor, _ = fashionclip.load_model("cpu")      # 20 short texts: the CPU is enough
    T = fashionclip.embed_texts([c["prompt"] for c in concepts], model, processor, "cpu").astype(np.float32)
    scores = V @ T.T                                          # pictures x concepts
    print(f"{len(df):,} test pictures, {len(concepts)} concepts", flush=True)

    rows, unchecked = [], []
    for j, c in enumerate(concepts):
        if not c["check"]:
            unchecked.append(c["concept"])
            continue
        field, value = c["check"].split("=", 1)
        known = df[field] != ""
        y = has_value(df.loc[known, field], value).to_numpy()
        if y.sum() < 10 or (~y).sum() < 10:
            rows.append({"concept": c["concept"], "label": c["check"], "pictures": int(known.sum()),
                         "with_label": int(y.sum()), "auc": None})
            continue
        auc = roc_auc_score(y, scores[known.to_numpy(), j])
        rows.append({"concept": c["concept"], "label": c["check"], "pictures": int(known.sum()),
                     "with_label": int(y.sum()), "auc": round(float(auc), 3)})

    lines = ["# Concept probes: evaluation", "",
             "Made by `src/phase4/evaluate_concepts.py`. The Similar page shows the concepts the picture "
             "model (FashionCLIP) associates with two pieces (`mappings/style_concepts.csv`, REVIEW). For "
             "concepts that match an existing label, AUC = how well the concept's score separates test "
             f"pictures with that label from the others ({len(df):,} test pictures of Fashion Product and "
             "PolyVore; only pictures whose field is known count). 0.5 = chance, 1 = perfect.", "",
             "| concept | label | pictures | with the label | AUC |", "|---|---|---:|---:|---:|"]
    for r in rows:
        auc = "too few" if r["auc"] is None else f"{r['auc']:.3f}"
        lines.append(f"| {r['concept']} | `{r['label']}` | {r['pictures']:,} | {r['with_label']:,} | {auc} |")
    checked = [r["auc"] for r in rows if r["auc"] is not None]
    lines += ["", f"Mean AUC over the {len(checked)} checkable concepts: "
              f"{np.mean(checked):.3f}." if checked else "", "",
              "Not checkable (no label in the data): " + ", ".join(unchecked) + ". These are shown in the "
              "app as what the picture model associates with a photo, never as facts.", "",
              "The app ranks concepts above the average picture (`concept_baseline`); that shift is the same "
              "for every picture, so it does not change these AUCs."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
