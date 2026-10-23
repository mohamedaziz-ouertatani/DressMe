"""
The wear log (step 2 of the upgrade): what the user wore, day by day.

    POST   /wear          {item_ids, occasion?, event_name?, score_shown?, label_shown?, source: card | build}
    GET    /wear          ?from=YYYY-MM-DD&to=YYYY-MM-DD (both optional): the user's entries, newest first
    DELETE /wear/{id}     undo; only on the day it was worn (Tunis time), else 409

`worn_on` is the calendar date in Africa/Tunis, computed here on the server (src/phase4/dress.py), never
taken from the app. The same set of pieces on the same day is one entry: the second POST returns the first
(200), so a double tap or a reload never doubles the log. Every piece must be the user's own (else 404).
No screen shows the history yet: it comes with the wardrobe view (step 5).
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from .. import ml  # noqa: F401  (puts src/ on the import path)
import dress

from ..db import object_id
from ..events import log_event
from ..schemas import WearIn
from ..security import current_user
from .items import own_item

router = APIRouter(tags=["wear"])


def entry_out(doc):
    return {"id": str(doc["_id"]), "item_ids": doc["item_ids"], "worn_on": doc["worn_on"],
            "occasion": doc.get("occasion"), "event_name": doc.get("event_name"),
            "score_shown": doc.get("score_shown"), "label_shown": doc.get("label_shown"),
            "source": doc["source"], "created_at": doc["created_at"].isoformat()}


def today():
    return dress.tunis_date(datetime.now(timezone.utc)).isoformat()


@router.post("/wear", status_code=201)
def wear(body: WearIn, request: Request, response: Response, user=Depends(current_user)):
    db = request.app.state.db
    ids = list(dict.fromkeys(body.item_ids))            # the same piece twice counts once
    for item_id in ids:
        own_item(request, user, item_id)                 # 404: not theirs
    day = today()
    existing = db.wear_log.find_one({"user_id": user["_id"], "worn_on": day,
                                     "item_ids": {"$all": ids, "$size": len(ids)}})
    if existing:
        response.status_code = 200
        return entry_out(existing)
    doc = {"user_id": user["_id"], "item_ids": ids, "worn_on": day, "occasion": body.occasion or None,
           "event_name": body.event_name or None, "score_shown": body.score_shown,
           "label_shown": body.label_shown, "source": body.source, "created_at": datetime.now(timezone.utc)}
    doc["_id"] = db.wear_log.insert_one(doc).inserted_id
    log_event(db, "wear", user["_id"], source=body.source, pieces=len(ids))
    return entry_out(doc)


@router.get("/wear")
def wear_list(request: Request, from_: date | None = Query(None, alias="from"), to: date | None = None,
              user=Depends(current_user)):
    query = {"user_id": user["_id"]}
    if from_ or to:
        query["worn_on"] = {**({"$gte": from_.isoformat()} if from_ else {}), **({"$lte": to.isoformat()} if to else {})}
    docs = request.app.state.db.wear_log.find(query).sort([("worn_on", -1), ("created_at", -1)]).limit(500)
    return [entry_out(d) for d in docs]


@router.delete("/wear/{entry_id}", status_code=204)
def undo(entry_id: str, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    oid = object_id(entry_id)
    doc = oid and db.wear_log.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(404, "Entry not found")      # also another user's entry
    if doc["worn_on"] != today():
        raise HTTPException(409, "Only today's entries can be removed")
    db.wear_log.delete_one({"_id": doc["_id"]})
