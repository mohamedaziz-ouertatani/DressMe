"""
Outfits (score, suggest, complete), "should I buy this?" and similar items.
All the fashion logic is in src/phase4/compatibility.py; this file only connects it
to the user's wardrobe and profile.
"""

import io
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility
import dress
import explain_outfit
import explain_similarity
import genders
import verdict

from ..db import vector_from_bson, vector_to_bson
from ..events import log_event
from ..schemas import BuyAdvice, Complete, ItemIds, OutfitFeedback
from ..security import current_user, gendered_user, user_gender
from ..vocab import SEASONS, USAGES
from ..wardrobe import candidate_view, item_out, outfit_out, short_item, to_compat
from .items import apply_update, own_item

router = APIRouter(tags=["outfits"])


def wardrobe(request, user):
    docs = list(request.app.state.db.items.find({"user_id": user["_id"]}))
    return docs, {str(d["_id"]): d for d in docs}


def profile(user, season=None, occasion=None, style_vector=None):
    """The personal filters of compatibility.filter_items."""
    return {"min_coverage": user["profile"].get("min_coverage"), "season": season,
            "occasion": occasion, "style_vector": style_vector}


def rules_of(user):
    """The team's rules for this user's gender (src/phase4/compatibility.rules_for)."""
    return compatibility.rules_for(user_gender(user))


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
    result = profile(user, season, occasion,
                     compatibility.user_style_profile(items, feedback, rules_of(user)))
    result["disliked_outfits"] = disliked_outfits
    return result


def no_clash(items, rules):
    """Hard rule: no sub_category twice, no category over its limit (else 422)."""
    why = compatibility.clashes(items, rules)
    if why:
        raise HTTPException(422, "These pieces can't be worn together: " + "; ".join(why))


def labelled_outfits(outfits, docs, prof, rules, dress_rules=None):
    """The outfits with `label` and `confidence` (src/phase4/dress.py). The taste vector is the one the
    scoring already uses; "usable" is the wardrobe left after this request's filters."""
    dress_rules = dress_rules or dress.load_rules()
    usable, _ = compatibility.filter_items([to_compat(d) for d in docs], prof, rules)
    return dress.label_outfits(outfits, {str(d["_id"]): candidate_view(d) for d in docs},
                               prof["style_vector"], dress_rules, usable=len(usable))


@router.get("/outfits/limits")
def limits(user=Depends(gendered_user)):
    """Max pieces per category (mappings/outfit_structure.csv); a sub_category is
    always at most one. The Build page uses this to swap pieces instead of stacking them."""
    return {"max_items": {c: int(n) for c, n in rules_of(user).max_items.items()},
            "max_per_sub_category": 1}


@router.post("/outfits/score")
def score(body: ItemIds, request: Request, user=Depends(gendered_user)):
    rules = rules_of(user)
    docs = [own_item(request, user, i) for i in body.item_ids]
    items = [to_compat(d) for d in docs]
    no_clash(items, rules)
    all_docs, _ = wardrobe(request, user)
    prof = user_profile(user, all_docs, request)
    result = compatibility.score_outfit(items, rules, style_profile=prof["style_vector"])
    labelled = labelled_outfits([{**result, "items": items}], all_docs, prof, rules)
    return outfit_out(labelled[0], {str(d["_id"]): d for d in docs}, explain=True, rules=rules)


@router.post("/outfits/explain")
def explain_outfit_route(body: ItemIds, request: Request, user=Depends(gendered_user)):
    """Why this score, in more depth: the best swap for each piece (from your own
    wardrobe, same filters as the suggestions) and how every pair of pieces works."""
    rules = rules_of(user)
    docs = [own_item(request, user, i) for i in body.item_ids]
    items = [to_compat(d) for d in docs]
    no_clash(items, rules)
    all_docs, by_id = wardrobe(request, user)
    prof = user_profile(user, all_docs, request)
    pool, _ = compatibility.filter_items([to_compat(d) for d in all_docs], prof, rules)
    swaps = explain_outfit.swaps(items, pool, rules, style_profile=prof["style_vector"])
    return {"swaps": [{"item_id": s["item_id"], "gain": s["gain"],
                       "swap": short_item(by_id[s["best_swap_id"]]) if s["best_swap_id"] else None}
                      for s in swaps],
            "weakest": explain_outfit.weakest(
                swaps, min_gain=explain_outfit.explain.load_settings()["min_swap_gain"]),
            "pair_map": explain_outfit.pair_map(items, rules)}


