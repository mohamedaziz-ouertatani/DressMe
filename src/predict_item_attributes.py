"""
Run the trained classifier once over every cached picture, so that fields the
datasets do not label (e.g. pattern on PolyVore) are available to the
compatibility formula and, later, to the backend.

These are PREDICTIONS (with a confidence), kept apart from the dataset labels
in dressme.csv: never mix them up when training or evaluating a classifier.

Output (inside data/, never committed):
    data/processed/predicted_attributes.csv
        id, pred_category, pred_category_conf, pred_sub_category,
        pred_sub_category_conf, pred_pattern, pred_pattern_conf
    (one row per dressme.csv row that has a cached picture; duplicate copies
     get the prediction of their picture)

Run from the project root (~10 min on the GPU):
    python src/predict_item_attributes.py
"""

import pandas as pd

from classifier import decode, load_classifier, predict_tensors
from item_images import DATA, picture_key
from train_classifier import batches, load_table

OUT_PATH = DATA / "processed" / "predicted_attributes.csv"


def main():
    pictures = load_table()          # one row per distinct cached picture, all splits
    model, device = load_classifier()
    answers = []
    for n, (x, _) in enumerate(batches(pictures, device, train=False, batch=256), 1):
        answers += decode(predict_tensors(x, model, device))
        if n % 100 == 0:
            print(f"  {len(answers):,}/{len(pictures):,}", flush=True)
    pred = pd.DataFrame(answers).add_prefix("pred_")
    pred["key"] = pictures["key"].to_numpy()

    # every dressme.csv row gets the prediction of its picture
    rows = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                       usecols=["id", "dataset", "image_group"])
    rows["key"] = picture_key(rows)
    out = rows[["id", "key"]].merge(pred, on="key").drop(columns="key")
    for c in out.columns:
        if c.endswith("_conf"):
            out[c] = out[c].round(3)
    out.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(out):,} rows ({len(pred):,} pictures) to {OUT_PATH}")


if __name__ == "__main__":
    main()
