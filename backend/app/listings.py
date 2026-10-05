"""
Shop listings: products people can buy now, collected by src/collect_listings.py
from the sources the team approved in mappings/listing_sources.csv (see LISTINGS.md).

    load_sources(mappings_dir)  -> the sources table (one dict per source)
    usable(source)              -> "" if the collector may run it, else why not
    sync_listings(...)          -> saves one successful run of a source in MongoDB
    ListingIndex.search(...)    -> the in-stock listings closest to a FashionCLIP vector
    listing_out(doc)            -> a listing as JSON for the app

The labels of a listing (category, colour, ...) are our models' predictions on
its picture, exactly like a wardrobe upload: the shop's own words are not
mapped yet (that needs rule files per source, see LISTINGS.md).
"""

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import numpy as np
from bson import ObjectId

from .db import vector_from_bson, vector_to_bson

SOURCES_FILE = "listing_sources.csv"
KINDS = {"inditex", "snapshot", "shopify", "woocommerce", "sitemap"}   # kinds with a connector in src/connectors/
SELLERS = "sellers"            # source_id of the listings friperie sellers post in the app
THUMB_SIDE = 320               # we keep a small picture only, and link to the shop


@dataclass
class RawListing:
    """One product colour as a connector reads it from the shop."""
    external_id: str           # the shop's id, unique inside its source
    url: str                   # the product page: the app always links to it
    title: str
    image_url: str
    brand: str = ""
    shop_colour: str = ""      # the shop's colour name (e.g. "ECRU"), shown as is
    gender: str = ""
    price_tnd: float | None = None
    sizes: list = field(default_factory=list)
    sizes_in_stock: list = field(default_factory=list)
    in_stock: bool | None = None          # None = the shop did not say
    availability_level: str = ""          # colour / product / catalogue / "" (see collect_listings)
    image_path: str = ""       # a local picture (the frozen snapshot): read it, never download
    checked_at: str = ""       # when the shop was really checked, if older than this run (ISO date)
    snapshot: bool = False     # a frozen copy: price and stock are only true on checked_at
    price_original: str = ""   # the shop's own price when it is not in TND, e.g. "29.99 EUR"


class SourceBlocked(Exception):
    """The shop refused us (403 / 429 / bot check): stop this source, never work around it."""


