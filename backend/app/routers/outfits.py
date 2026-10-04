"""
Outfits (score, suggest, complete), "should I buy this?" and similar items.
All the fashion logic is in src/compatibility.py; this file only connects it
to the user's wardrobe and profile.
"""

import io
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..db import vector_from_bson, vector_to_bson
from ..events import log_event
from ..schemas import BuyAdvice, Complete, ItemIds, OutfitFeedback
from ..security import current_user
from ..vocab import SEASONS, USAGES
from ..wardrobe import item_out, outfit_out, to_compat
from .items import apply_update, own_item

router = APIRouter(tags=["outfits"])


def wardrobe(request, user):
    docs = list(request.app.state.db.items.find({"user_id": user["_id"]}))
    return docs, {str(d["_id"]): d for d in docs}


def profile(user, season=None, occasion=None, style_vector=None):
    """The personal filters of compatibility.filter_items."""
    return {"min_coverage": user["profile"].get("min_coverage"), "season": season,
            "occasion": occasion, "style_vector": style_vector}


def user_profile(user, docs, request=None, season=None, occasion=None):
    """Build the request-scoped profile, including implicit style preferences."""
    items = [to_compat(d) for d in docs]
    feedback_collection = getattr(request.app.state.db, "outfit_feedback", None) \
        if request is not None else None
    feedback = list(feedback_collection.find({"user_id": user["_id"]})) \
        if feedback_collection is not None else []
    disliked_outfits = set()
    for entry in feedback:
        entry["vector"] = vector_from_bson(entry.get("vector"))
        if entry.get("rating") == -1:
            disliked_outfits.add(entry["outfit_key"])
    result = profile(user, season, occasion, compatibility.user_style_profile(items, feedback))
    result["disliked_outfits"] = disliked_outfits
    return result


def no_clash(items):
    """Hard rule: no sub_category twice, no category over its limit (else 422)."""
    why = compatibility.clashes(items)
    if why:
        raise HTTPException(422, "These pieces can't be worn together: " + "; ".join(why))


@router.get("/outfits/limits")
def limits(user=Depends(current_user)):
    """Max pieces per category (mappings/outfit_structure.csv); a sub_category is
    always at most one. The Build page uses this to swap pieces instead of stacking them."""
    return {"max_items": {c: int(n) for c, n in compatibility.RULES.max_items.items()},
            "max_per_sub_category": 1}


@router.post("/outfits/score")
def score(body: ItemIds, request: Request, user=Depends(current_user)):
    docs = [own_item(request, user, i) for i in body.item_ids]
    items = [to_compat(d) for d in docs]
    no_clash(items)
    all_docs, _ = wardrobe(request, user)
    result = compatibility.score_outfit(
        items, style_profile=user_profile(user, all_docs, request)["style_vector"])
    return outfit_out({**result, "items": items}, {str(d["_id"]): d for d in docs})


@router.post("/outfits/feedback")
def feedback(body: OutfitFeedback, request: Request, user=Depends(current_user)):
    docs = [own_item(request, user, item_id) for item_id in body.item_ids]
    items = [to_compat(d) for d in docs]
    no_clash(items)
    vector = compatibility.outfit_vector(items)
    if vector is None:
        raise HTTPException(422, "At least one outfit item needs a style vector")
    key = "|".join(sorted(body.item_ids))
    request.app.state.db.outfit_feedback.update_one(
        {"user_id": user["_id"], "outfit_key": key},
        {"$set": {"item_ids": sorted(body.item_ids), "rating": body.rating,
                  "vector": vector_to_bson(vector),
                  "updated_at": datetime.now(timezone.utc)}},
        upsert=True)
    return {"item_ids": sorted(body.item_ids), "rating": body.rating}


Season = Literal[tuple(SEASONS)]       # only these values are accepted (else 422)
Occasion = Literal[tuple(USAGES)]


