"""
FashionCLIP vectors for the H&M shop catalogue (the pictures downloaded by
src/fetch_hm_images.py), so the app can find "something like this to buy".

Same model and settings as src/embed_fashionclip.py, so the H&M vectors can be
compared with the wardrobe and dataset vectors. Kept apart from fashionclip.npy
because H&M is not part of dressme.csv.

Output (inside data/, so never committed):
    data/processed/embeddings/hm_fashionclip.npy      N x 512 float16, unit length
    data/processed/embeddings/hm_fashionclip_ids.csv  row i of the .npy <-> id

Run from the project root after the download (~5 min on the GPU):
    python src/embed_hm.py
"""

import sys
import time

import numpy as np
import pandas as pd

from embed_fashionclip import OUT_DIR, check
from fashionclip import embed_images, load_model
from item_images import DATA, load_item_image
from map_hm import OUT_PATH as HM_CSV

BATCH = 64
NPY_PATH = OUT_DIR / "hm_fashionclip.npy"
IDS_PATH = OUT_DIR / "hm_fashionclip_ids.csv"


def main():
    df = pd.read_csv(HM_CSV, dtype=str, keep_default_na=False, usecols=["id", "image_path"])
    df = df[[(DATA / p).exists() for p in df["image_path"]]].reset_index(drop=True)
    print(f"{len(df):,} H&M articles have a picture on disk")

    model, processor, device = load_model()
    vecs = np.zeros((len(df), 512), np.float16)
    start = time.time()
    for s in range(0, len(df), BATCH):
        rows = df.iloc[s:s + BATCH].to_dict("records")
        vecs[s:s + len(rows)] = embed_images([load_item_image(r) for r in rows],
                                             model, processor, device)
        if s % (BATCH * 50) == 0:
            print(f"  {s + len(rows):,}/{len(df):,} ({(s + len(rows)) / (time.time() - start):.0f} img/s)")

    check(vecs, "the H&M vectors")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # write new files first, then swap them in: if the swap fails (e.g. a running
    # backend still has the old file open), the new vectors are not lost
    new_npy, new_ids = NPY_PATH.with_suffix(".new.npy"), IDS_PATH.with_suffix(".new.csv")
    np.save(new_npy, vecs)
    df[["id"]].to_csv(new_ids, index=False)
    try:
        new_npy.replace(NPY_PATH)
        new_ids.replace(IDS_PATH)
    except OSError:
        sys.exit(f"ERROR: cannot replace {NPY_PATH.name} (is the backend running? stop it), "
                 f"then rename {new_npy.name} -> {NPY_PATH.name} and {new_ids.name} -> {IDS_PATH.name}")
    print(f"Saved {len(df):,} vectors to {NPY_PATH} in {(time.time() - start) / 60:.1f} min")


if __name__ == "__main__":
    main()
