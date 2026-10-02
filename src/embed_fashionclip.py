"""
Compute one FashionCLIP vector for every picture of the merged dataset.

Each picture is embedded only once:
  - Fashion Product and PolyVore: per `image_group` (MD5 of the file), so the
    ~24k duplicate copies reuse the same vector;
  - Fashionpedia: per item (`id`), because the item is cropped out of a street
    photo with its bbox. Crops smaller than 32 px are skipped (no vector).

The work is saved per dataset ("shard"), so if the run crashes only the
current dataset is lost: re-running skips the shards that already exist.
Delete data/processed/embeddings/ to start again from zero.

Output (inside data/, so never committed):
    data/processed/embeddings/fashionclip.npy      N x 512 float16, unit length
    data/processed/embeddings/fashionclip_ids.csv  row i of the .npy <-> id
    (+ one fashionclip_<dataset>.npy / _keys.csv shard per dataset)

Run from the project root (GPU strongly recommended, ~20-60 min):
    python src/embed_fashionclip.py
    python src/embed_fashionclip.py --limit 500   # quick test, separate folder
Lower DRESSME_WORKERS (default 2) if you get a MemoryError.
"""

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from fashionclip import DATA, load_item_image, load_model, embed_pixels

OUT_DIR = DATA / "processed" / "embeddings"
MIN_SIDE = 32          # Fashionpedia crops below this size are skipped
BATCH = 128
WORKERS = int(os.environ.get("DRESSME_WORKERS", 2))
DATASETS = ["fashion_product", "polyvore", "fashionpedia"]


def picture_key(df):
    """The key that identifies one picture: the file MD5, or the item for crops."""
    return np.where(df["dataset"] == "fashionpedia", df["id"], df["image_group"])


def jobs_for(df, dataset):
    """One row per picture to embed for this dataset."""
    d = df[df["dataset"] == dataset]
    if dataset == "fashionpedia":
        side = np.minimum(d["bbox_w"].astype(float), d["bbox_h"].astype(float))
        d = d[side >= MIN_SIDE]
    return d.drop_duplicates("key").reset_index(drop=True)


class Pictures(Dataset):
    """Loads and prepares the pictures in background worker processes."""

    def __init__(self, rows, image_processor):
        self.rows = rows.to_dict("records")
        self.image_processor = image_processor

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        try:
            img = load_item_image(self.rows[i])
            pixels = self.image_processor(images=img, return_tensors="pt")["pixel_values"][0]
            return i, pixels
        except Exception as e:          # a broken file must not stop a 1-hour run
            print(f"  cannot read {self.rows[i]['image_path']}: {e}")
            return i, None


def collate(batch):
    batch = [(i, p) for i, p in batch if p is not None]
    if not batch:
        return [], None
    return [i for i, _ in batch], torch.stack([p for _, p in batch])


def embed_shard(rows, model, processor, device, name):
    loader = DataLoader(Pictures(rows, processor.image_processor), batch_size=BATCH,
                        num_workers=WORKERS, collate_fn=collate)
    vecs = np.zeros((len(rows), 512), np.float16)
    done = np.zeros(len(rows), bool)
    start = time.time()
    for b, (idx, pixels) in enumerate(loader):
        if pixels is None:          # the whole batch was unreadable
            continue
        vecs[idx] = embed_pixels(pixels, model, device)
        done[idx] = True
        if b % 50 == 0:
            n = done.sum()
            print(f"  {name}: {n:,}/{len(rows):,} ({n / (time.time() - start):.0f} img/s)")
    print(f"  {name}: {done.sum():,} pictures in {(time.time() - start) / 60:.1f} min, "
          f"{(~done).sum()} unreadable")
    return vecs[done], rows.loc[done, "key"]


def check(vecs, what):
    """Stop if the vectors are broken: no NaN, and every vector of length 1."""
    if np.isnan(vecs.astype(np.float32)).any():
        sys.exit(f"ERROR: NaN in {what}")
    norms = np.linalg.norm(vecs.astype(np.float32), axis=1)
    if np.abs(norms - 1).max() > 0.01:
        sys.exit(f"ERROR: {what} has vectors that are not unit length")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="embed only the first N pictures per dataset (test)")
    args = ap.parse_args()
    out_dir = OUT_DIR / "smoke" if args.limit else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=["id", "dataset", "image_path", "image_group",
                              "bbox_x", "bbox_y", "bbox_w", "bbox_h"])
    df["key"] = picture_key(df)
    model, processor, device = load_model()
    print(f"FashionCLIP on {device}, {WORKERS} loader workers")

    # --- one shard per dataset (skipped when it already exists) ------------
    keys = {}
    for dataset in DATASETS:
        rows = jobs_for(df, dataset)
        if args.limit:
            rows = rows.head(args.limit)
        npy, ids = out_dir / f"fashionclip_{dataset}.npy", out_dir / f"fashionclip_{dataset}_keys.csv"
        if npy.exists() and ids.exists():
            print(f"{dataset}: shard already done, skipped")
        else:
            print(f"{dataset}: {len(rows):,} pictures to embed")
            vecs, shard_keys = embed_shard(rows, model, processor, device, dataset)
            check(vecs, dataset)
            np.save(npy, vecs)
            shard_keys.to_frame("key").to_csv(ids, index=False)
        keys[dataset] = (np.load(npy), pd.read_csv(ids, dtype=str)["key"])

    # --- one vector per dressme.csv row (duplicates share their picture's) --
    all_vecs = np.concatenate([v for v, _ in keys.values()])
    position = pd.Series(np.arange(len(all_vecs)),
                         index=pd.concat([k for _, k in keys.values()], ignore_index=True))
    rows = df[df["key"].isin(position.index)]
    final = all_vecs[position.loc[rows["key"]].to_numpy()]
    check(final, "the final matrix")
    np.save(out_dir / "fashionclip.npy", final)
    rows[["id"]].to_csv(out_dir / "fashionclip_ids.csv", index=False)

    # --- summary ----------------------------------------------------------
    print(f"\nSaved {len(final):,} vectors ({len(all_vecs):,} distinct pictures) to {out_dir}")
    print("rows with a vector per dataset:\n" + rows["dataset"].value_counts().to_string())
    if not args.limit:
        expected = sum(len(jobs_for(df, d)) for d in DATASETS)
        if len(all_vecs) != expected:
            print(f"WARNING: {expected - len(all_vecs)} pictures could not be read (see above)")


if __name__ == "__main__":
    main()
