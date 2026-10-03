"""
Light helpers to find and open the picture of one item (PIL only, no PyTorch,
so worker processes stay small).

    rows = jobs_for(df, "polyvore")        # one row per distinct picture
    img = load_item_image(rows.iloc[0])    # PIL image (Fashionpedia: cropped)
    square = letterbox(img, 224)           # 224 x 224, padded with white

A "picture" is identified by `picture_key`: the file MD5 (`image_group`) for
product shots, so duplicate copies are handled once, and the item `id` for
Fashionpedia, where each item is cropped out of a street photo.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CROP_PADDING = 0.05    # Fashionpedia crops get 5% extra margin around the bbox
MIN_SIDE = 32          # Fashionpedia crops below this size are skipped
DATASETS = ["fashion_product", "polyvore", "fashionpedia"]


def picture_key(df):
    """The key that identifies one picture: the file MD5, or the item for crops."""
    return np.where(df["dataset"] == "fashionpedia", df["id"], df["image_group"])


def jobs_for(df, dataset):
    """One row per distinct picture of this dataset (df needs a 'key' column)."""
    d = df[df["dataset"] == dataset]
    if dataset == "fashionpedia":
        side = np.minimum(d["bbox_w"].astype(float), d["bbox_h"].astype(float))
        d = d[side >= MIN_SIDE]
    return d.drop_duplicates("key").reset_index(drop=True)


def load_item_image(row):
    """Open the picture of one dressme.csv row (a dict or a pandas row).

    Fashionpedia rows have a bbox: the item is cropped out of the street photo,
    with a small margin so the edges of the garment are not cut.
    """
    img = Image.open(DATA / row["image_path"])
    if row.get("dataset") == "local":
        # phone photos: apply the EXIF "rotate" tag, or a portrait photo lies on its side
        # (only for our photos: the dataset bboxes were drawn on the stored pixels)
        img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if str(row.get("bbox_w", "")) not in ("", "nan"):
        x, y, w, h = (float(row[k]) for k in ("bbox_x", "bbox_y", "bbox_w", "bbox_h"))
        pad_w, pad_h = w * CROP_PADDING, h * CROP_PADDING
        img = img.crop((max(0, x - pad_w), max(0, y - pad_h),
                        min(img.width, x + w + pad_w), min(img.height, y + h + pad_h)))
    return img


def letterbox(img, size):
    """Resize so the longer side is `size`, then pad to a white square.

    Nothing is cut off (a centre crop could remove the sleeves of a wide top),
    and product shots are already on white, so the padding blends in.
    """
    scale = size / max(img.width, img.height)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                     Image.BICUBIC)
    square = Image.new("RGB", (size, size), (255, 255, 255))
    square.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return square