@router.get("/outfits/suggest")
def suggest(request: Request, season: Season | None = None, occasion: Occasion | None = None,
            n: int = Query(5, ge=1, le=20), user=Depends(current_user)):
    docs, by_id = wardrobe(request, user)
    outfits = compatibility.suggest_outfits(
        [to_compat(d) for d in docs], user_profile(user, docs, request, season, occasion), n=n)
    return [outfit_out(o, by_id) for o in outfits]


@router.post("/outfits/complete")
def complete(body: Complete, request: Request, user=Depends(current_user)):
    chosen = [own_item(request, user, i) for i in body.item_ids]
    no_clash([to_compat(d) for d in chosen])
    docs, by_id = wardrobe(request, user)
    candidates = [to_compat(d) for d in docs if str(d["_id"]) not in body.item_ids]
    ranked = compatibility.complete_outfit(
        [to_compat(d) for d in chosen], candidates, user_profile(user, docs, request), k=body.k)
    return [{**outfit_out(r, by_id), "item": item_out(by_id[r["item"]["id"]])} for r in ranked]


@router.post("/buy-advice")
def buy_advice(body: BuyAdvice, request: Request, user=Depends(current_user)):
    """A candidate from /analyze (optionally corrected) vs the wardrobe."""
    cand = own_item(request, user, body.candidate_id, collection="candidates")
    if body.corrections:
        changes = apply_update(cand, body.corrections)
        # saved, so /tryon and the chat's last scan see the corrected item too
        request.app.state.db.candidates.update_one({"_id": cand["_id"]}, {"$set": changes})
        cand = {**cand, **changes}
    docs, by_id = wardrobe(request, user)
    by_id[str(cand["_id"])] = cand
    advice = compatibility.buy_advice(
        to_compat(cand), [to_compat(d) for d in docs], user_profile(user, docs, request))
    log_event(request.app.state.db, "verdict", user["_id"], verdict=advice["verdict"])
    return {"verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
            "reasons": advice["reasons"], "candidate": item_out(cand, kind="candidates"),
            "best": [outfit_out(o, by_id) for o in advice["best"]]}


@router.get("/similar")
def similar(request: Request, item_id: str | None = None, candidate_id: str | None = None,
            k: int = Query(6, ge=1, le=20), user=Depends(current_user)):
    """Look-alikes in your wardrobe ('you already have this'), dataset inspiration,
    H&M products ('shop', no price or stock) and shop listings in stock now ('listings')."""
    if bool(item_id) == bool(candidate_id):
        raise HTTPException(422, "Give exactly one of item_id or candidate_id")
    doc = own_item(request, user, item_id or candidate_id,
                   collection="items" if item_id else "candidates")
    query = vector_from_bson(doc.get("vector"))
    docs, _ = wardrobe(request, user)
    mine = sorted(((float(vector_from_bson(d["vector"]) @ query), d) for d in docs
                   if d["_id"] != doc["_id"] and d.get("vector")), key=lambda x: -x[0])[:k]
    catalog = request.app.state.catalog.search(query, k=k, category=doc["category"])
    shop = request.app.state.catalog.search_shop(query, k=k, category=doc["category"])
    for c in catalog + shop:
        c["image_url"] = f"/catalog/{c['id']}/image"
    listings = request.app.state.listing_index.search(
        request.app.state.db, query, k=k + 1, category=doc["category"])
    # a candidate made from a listing: leave the listing itself out
    listings = [x for x in listings if x["id"] != str(doc.get("listing_id"))][:k]
    return {"wardrobe": [{**item_out(d), "similarity": round(s, 3)} for s, d in mine],
            "catalog": catalog, "shop": shop, "listings": listings}


@router.get("/catalog/{item_id}/image")
def catalog_image(item_id: str, request: Request, user=Depends(current_user)):
    """A dataset product shot (academic use only: served to logged-in users, never published)."""
    img = request.app.state.catalog.image(item_id)
    if img is None:
        raise HTTPException(404, "Not in the catalog")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")
