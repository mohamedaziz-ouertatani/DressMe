"""
Runs ON KAGGLE (a private notebook), not on our machines.

The H&M competition pictures are ~30 GB and Kaggle only lets us download
~500 single files per period, so we shrink them where they already are:
every adult article (children's wear is dropped, like hm_index_group.csv)
is resized to 320 px on its longest side and packed into ONE zip in the
notebook output (~850 MB). src/fetch_hm_images.py then downloads that zip
in one request.

The notebook must stay PRIVATE: the pictures belong to H&M and are only
used under the competition rules (never redistributed).

Pushed with (from the project root):
    kaggle kernels push -p kaggle/hm_images
"""

import time
import zipfile
from io import BytesIO
from multiprocessing import Pool
from pathlib import Path

import pandas as pd
from PIL import Image

# where Kaggle mounts the competition data has changed over time: search for it
INPUT = next(Path("/kaggle/input").rglob("articles.csv")).parent
OUTPUT = Path("/kaggle/working/hm_images_320.zip")
MAX_SIDE = 320
DROP_GROUPS = ["Baby/Children"]     # same rule as mappings/hm_index_group.csv


def shrink(article_id):
    """Resized JPEG bytes of one article's picture, or None if it has none."""
    path = INPUT / "images" / article_id[:3] / f"{article_id}.jpg"
    if not path.exists():
        return article_id, None
    img = Image.open(path).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)    # keeps the proportions
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return article_id, buf.getvalue()


def main():
    articles = pd.read_csv(INPUT / "articles.csv", dtype=str)
    ids = articles.loc[~articles["index_group_name"].isin(DROP_GROUPS), "article_id"].tolist()
    print(f"Data in {INPUT}: {len(ids)} adult articles", flush=True)

    start, saved, missing = time.time(), 0, 0
    # pictures are already JPEG: store them in the zip without compressing again
    with Pool(4) as pool, zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_STORED) as z:
        for article_id, data in pool.imap_unordered(shrink, ids, chunksize=64):
            if data is None:
                missing += 1
                continue
            z.writestr(f"{article_id}.jpg", data)
            saved += 1
            if saved % 5000 == 0:
                print(f"  {saved}/{len(ids)} ({saved / (time.time() - start):.0f}/s)", flush=True)
    print(f"Done in {(time.time() - start) / 60:.1f} min: {saved} pictures, "
          f"{missing} articles without a picture, "
          f"{OUTPUT.stat().st_size / 1e6:.0f} MB", flush=True)


if __name__ == "__main__":
    main()
