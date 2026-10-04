"""
Shop listings collected by src/collect_listings.py (see LISTINGS.md).

    GET  /listings                    browse, with filters (in-stock only by default)
    GET  /listings/sources            the shops that have listings (for the filter)
    GET  /listings/{id}               one listing
    GET  /listings/{id}/image         its small picture (the app links to the shop for more)
    POST /listings/{id}/candidate     "Should I buy this?": the listing becomes a
                                      candidate, then the app calls /buy-advice as for a scan

Listings are shared by every user (they are shop products, not anyone's data);
the candidate made from one belongs to the user who asked, like a scan.
"""

import shutil
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from ..db import object_id
from ..events import log_event
from ..listings import listing_out, thumbnail_path
from ..security import current_user
from ..wardrobe import item_out

router = APIRouter(tags=["listings"])
NO_VECTOR = {"vector": 0}      # 1 KB per listing the app never needs


def get_listing(request, listing_id):
    oid = object_id(listing_id)
    doc = oid and request.app.state.db.listings.find_one({"_id": oid}, NO_VECTOR)
    if not doc:
        raise HTTPException(404, "Listing not found")
    return doc


@router.get("/listings")
def list_listings(request: Request, category: str | None = None, sub_category: str | None = None,
                  colour: str | None = None, size: str | None = None, source: str | None = None,
                  max_price: float | None = Query(None, ge=0), in_stock: bool = True,
                  sort: Literal["new", "price"] = "new",
                  page: int = Query(1, ge=1), per_page: int = Query(24, ge=1, le=100),
                  user=Depends(current_user)):
    """`size` matches the sizes the product comes in; its stock per size is only
    known when availability_level = colour (then see sizes_in_stock)."""
    query = {"status": "active"}
    for key, value in (("category", category), ("sub_category", sub_category),
                       ("colour", colour), ("source_id", source), ("sizes", size)):
        if value:
            query[key] = value
    if max_price is not None:
        query["price_tnd"] = {"$lte": max_price}
    if in_stock:
        query["in_stock"] = True
    order = [("price_tnd", 1), ("_id", 1)] if sort == "price" else [("created_at", -1), ("_id", -1)]
    db = request.app.state.db
    docs = db.listings.find(query, NO_VECTOR).sort(order).skip((page - 1) * per_page).limit(per_page)
    return {"total": db.listings.count_documents(query), "page": page, "per_page": per_page,
            "items": [listing_out(d) for d in docs]}


@router.get("/listings/sources")
def listing_sources(request: Request, user=Depends(current_user)):
    rows = request.app.state.db.listings.aggregate([
        {"$match": {"status": "active", "in_stock": True}},
        {"$group": {"_id": "$source_id", "brand": {"$first": "$brand"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}])
    return [{"source_id": r["_id"], "brand": r["brand"], "count": r["count"]} for r in rows]


@router.get("/listings/{listing_id}")
def get_one(listing_id: str, request: Request, user=Depends(current_user)):
    return listing_out(get_listing(request, listing_id))


@router.get("/listings/{listing_id}/image")
def listing_image(listing_id: str, request: Request, user=Depends(current_user)):
    doc = get_listing(request, listing_id)
    path = thumbnail_path(request.app.state.settings.storage_dir, doc["_id"])
    if not path.exists():
        raise HTTPException(404, "Image missing")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/listings/{listing_id}/candidate", status_code=201)
def listing_candidate(listing_id: str, request: Request, user=Depends(current_user)):
    """Copy the listing into the user's candidates (deleted after 24 h, like a scan),
    so /buy-advice and /similar work on it unchanged."""
    oid = object_id(listing_id)
    db = request.app.state.db
    doc = oid and db.listings.find_one({"_id": oid, "status": "active"})
    if not doc:
        raise HTTPException(404, "Listing not found")
    cand = {"user_id": user["_id"], "category": doc["category"], "sub_category": doc["sub_category"],
            "pattern": doc["pattern"], "colour": doc["colour"], "predicted": doc.get("predicted", {}),
            "vector": doc["vector"], "coverage": None, "season": [], "usage": [], "corrected": [],
            "listing_id": doc["_id"], "created_at": datetime.now(timezone.utc)}
    cand["_id"] = db.candidates.insert_one(cand).inserted_id
    storage = request.app.state.settings.storage_dir
    picture = thumbnail_path(storage, doc["_id"])
    if picture.exists():
        folder = storage / str(user["_id"])
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(picture, folder / f"{cand['_id']}.jpg")
    log_event(db, "scan", user["_id"], category=cand["category"], source="listing")
    return item_out(cand, kind="candidates")
