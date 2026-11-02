"""
Saving a piece into the wardrobe: ONE function, `promote`, with two ways in.

    a fresh upload   promote(db, storage_dir, user_id, doc=<analysed document>, image=<PIL image>)
                     (POST /items: the photo is saved, the document inserted, an `upload` event logged)
    a scan           promote(db, storage_dir, user_id, candidate=<candidates document>, photo=<jpeg bytes>)
                     ("Bought it": the scan's cleaned photo, labels, guesses, corrections and vector
                     are reused. NO second analysis)

It returns (item document, created). Promoting the same scan twice returns the item made the first
time (created=False): a unique partial index on `items.promoted_from.id` stops a second copy even
when two requests arrive together (MongoDB runs on a single node, so there are no transactions).

New item fields (never back-filled: items from before have neither):
    promoted_from  {"kind": "candidate", "id": <scan id>}, or null for an upload
    analysed_by    {"models": {...} or null, "at": <when the labels were made>}, or null when unknown
"""

from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from .events import log_event

# what an item keeps from the scan it was made from (the rest of a scan is a verdict's working data)
FROM_CANDIDATE = ("category", "sub_category", "pattern", "colour", "coverage", "season", "usage",
                  "predicted", "corrected", "vector")


def analysed_by(analyzer, at=None):
    """Which models made the labels, and when. The real analyzer knows its model files
    (`versions`); a fake or an unknown one gives models=None."""
    versions = getattr(analyzer, "versions", None)
    return {"models": dict(versions) if versions else None, "at": at or datetime.now(timezone.utc)}


def promote(db, storage_dir, user_id, *, doc=None, image=None, candidate=None, photo=None):
    if (doc is None) == (candidate is None):
        raise ValueError("promote needs either an uploaded document or a candidate")
    folder = storage_dir / str(user_id)

    if candidate is None:                            # ---- a fresh upload (what POST /items always did)
        doc["_id"] = ObjectId()
        doc["promoted_from"] = None
        folder.mkdir(parents=True, exist_ok=True)
        image.save(folder / f"{doc['_id']}.jpg", quality=85)
        db.items.insert_one(doc)
        log_event(db, "upload", user_id, category=doc["category"])
        return doc, True

    # ---- a scan
    source = {"kind": "candidate", "id": str(candidate["_id"])}
    existing = db.items.find_one({"user_id": user_id, "promoted_from.id": source["id"]})
    if existing:
        return existing, False
    item = {k: candidate[k] for k in FROM_CANDIDATE if k in candidate}
    item.update({"_id": ObjectId(), "user_id": user_id, "created_at": datetime.now(timezone.utc),
                 "promoted_from": source, "analysed_by": candidate.get("analysed_by")})
    path = folder / f"{item['_id']}.jpg"
    if photo:
        folder.mkdir(parents=True, exist_ok=True)
        path.write_bytes(photo)
    try:
        db.items.insert_one(item)
    except DuplicateKeyError:                        # another request promoted it first
        path.unlink(missing_ok=True)
        existing = db.items.find_one({"user_id": user_id, "promoted_from.id": source["id"]})
        if existing is None:
            raise
        return existing, False
    log_event(db, "upload", user_id, category=item["category"], source="candidate")
    return item, True