@router.post("/outfits/feedback")
def feedback(body: OutfitFeedback, request: Request, user=Depends(gendered_user)):
    docs = [own_item(request, user, item_id) for item_id in body.item_ids]
    items = [to_compat(d) for d in docs]
    no_clash(items, rules_of(user))
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
            n: int = Query(5, ge=1, le=20), beach: bool = False, user=Depends(gendered_user)):
    """beach=true: beach / pool outfits around a swimsuit (swimwear is left out otherwise)."""
    docs, by_id = wardrobe(request, user)
    prof = user_profile(user, docs, request, season, occasion)
    prof["beach"] = beach
    rules = rules_of(user)
    dress_rules = dress.load_rules()
    # TODO(step 2): wear_penalty_days and wear_penalty_points start at 0 (mappings/dress_rules.csv, REVIEW): the
    # team picks the values, then the suggestions start to rotate the pieces worn recently.
    penalty = dress.penalty_active(dress_rules)
    # the penalty re-orders a longer list (the first n of it are the outfits asked for without it, as each
    # piece is used in at most 2); with the penalty off nothing is fetched, re-ordered or changed
    outfits = compatibility.suggest_outfits([to_compat(d) for d in docs], prof, n=20 if penalty else n, rules=rules)
    if penalty:
        today = dress.tunis_date(datetime.now(timezone.utc))
        recent = request.app.state.db.wear_log.find(
            {"user_id": user["_id"], "worn_on": {"$gte": (today - timedelta(days=int(dress_rules["wear_penalty_days"]))).isoformat()}})
        outfits = dress.apply_wear_penalty(outfits, dress.recently_worn(recent, today, dress_rules["wear_penalty_days"]),
                                           dress_rules, n)
    outfits = labelled_outfits(outfits, docs, prof, rules, dress_rules)
    return [outfit_out(o, by_id, explain=True, rules=rules) for o in outfits]


@router.post("/outfits/complete")
def complete(body: Complete, request: Request, user=Depends(gendered_user)):
    rules = rules_of(user)
    chosen = [to_compat(own_item(request, user, i)) for i in body.item_ids]
    no_clash(chosen, rules)
    docs, by_id = wardrobe(request, user)
    candidates = [to_compat(d) for d in docs if str(d["_id"]) not in body.item_ids]
    prof = user_profile(user, docs, request)
    ranked = compatibility.complete_outfit(chosen, candidates, prof, k=body.k, rules=rules)
    labelled = labelled_outfits([{**r, "items": chosen + [r["item"]]} for r in ranked], docs, prof, rules)
    return [{**outfit_out(o, by_id, explain=True, rules=rules), "item": item_out(by_id[r["item"]["id"]])}
            for o, r in zip(labelled, ranked)]


