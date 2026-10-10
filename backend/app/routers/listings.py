"""
Listings: things people can buy now (see LISTINGS.md).
  - shop products collected by src/phase4/collect_listings.py (shared by every user);
  - friperie sellers' own items, posted here and approved by an admin.

    GET    /listings                 browse active listings, with filters (in stock only by default)
    GET    /listings/sources         the sources that have listings (for the filter)
    GET    /listings/mine            the seller's own listings, every status
    POST   /listings/sell            a seller posts an item (photo + price + size + city + contact)
    GET    /listings/{id}            one listing
    GET    /listings/{id}/image      its picture
    PATCH  /listings/{id}            the seller corrects it, or marks it sold
    DELETE /listings/{id}            the seller removes it
    POST   /listings/{id}/candidate  "Should I buy this?": the listing becomes one of the
                                     user's candidates, then the app calls /buy-advice

A seller listing starts "pending" and only shows to others once an admin
approves it (/admin/listings). Changing its title, city or contact sends it
back to review. Pending or rejected listings answer 404 to everyone but
their seller and the admins, and another user's listing can never be changed.
"""

import shutil
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db import object_id
from ..events import log_event
from .. import ml  # noqa: F401  (puts src/ on the import path)
import genders

from ..listings import SELLERS, listing_out, listing_query, thumbnail_path
from ..schemas import ItemUpdate
from ..security import current_user, gendered_user, user_gender
from ..wardrobe import item_out
from .items import analyse, apply_update, read_photo

router = APIRouter(tags=["listings"])
NO_VECTOR = {"vector": 0}      # 1 KB per listing the app never needs
SELLER_PICTURE_SIDE = 640      # a seller's photo is the only picture buyers get: keep it bigger
MAX_PENDING = 20               # per seller, so nobody floods the review queue
REVIEWED_FIELDS = {"title", "city", "contact"}   # free text: a change goes back to review


def visible_to(doc, user):
    """Pending / rejected seller listings: only their seller and the admins see them."""
    if doc.get("status") in ("pending", "rejected"):
        return doc.get("seller_id") == user["_id"] or user.get("role") == "admin"
    return True


def get_listing(request, listing_id, user):
    oid = object_id(listing_id)
    doc = oid and request.app.state.db.listings.find_one({"_id": oid}, NO_VECTOR)
    if not doc or not visible_to(doc, user):
        raise HTTPException(404, "Listing not found")
    return doc


def own_listing(request, listing_id, user):
    """The user's own seller listing, or 404 (also for other people's: never reveal they exist)."""
    oid = object_id(listing_id)
    doc = oid and request.app.state.db.listings.find_one(
        {"_id": oid, "source_id": SELLERS, "seller_id": user["_id"]}, NO_VECTOR)
    if not doc:
        raise HTTPException(404, "Listing not found")
    return doc


def search_changed(request):
    """A listing appeared, disappeared or changed category: /similar must reload."""
    request.app.state.listing_index.invalidate()


@router.get("/listings")
def list_listings(request: Request, category: str | None = None, sub_category: str | None = None,
                  colour: str | None = None, size: str | None = None, source: str | None = None,
                  max_price: float | None = Query(None, ge=0), in_stock: bool = True,
                  sort: Literal["new", "price"] = "new", gender: Literal["mine", "all"] = "mine",
                  page: int = Query(1, ge=1), per_page: int = Query(24, ge=1, le=100),
                  user=Depends(gendered_user)):
    """`size` matches the sizes the product comes in; its stock per size is only
    known when availability_level = colour (then see sizes_in_stock).
    gender=all: also the other gender's pieces (default: the user's gender + unisex)."""
    shown = None if gender == "all" else genders.shown(user_gender(user))
    query = listing_query(category, sub_category, colour, size, source, max_price, in_stock,
                          genders=shown)
    order = [("price_tnd", 1), ("_id", 1)] if sort == "price" else [("created_at", -1), ("_id", -1)]
    db = request.app.state.db
    docs = db.listings.find(query, NO_VECTOR).sort(order).skip((page - 1) * per_page).limit(per_page)
    return {"total": db.listings.count_documents(query), "page": page, "per_page": per_page,
            "items": [listing_out(d) for d in docs]}


