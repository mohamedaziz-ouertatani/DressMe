"""
The frozen Inditex snapshot (data/processed/shop_demo.csv, written once by
src/freeze_shop_demo.py) as listings. It never contacts a shop: the Inditex
sites refuse our browser (2026-10-04), so these rows are a dated academic demo,
never refreshed. Each listing keeps the date it was really checked
(`checked_at`), and the app shows price and stock as "on that date".
"""

import csv
from pathlib import Path

from app.listings import RawListing

from .base import FetchResult
from .inditex import split

DATA = Path(__file__).resolve().parents[2] / "data"
SNAPSHOT = DATA / "processed" / "shop_demo.csv"
IN_STOCK = {"in_stock", "low_on_stock"}


def to_raw(row):
    availability = row.get("availability", "")
    in_stock = True if availability in IN_STOCK else False if availability == "out_of_stock" else None
    level = row.get("availability_level", "")
    try:
        price = float(row["price_tnd"]) if row.get("price_tnd") else None
    except ValueError:
        price = None
    return RawListing(
        external_id=row["id"], url=row.get("url", ""), title=row.get("name", ""),
        image_url=row.get("image_url", ""), brand=row.get("brand", ""),
        shop_colour=row.get("colour_name", ""), gender=row.get("gender", ""), price_tnd=price,
        sizes=split(row.get("sizes")),
        sizes_in_stock=split(row.get("sizes_in_stock")) if level == "colour" else [],
        in_stock=in_stock, availability_level=level,
        image_path=str(DATA / row["image_path"]) if row.get("image_path") else "",
        checked_at=row.get("checked_at", ""), snapshot=True)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # a listing needs a link to the shop and a picture we already have
    return [to_raw(r) for r in rows if r.get("url") and r.get("image_path")]


def fetch(source, args):
    if not SNAPSHOT.exists():
        return FetchResult("error", f"{SNAPSHOT} not found: run python src/freeze_shop_demo.py first",
                           mode="snapshot")
    rows = read_rows(SNAPSHOT)
    if getattr(args, "limit", 0):
        rows = rows[:args.limit]
    return FetchResult("ok", f"{len(rows)} rows from {SNAPSHOT.name}", rows, "snapshot")
