"""
Pre-resize every distinct picture to a small square JPEG, once, so that
training the classifier does not decode full-size street photos at every
epoch (that was ~140 pictures/s; small JPEGs load ~10x faster).

Each picture is stored once, under its picture key (see item_images.py):
Fashion Product / PolyVore per file MD5 (duplicates shared), Fashionpedia per
item, cropped with its bbox (crops < 32 px are skipped). Pictures are padded
to a white square (letterbox), so nothing is cut off.

Already-cached files are skipped, so the script can be stopped and re-run.

At the end, all the small JPEGs are packed into ONE file plus an index.
Opening 282k small files is slow on Windows (~300 files/s, the antivirus
checks each one), while slices of one big file read at thousands per second.
Once the pack exists, the folder of small files is deleted (pass --keep-files
to keep it).

Output (inside data/, never committed, ~2.6 GB):
    data/interim/image_cache_224.bin        all JPEGs, one after the other
    data/interim/image_cache_224_index.csv  key, offset, length (bytes)

Run from the project root (~35 min; lower DRESSME_WORKERS if MemoryError):
    python src/build_image_cache.py
"""

import argparse
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from item_images import DATA, DATASETS, jobs_for, letterbox, load_item_image, picture_key

SIZE = 224
QUALITY = 90
CACHE_DIR = DATA / "interim" / f"image_cache_{SIZE}"
PACK = DATA / "interim" / f"image_cache_{SIZE}.bin"
PACK_INDEX = DATA / "interim" / f"image_cache_{SIZE}_index.csv"
WORKERS = int(os.environ.get("DRESSME_WORKERS", 4))


def cache_one(row):
    """Resize one picture into the cache. Returns an error message or None."""
    try:
        letterbox(load_item_image(row), SIZE).save(CACHE_DIR / f"{row['key']}.jpg", quality=QUALITY)
        return None
    except Exception as e:      # a broken file must not stop the whole run
        return f"{row['image_path']}: {e}"


def pack(keep_files):
    """Concatenate every small JPEG into one file, with an index of where each starts."""
    files = sorted(CACHE_DIR.glob("*.jpg"))
    index, offset = [], 0
    with open(PACK, "wb") as out:
        for n, path in enumerate(files, 1):
            data = path.read_bytes()
            out.write(data)
            index.append((path.stem, offset, len(data)))
            offset += len(data)
            if n % 50_000 == 0:
                print(f"  packed {n:,}/{len(files):,}", flush=True)
    pd.DataFrame(index, columns=["key", "offset", "length"]).to_csv(PACK_INDEX, index=False)
    print(f"Packed {len(files):,} pictures into {PACK} ({offset / 1e9:.2f} GB)")
    if not keep_files:
        shutil.rmtree(CACHE_DIR)
        print(f"Deleted the folder of small files {CACHE_DIR}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-files", action="store_true", help="keep the small JPEG files")
    args = ap.parse_args()
    if PACK_INDEX.exists():
        sys.exit(f"{PACK_INDEX} already exists: delete the pack files to rebuild the cache")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=["id", "dataset", "image_path", "image_group",
                              "bbox_x", "bbox_y", "bbox_w", "bbox_h"])
    df["key"] = picture_key(df)
    done = {p.stem for p in CACHE_DIR.glob("*.jpg")}
    errors = []
    for dataset in DATASETS:
        rows = jobs_for(df, dataset)
        todo = rows[~rows["key"].isin(done)].to_dict("records")
        print(f"{dataset}: {len(rows):,} pictures, {len(todo):,} still to cache", flush=True)
        start = time.time()
        with ProcessPoolExecutor(WORKERS) as ex:
            for n, err in enumerate(ex.map(cache_one, todo, chunksize=64), 1):
                if err:
                    errors.append(err)
                if n % 10_000 == 0:
                    print(f"  {n:,}/{len(todo):,} ({n / (time.time() - start):.0f} img/s)", flush=True)
    print(f"\nCache ready in {CACHE_DIR}: {len(list(CACHE_DIR.glob('*.jpg'))):,} files, "
          f"{len(errors)} unreadable")
    for e in errors[:20]:
        print("  " + e)
    if errors:
        sys.exit(1)
    pack(args.keep_files)


if __name__ == "__main__":
    main()