@router.post("/buy-advice")
def buy_advice(body: BuyAdvice, request: Request, user=Depends(gendered_user)):
    """A candidate from /analyze (optionally corrected) vs the wardrobe."""
    cand = own_item(request, user, body.candidate_id, collection="candidates")
    changes = apply_update(cand, body.corrections) if body.corrections else {}
    if body.price_tnd is not None:
        changes["price_tnd"] = body.price_tnd      # the price on the tag; not given = unknown, kept as it was
    if changes:
        # saved, so /tryon and the chat's last scan see the corrected item too
        request.app.state.db.candidates.update_one({"_id": cand["_id"]}, {"$set": changes})
        cand = {**cand, **changes}
    docs, by_id = wardrobe(request, user)
    by_id[str(cand["_id"])] = cand
    rules = rules_of(user)
    owned = [to_compat(d) for d in docs]
    prof = user_profile(user, docs, request)
    advice = compatibility.buy_advice(to_compat(cand), owned, prof, rules)
    log_event(request.app.state.db, "verdict", user["_id"], verdict=advice["verdict"])
    # how far to trust it, and why (src/phase4/verdict.py): reads the advice, never changes it
    assessed = verdict.assess(
        advice, candidate_view(cand), owned, {**prof, "budget_tnd": user["profile"].get("budget_tnd")},
        compatibility.wardrobe_insights(owned, prof, rules), rules)
    s = rules.settings
    request.app.state.db.candidates.update_one({"_id": cand["_id"]}, {"$set": {"last_advice": {
        "verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
        "codes": assessed["codes"], "confidence": assessed["confidence"],
        "thresholds": {"good_outfit": s["good_outfit"], "buy_min": int(s["buy_min_outfits"]),
                       "think_min": int(s["think_min_outfits"])},
        "price_tnd": cand.get("price_tnd"), "computed_at": datetime.now(timezone.utc)}}})
    # why this verdict: owned ids become short items the app can show with their photo
    why = explain_outfit.buy_explanation(advice, rules)
    explanation = {**why,
                   "beats": [{**b, "owned": short_item(by_id[b["owned_id"]]) if b["owned_id"] else None}
                             for b in why["beats"]],
                   "lost_to": [{**l, "owned": short_item(by_id[l["owned_id"]])} for l in why["lost_to"]],
                   "twins": [{"item": short_item(by_id[t["id"]]), "similarity": t["similarity"]}
                             for t in why["twins"]]}
    return {"verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
            "reasons": advice["reasons"],
            "confidence": assessed["confidence"], "codes": assessed["codes"],      # new in step 1
            "candidate": item_out(cand, kind="candidates"),
            "best": [outfit_out(o, by_id, explain=True, rules=rules) for o in advice["best"]],
            "explanation": explanation}


@router.get("/similar")
def similar(request: Request, item_id: str | None = None, candidate_id: str | None = None,
            k: int = Query(6, ge=1, le=20), gender: Literal["mine", "all"] = "mine",
            user=Depends(gendered_user)):
    """gender=all: also the other gender's pieces (default: the user's gender + unisex).
    Look-alikes in your wardrobe ('you already have this'), dataset inspiration,
    H&M products ('shop', no price or stock) and shop listings in stock now ('listings')."""
    if bool(item_id) == bool(candidate_id):
        raise HTTPException(422, "Give exactly one of item_id or candidate_id")
    doc = own_item(request, user, item_id or candidate_id,
                   collection="items" if item_id else "candidates")
    query = vector_from_bson(doc.get("vector"))
    docs, _ = wardrobe(request, user)
    mine = sorted(((float(vector_from_bson(d["vector"]) @ query), d) for d in docs
                   if d["_id"] != doc["_id"] and d.get("vector")), key=lambda x: -x[0])[:k]
    shown = None if gender == "all" else genders.shown(user_gender(user))
    catalog = request.app.state.catalog.search(query, k=k, category=doc["category"], genders=shown)
    shop = request.app.state.catalog.search_shop(query, k=k, category=doc["category"], genders=shown)
    for c in catalog + shop:
        c["image_url"] = f"/catalog/{c['id']}/image"
    listings = request.app.state.listing_index.search(
        request.app.state.db, query, k=k + 1, category=doc["category"], genders=shown)
    # a candidate made from a listing: leave the listing itself out
    listings = [x for x in listings if x["id"] != str(doc.get("listing_id"))][:k]

    # why each one looks alike (XAI): shared labels + what the picture model
    # associates with both pictures; the vectors themselves never leave the server
    concepts = request.app.state.analyzer.concept_vectors(user_gender(user))
    baseline = explain_similarity.concept_baseline(request.app.state.catalog.mean_vector(), concepts)
    explain = lambda hit, vector: explain_similarity.explain_pair(doc, hit, query, vector, concepts,
                                                                  baseline=baseline)
    out_mine = [{**item_out(d), "similarity": round(s, 3)} for s, d in mine]
    for hit, (_, d) in zip(out_mine, mine):
        hit["why"] = explain(hit, vector_from_bson(d["vector"]))
    for hit in catalog + shop:
        hit["why"] = explain(hit, request.app.state.catalog.vector(hit["id"]))
    for hit in listings:
        hit["why"] = explain(hit, request.app.state.listing_index.vector(request.app.state.db, hit["id"]))
    return {"wardrobe": out_mine, "catalog": catalog, "shop": shop, "listings": listings}


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
