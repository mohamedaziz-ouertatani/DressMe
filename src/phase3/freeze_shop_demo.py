"""
Freeze the shop rows already scraped (src/phase3/scrape_shops.py) into a static demo
snapshot. The shops' bot protection blocks new runs (see CLAUDE.md), so this
snapshot is all we keep: it is never refreshed and never mixed with
"live" data.

What it does:
  - reads every data/raw/Shops/<brand>_<cc>/products.csv;
  - keeps the columns the demo needs, with the price in TND;
  - marks how far the stock can be trusted (`availability_level`):
      colour  = the stock was checked for this exact colour (sizes known);
      product = rows scraped before the per-colour fix: Zara's stock answer
                covers every colour, so "in_stock" only means "some colour /
                size of this product was in stock";
  - downloads each picture ONCE (slowly) so the demo works offline. A picture
    that cannot be downloaded keeps only its image_url.

Run (from the project root):
    python src/phase3/freeze_shop_demo.py
    python src/phase3/freeze_shop_demo.py --no-images

Output (inside data/, so never committed; academic demo only, the shops'
terms do not allow redistributing it):
    data/processed/shop_demo.csv
    data/processed/shop_demo_images/<id>.jpg
"""

import argparse
import sys
import time
import urllib.request

import pandas as pd

from scrape_shops import OUT_DIR, ROOT

OUT_CSV = ROOT / "data" / "processed" / "shop_demo.csv"
IMG_DIR = ROOT / "data" / "processed" / "shop_demo_images"

COLUMNS = ["id", "brand", "country", "gender", "name", "colour_name", "category_paths",
           "price_tnd", "url", "image_url", "image_path", "sizes", "availability",
           "availability_level", "sizes_in_stock", "checked_at"]


# who we are, never a fake browser (the same words as src/phase4/connectors/http.py)
USER_AGENT = "DressMe student project (ESPRIT, academic, non-commercial)"


class NoScrapedRows(Exception):
    """No data/raw/Shops/*/products.csv on this computer: nothing to freeze."""


def download(url, path):
    """Save one picture; True if it worked."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            path.write_bytes(resp.read())
        return True
    except Exception as err:
        print(f"  no picture for {path.stem}: {err}")
        return False


def freeze(images=True, delay=1.0, should_stop=lambda: False):
    """Build data/processed/shop_demo.csv (+ pictures) from the scraped rows.
    Returns (csv path, number of rows, number of pictures saved).
    Also called by the snapshot connector (src/phase4/connectors/snapshot.py) when the
    file is missing. A row whose picture could not be saved keeps its
    image_url, and the collector tries it once more."""
    files = sorted(OUT_DIR.glob("*/products.csv"))
    if not files:
        raise NoScrapedRows(f"no products.csv under {OUT_DIR}: nothing was scraped on this computer")
    df = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in files],
                   ignore_index=True)
    df = df.drop_duplicates("id")
    print(f"{len(df)} product colours from {len(files)} file(s): "
          + ", ".join(f"{b} {n}" for b, n in df["brand"].value_counts().items()), flush=True)

    # price: the scraper already divided price_raw by 100 (checked on zara.com/tn)
    df["price_tnd"] = df["price"]
    # stock checked per colour only when we knew the colour's SKUs
    checked = df["availability_from"] == "stock_api"
    df["availability_level"] = ""
    df.loc[checked & (df["sku_sizes"] != ""), "availability_level"] = "colour"
    df.loc[checked & (df["sku_sizes"] == ""), "availability_level"] = "product"
    # sizes_in_stock of "product" rows are SKU numbers of mixed colours: useless
    df.loc[df["availability_level"] == "product", "sizes_in_stock"] = ""

    df["image_path"] = ""
    if images:
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        for n, (i, row) in enumerate(df.iterrows(), 1):
            if should_stop():
                raise InterruptedError("stopped while saving the pictures")
            path = IMG_DIR / f"{row['id']}.jpg"
            if path.exists():
                df.at[i, "image_path"] = str(path.relative_to(ROOT / "data")).replace("\\", "/")
            elif row["image_url"] and download(row["image_url"], path):
                df.at[i, "image_path"] = str(path.relative_to(ROOT / "data")).replace("\\", "/")
                time.sleep(delay)
            if n % 50 == 0:
                print(f"  pictures {n}/{len(df)}", flush=True)
        print(f"{(df['image_path'] != '').sum()} / {len(df)} pictures saved in {IMG_DIR}", flush=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df[COLUMNS].to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}")
    print("availability:", df["availability"].value_counts().to_dict(),
          "| level:", df["availability_level"].value_counts().to_dict())
    return OUT_CSV, len(df), int((df["image_path"] != "").sum())


def main():
    ap = argparse.ArgumentParser(description="Freeze the scraped shop rows into a demo snapshot")
    ap.add_argument("--no-images", action="store_true", help="do not download the pictures")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between picture downloads")
    args = ap.parse_args()
    try:
        freeze(images=not args.no_images, delay=args.delay)
    except NoScrapedRows as err:
        sys.exit(f"ERROR: {err}.")


if __name__ == "__main__":
    main()