@router.get("/listings/sources")
def listing_sources(request: Request, user=Depends(current_user)):
    """One line per source with active listings; `brands` = the brands inside it
    (the snapshot mixes Zara, Bershka and Pull&Bear; sellers have none)."""
    rows = request.app.state.db.listings.aggregate([
        {"$match": {"status": "active", "in_stock": True}},
        {"$group": {"_id": "$source_id", "brands": {"$addToSet": "$brand"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}])
    return [{"source_id": r["_id"], "brands": sorted(b for b in r["brands"] if b), "count": r["count"]}
            for r in rows]


@router.get("/listings/mine")
def my_listings(request: Request, user=Depends(current_user)):
    docs = request.app.state.db.listings.find(
        {"source_id": SELLERS, "seller_id": user["_id"]}, NO_VECTOR).sort("created_at", -1)
    return [listing_out(d) for d in docs]


def text(value, name, longest, required=True):
    value = (value or "").strip()
    if required and not value:
        raise HTTPException(422, f"{name} is required")
    if len(value) > longest:
        raise HTTPException(422, f"{name}: at most {longest} characters")
    return value


@router.post("/listings/sell", status_code=201)
async def sell(request: Request, photo: UploadFile = File(...),
               price_tnd: float = Form(..., gt=0, le=100000), size: str = Form(""),
               city: str = Form(...), contact: str = Form(...), title: str = Form(""),
               user=Depends(gendered_user)):
    """A friperie seller posts one item. The photo is cleaned and analysed like a
    wardrobe upload; the listing waits for an admin before anyone else sees it."""
    db = request.app.state.db
    if db.listings.count_documents({"source_id": SELLERS, "seller_id": user["_id"],
                                    "status": "pending"}) >= MAX_PENDING:
        raise HTTPException(429, f"You already have {MAX_PENDING} listings waiting for review")
    fields = {"size": text(size, "size", 20, required=False), "city": text(city, "city", 40),
              "contact": text(contact, "contact", 60), "title": text(title, "title", 80, required=False)}
    img = await read_photo(photo, request)
    analysed = analyse(img, user, request)        # the same fields as an upload
    now = datetime.now(timezone.utc)
    lid = ObjectId()
    doc = {
        "_id": lid, "source_id": SELLERS, "external_id": str(lid), "seller_id": user["_id"],
        # a seller lists for their own side (REVIEW, see LISTINGS.md)
        "title": fields["title"], "brand": "", "shop_colour": "", "gender": user_gender(user), "url": "",
        "price_tnd": round(price_tnd, 3), "sizes": [fields["size"]] if fields["size"] else [],
        "sizes_in_stock": [fields["size"]] if fields["size"] else [], "in_stock": True,
        "availability_level": "colour", "image_url": "", "city": fields["city"],
        "contact": fields["contact"], "status": "pending", "review_note": "",
        "created_at": now, "seen_at": now, "checked_at": None, "snapshot": False,
        **{k: analysed[k] for k in ("category", "sub_category", "pattern", "colour", "predicted",
                                    "vector", "corrected")},
    }
    path = thumbnail_path(request.app.state.settings.storage_dir, lid)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.thumbnail((SELLER_PICTURE_SIDE, SELLER_PICTURE_SIDE))
    img.save(path, quality=85)
    db.listings.insert_one(doc)
    doc.pop("vector")
    return listing_out(doc)


@router.get("/listings/{listing_id}")
def get_one(listing_id: str, request: Request, user=Depends(current_user)):
    return listing_out(get_listing(request, listing_id, user))


@router.get("/listings/{listing_id}/image")
def listing_image(listing_id: str, request: Request, user=Depends(current_user)):
    doc = get_listing(request, listing_id, user)
    path = thumbnail_path(request.app.state.settings.storage_dir, doc["_id"])
    if not path.exists():
        raise HTTPException(404, "Image missing")
    return FileResponse(path, media_type="image/jpeg")


class ListingUpdate(BaseModel):
    """What a seller may change. Only the fields sent are changed."""
    category: str | None = None
    sub_category: str | None = None
    pattern: str | None = None
    colour: str | None = None
    price_tnd: float | None = Field(None, gt=0, le=100000)
    size: str | None = Field(None, max_length=20)
    city: str | None = Field(None, min_length=1, max_length=40)
    contact: str | None = Field(None, min_length=1, max_length=60)
    title: str | None = Field(None, max_length=80)
    sold: bool | None = None


@router.patch("/listings/{listing_id}")
def update_listing(listing_id: str, body: ListingUpdate, request: Request, user=Depends(current_user)):
    doc = own_listing(request, listing_id, user)
    sent = body.model_dump(exclude_unset=True)
    labels = {k: sent.pop(k) for k in ("category", "sub_category", "pattern", "colour") if k in sent}
    changes = apply_update(doc, ItemUpdate(**labels)) if labels else {}
    if "price_tnd" in sent:
        changes["price_tnd"] = round(sent["price_tnd"], 3)
    if "size" in sent:
        size = (sent["size"] or "").strip()
        changes["sizes"] = changes["sizes_in_stock"] = [size] if size else []
    for key in REVIEWED_FIELDS & set(sent):
        changes[key] = (sent[key] or "").strip()
    if sent.get("sold"):
        changes.update(status="gone", in_stock=False)
    elif REVIEWED_FIELDS & set(sent) and doc["status"] in ("active", "rejected"):
        changes.update(status="pending", review_note="")     # new text: an admin looks again
    if changes:
        request.app.state.db.listings.update_one({"_id": doc["_id"]}, {"$set": changes})
        search_changed(request)
    return listing_out(own_listing(request, listing_id, user))


@router.delete("/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: str, request: Request, user=Depends(current_user)):
    doc = own_listing(request, listing_id, user)
    request.app.state.db.listings.delete_one({"_id": doc["_id"]})
    thumbnail_path(request.app.state.settings.storage_dir, doc["_id"]).unlink(missing_ok=True)
    search_changed(request)


@router.post("/listings/{listing_id}/candidate", status_code=201)
def listing_candidate(listing_id: str, request: Request, user=Depends(gendered_user)):
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


def delete_seller_listings(db, storage_dir, user_id):
    """When an account is deleted, its seller listings and pictures go too."""
    for doc in db.listings.find({"source_id": SELLERS, "seller_id": user_id}, {"_id": 1}):
        thumbnail_path(storage_dir, doc["_id"]).unlink(missing_ok=True)
    db.listings.delete_many({"source_id": SELLERS, "seller_id": user_id})
