"""
The decision log: what the user did after "Should I buy this?".

    POST /decisions   {candidate_id, answer: "bought" | "left", price_paid?}
    GET  /decisions   the user's decisions, newest first

A decision keeps the piece's labels, a copy of what the app showed (the scan's `last_advice`: verdict,
confidence, codes, thresholds, price), the item made when the answer is "bought", and never the photo.
One decision per user and scan (unique index): the same answer again returns it, another answer is a
409. "bought" saves the scan into the wardrobe with `promote` (no second analysis).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError

from ..events import log_event
from ..schemas import DecisionIn
from ..security import current_user
from ..wardrobe_store import promote
from .items import load_photo, own_item

router = APIRouter(tags=["decisions"])


# TODO(step 1): `price_paid` is accepted and saved but no screen asks for it yet, and a decision
# cannot be changed (a different answer is a 409). The full version: ask the price when the user taps
# Bought it, allow changing a "Left it" later (a Left it today has nothing to undo, a Bought it has an item),
# and read the log back for the step 6 / learning rules.
def decision_out(doc):
    return {
        "id": str(doc["_id"]), "candidate_id": doc["candidate_id"],
        "listing_id": str(doc["listing_id"]) if doc.get("listing_id") else None,
        "answer": doc["answer"], "price_tnd": doc.get("price_tnd"), "price_paid": doc.get("price_paid"),
        "category": doc.get("category", ""), "sub_category": doc.get("sub_category", ""),
        "colour": doc.get("colour", ""), "pattern": doc.get("pattern", ""),
        "last_advice": {**doc["last_advice"], "computed_at": doc["last_advice"]["computed_at"].isoformat()},
        "item_id": str(doc["item_id"]) if doc.get("item_id") else None,
        "created_at": doc["created_at"].isoformat(),
    }


def answered(existing, answer, response):
    """The earlier decision when the answer is the same (200), else 409."""
    if existing["answer"] != answer:
        raise HTTPException(409, f"You already answered '{existing['answer']}' for this piece")
    response.status_code = 200
    return decision_out(existing)


@router.post("/decisions", status_code=201)
def decide(body: DecisionIn, request: Request, response: Response, user=Depends(current_user)):
    db = request.app.state.db
    cand = own_item(request, user, body.candidate_id, collection="candidates")     # 404: not theirs, or expired
    if not cand.get("last_advice"):
        raise HTTPException(409, "No verdict has been shown for this piece yet")
    candidate_id = str(cand["_id"])
    existing = db.decisions.find_one({"user_id": user["_id"], "candidate_id": candidate_id})
    if existing:
        return answered(existing, body.answer, response)

    item_id = None
    if body.answer == "bought":
        item, _ = promote(db, request.app.state.settings.storage_dir, user["_id"], candidate=cand,
                          photo=load_photo(request, user, cand))
        item_id = item["_id"]
    doc = {"user_id": user["_id"], "candidate_id": candidate_id, "listing_id": cand.get("listing_id"),
           "answer": body.answer, "price_tnd": cand.get("price_tnd"), "price_paid": body.price_paid,
           "category": cand.get("category", ""), "sub_category": cand.get("sub_category", ""),
           "colour": cand.get("colour", ""), "pattern": cand.get("pattern", ""),
           "last_advice": cand["last_advice"], "item_id": item_id, "created_at": datetime.now(timezone.utc)}
    try:
        doc["_id"] = db.decisions.insert_one(doc).inserted_id
    except DuplicateKeyError:                       # an identical request got there first
        return answered(db.decisions.find_one({"user_id": user["_id"], "candidate_id": candidate_id}),
                        body.answer, response)
    log_event(db, "decision", user["_id"], answer=body.answer, verdict=cand["last_advice"]["verdict"])
    # from the stored document, so the first answer and a repeat are identical (MongoDB keeps milliseconds)
    return decision_out(db.decisions.find_one({"_id": doc["_id"]}))


@router.get("/decisions")
def list_decisions(request: Request, user=Depends(current_user)):
    docs = request.app.state.db.decisions.find({"user_id": user["_id"]}).sort([("created_at", -1), ("_id", -1)])
    return [decision_out(d) for d in docs]
