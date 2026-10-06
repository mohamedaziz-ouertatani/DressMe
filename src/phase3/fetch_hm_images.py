"""
Get the H&M pictures: download the zip made by our private Kaggle notebook
and unpack it into data/raw/HM/images/<article_id>.jpg.

Why a notebook: the full picture set is ~30 GB (too big for our disks), and
Kaggle only allows ~500 single-file downloads per period (429 Too Many
Requests), so 1-by-1 downloads would take days. The notebook
(kaggle/hm_images/) runs on Kaggle, next to the data, shrinks every adult
article's picture to 320 px and packs them into ONE zip (~850 MB).

Steps (from the project root; the Kaggle account must have accepted the
competition rules, see CLAUDE.md):
    kaggle kernels push -p kaggle/hm_images     # once: runs ~20 min on Kaggle
    kaggle kernels status mohameddazizz/dressme-hm-images-320   # wait for COMPLETE
    python src/phase3/fetch_hm_images.py               # download + unpack (~1.7 GB free disk needed)

The notebook is PRIVATE and must stay so: the pictures belong to H&M.
"""

import subprocess
import sys
import zipfile

from map_hm import HM_DIR

KERNEL = "mohameddazizz/dressme-hm-images-320"
ZIP_PATH = HM_DIR / "hm_images_320.zip"
IMG_DIR = HM_DIR / "images"


def main():
    if not ZIP_PATH.exists():
        print(f"Downloading the output of {KERNEL} ...", flush=True)
        done = subprocess.run(["kaggle", "kernels", "output", KERNEL, "-p", str(HM_DIR),
                               "--file-pattern", r"hm_images_320\.zip"])
        if done.returncode != 0 or not ZIP_PATH.exists():
            sys.exit("ERROR: download failed (has the notebook finished? see the steps above)")

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as z:
        names = z.namelist()
        print(f"Unpacking {len(names):,} pictures to {IMG_DIR} ...", flush=True)
        z.extractall(IMG_DIR)
    ZIP_PATH.unlink()      # the disk is nearly full: keep only the pictures
    print(f"Done: {len(list(IMG_DIR.glob('*.jpg'))):,} pictures in {IMG_DIR}")


if __name__ == "__main__":
    main()