# ------------------------------------------------------------------ sources
def load_sources(mappings_dir):
    with open(mappings_dir / SOURCES_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def usable(source):
    """Why the collector must NOT run this source ("" = it may)."""
    if not source.get("kind"):
        return "kind not set yet: run python src/check_shop_source.py --all --save"
    if source.get("kind") not in KINDS:
        return f"no connector for kind '{source.get('kind')}'"
    if source.get("kind") in ("shopify", "woocommerce", "sitemap") and not source.get("base_url"):
        return "no base_url"
    if source.get("enabled", "").strip().lower() != "yes":
        return "not enabled"
    try:
        date.fromisoformat(source.get("approved_on", "").strip())
    except ValueError:
        return "no team approval date (approved_on)"
    return ""


# ------------------------------------------------------------------ saving a run
def thumbnail_path(storage_dir, listing_id):
    return storage_dir / "listings" / f"{listing_id}.jpg"


def sync_listings(db, source_id, raws, label, storage_dir, now=None, mark_gone=True, on_item=None,
                  keep_ids=None):
    """Save the listings of one run of a source and return what changed.

    `label(raw)` downloads and analyses the picture: it returns
    {"fields", "predicted", "vector", "thumbnail"} or None if the picture
    could not be read. It is only called for new listings or a new picture,
    so an unchanged shop costs no downloads. It may raise SourceBlocked: then
    the run stops and NOTHING is marked gone (we did not see the whole shop).

    Only after a complete run (mark_gone=True; never for a --limit test run),
    listings of this source that were not seen become "gone" (sold out for
    good or removed by the shop).

    `on_item(done, total)` is called before each listing (the admin page's
    progress bar). It may raise to stop the run (an admin pressed Stop):
    then too, nothing is marked gone.

    `keep_ids`: when a run fetched only part of a big shop (sitemap connector),
    the ids of every product the shop still lists. Then only listings missing
    from it become gone; the ones not fetched this time stay as they are.
    """
    now = now or datetime.now(timezone.utc)
    counts = {"added": 0, "updated": 0, "relabelled": 0, "no_picture": 0, "gone": 0}
    (storage_dir / "listings").mkdir(parents=True, exist_ok=True)
    for i, raw in enumerate(raws):
        if on_item:
            on_item(i, len(raws))
        old = db.listings.find_one({"source_id": source_id, "external_id": raw.external_id},
                                   {"_id": 1, "image_url": 1})
        doc = {"source_id": source_id, "external_id": raw.external_id, "url": raw.url,
               "title": raw.title, "brand": raw.brand, "shop_colour": raw.shop_colour,
               "gender": raw.gender, "price_tnd": raw.price_tnd, "sizes": raw.sizes,
               "sizes_in_stock": raw.sizes_in_stock, "in_stock": raw.in_stock,
               "availability_level": raw.availability_level, "image_url": raw.image_url,
               "checked_at": raw.checked_at or None, "snapshot": raw.snapshot,
               "price_original": raw.price_original,
               "seen_at": now, "status": "active"}
        if old is None or old.get("image_url") != raw.image_url:
            labels = label(raw)
            if labels is None:
                counts["no_picture"] += 1
                if old is None:
                    continue           # never list an item we could not look at
                doc.pop("image_url")   # keep the old picture and labels
            else:
                listing_id = old["_id"] if old else ObjectId()
                labels["thumbnail"].save(thumbnail_path(storage_dir, listing_id), quality=85)
                doc.update(labels["fields"], predicted=labels["predicted"],
                           vector=vector_to_bson(labels["vector"]))
                if old is None:
                    doc.update(_id=listing_id, created_at=now)
                    db.listings.insert_one(doc)
                    counts["added"] += 1
                    continue
                counts["relabelled"] += 1
        db.listings.update_one({"_id": old["_id"]}, {"$set": doc})
        counts["updated"] += 1
    if mark_gone:
        missing = ({"external_id": {"$nin": list(keep_ids)}} if keep_ids is not None
                   else {"seen_at": {"$lt": now}})
        gone = db.listings.update_many(
            {"source_id": source_id, "status": "active", **missing},
            {"$set": {"status": "gone"}})
        counts["gone"] = gone.modified_count
    return counts


def record_run(db, source_id, started_at, result, message="", counts=None, mode=""):
    """One line per collector run, for the admin page. result: ok / blocked / error / skipped."""
    db.listing_runs.insert_one({
        "source_id": source_id, "started_at": started_at,
        "finished_at": datetime.now(timezone.utc), "result": result,
        "message": message[-2000:], "counts": counts or {}, "mode": mode})


def last_run(db, source_id, result=None):
    query = {"source_id": source_id, **({"result": result} if result else {})}
    return db.listing_runs.find_one(query, sort=[("finished_at", -1)])


# ------------------------------------------------------------------ app answers
def listing_out(doc):
    lid = str(doc["_id"])
    return {
        "id": lid, "source_id": doc["source_id"], "brand": doc.get("brand", ""),
        "title": doc.get("title", ""), "shop_colour": doc.get("shop_colour", ""),
        "url": doc.get("url", ""), "price_tnd": doc.get("price_tnd"),
        "sizes": doc.get("sizes", []), "sizes_in_stock": doc.get("sizes_in_stock", []),
        "in_stock": doc.get("in_stock"), "availability_level": doc.get("availability_level", ""),
        "category": doc.get("category", ""), "sub_category": doc.get("sub_category", ""),
        "pattern": doc.get("pattern", ""), "colour": doc.get("colour", ""),
        "predicted": doc.get("predicted", {}), "corrected": doc.get("corrected", []),
        "status": doc.get("status", ""),
        "seen_at": doc["seen_at"].isoformat() if doc.get("seen_at") else None,
        # when price and stock were really checked: the snapshot's own date, else this run
        "checked_at": doc.get("checked_at") or (doc["seen_at"].isoformat() if doc.get("seen_at") else None),
        "snapshot": bool(doc.get("snapshot")),
        "price_original": doc.get("price_original", ""),
        "image_url": f"/listings/{lid}/image",
        # a friperie seller's own listing: where to find them (shown to logged-in users only)
        "seller": ({"city": doc.get("city", ""), "contact": doc.get("contact", ""),
                    "review_note": doc.get("review_note", "")}
                   if doc["source_id"] == SELLERS else None),
    }


class ListingIndex:
    """Nearest-neighbour search over the in-stock listings (brute force: fine
    up to ~100k listings). The vectors are read from MongoDB once and read
    again only after a new collector run."""

    def __init__(self):
        self._key = None
        self._docs = []
        self._vectors = np.zeros((0, 512), np.float32)

    def invalidate(self):
        """Read the listings again on the next search (a seller listing changed)."""
        self._key = None

    def _refresh(self, db):
        run = db.listing_runs.find_one(sort=[("finished_at", -1)], projection={"_id": 1})
        key = (run and run["_id"], db.listings.estimated_document_count())
        if key == self._key:
            return
        self._docs = list(db.listings.find(
            {"status": "active", "in_stock": {"$ne": False}, "vector": {"$ne": None}}))
        self._vectors = (np.stack([vector_from_bson(d["vector"]) for d in self._docs])
                         if self._docs else np.zeros((0, 512), np.float32))
        self._key = key

    def search(self, db, vector, k=6, category=None):
        self._refresh(db)
        if not self._docs:
            return []
        scores = self._vectors @ np.asarray(vector, np.float32)
        hits = []
        for i in np.argsort(-scores):
            doc = self._docs[i]
            if category and doc.get("category") != category:
                continue
            hits.append({**listing_out(doc), "score": round(float(scores[i]), 3)})
            if len(hits) == k:
                break
        return hits
