"""
Admin dashboard API (admins only: python -m app.make_admin <email>).

    GET    /admin/stats           usage per day + totals
    GET    /admin/model-quality   how often users correct each predicted field
    GET    /admin/users           list / search accounts
    PATCH  /admin/users/{id}      disable / enable, change role
    DELETE /admin/users/{id}      delete an account and everything it owns
    GET    /admin/formula         compatibility weights and settings (+ rule tables)
    PUT    /admin/formula         edit them: rewrites mappings/compatibility_weights.csv
    GET    /admin/sources         listing sources (mappings/listing_sources.csv) + their last runs
"""

import csv
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..db import object_id
from ..events import EVENT_TYPES
from ..listings import last_run, load_sources, usable
from ..ml import colour_min_confidence
from ..security import current_admin
from ..wardrobe import PREDICTED_FIELDS

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(current_admin)])
WEIGHTS_FILE = "compatibility_weights.csv"


# ------------------------------------------------------------------ stats
@router.get("/stats")
def stats(request: Request, days: int = Query(30, ge=1, le=365)):
    db = request.app.state.db
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.events.aggregate([
        {"$match": {"at": {"$gte": since}}},
        {"$group": {"_id": {"day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$at"}},
                            "type": "$type"}, "n": {"$sum": 1}}},
    ])
    per_day = {}
    for r in rows:
        per_day.setdefault(r["_id"]["day"], {t: 0 for t in EVENT_TYPES})[r["_id"]["type"]] = r["n"]
    verdicts = Counter(e.get("verdict") for e in db.events.find({"type": "verdict", "at": {"$gte": since}},
                                                               {"verdict": 1}))
    active = db.events.distinct("user_id", {"at": {"$gte": since}})
    return {
        "days": days,
        "per_day": [{"day": d, **per_day[d]} for d in sorted(per_day)],
        "totals": {"users": db.users.count_documents({}), "active_users": len(active),
                   "items": db.items.count_documents({}),
                   **{t: sum(v[t] for v in per_day.values()) for t in EVENT_TYPES}},
        "verdicts": {v: verdicts.get(v, 0) for v in ("buy", "think", "skip")},
    }


# ------------------------------------------------------------------ model quality
@router.get("/model-quality")
def model_quality(request: Request):
    """Per predicted field: share of wardrobe items whose value the user changed,
    and the most frequent changes (model said X, user set Y)."""
    items = list(request.app.state.db.items.find({}, {"predicted": 1, "corrected": 1,
                                                      **{f: 1 for f in PREDICTED_FIELDS}}))
    fields = []
    for f in PREDICTED_FIELDS:
        with_pred = [d for d in items if f in d.get("predicted", {})]
        changed = [d for d in with_pred
                   if f in d.get("corrected", []) and d[f] != d["predicted"][f]["value"]]
        pairs = Counter((d["predicted"][f]["value"], d[f] or "(empty)") for d in changed)
        fields.append({
            "field": f, "items": len(with_pred), "corrected": len(changed),
            "rate": round(len(changed) / len(with_pred), 4) if with_pred else None,
            "mean_confidence": round(sum(d["predicted"][f]["conf"] for d in with_pred) / len(with_pred), 3)
            if with_pred else None,
            "top_changes": [{"predicted": p, "corrected": c, "n": n} for (p, c), n in pairs.most_common(5)],
        })
    with_colour = [d for d in items if "colour" in d.get("predicted", {})]
    low = [d for d in with_colour if d["predicted"]["colour"]["conf"] < colour_min_confidence()]
    return {"items": len(items), "fields": fields,
            "colour_below_cut": {"items": len(low),
                                 "rate": round(len(low) / len(with_colour), 4) if with_colour else None,
                                 "cut": colour_min_confidence()}}


# ------------------------------------------------------------------ users
def user_row(u, item_counts):
    return {"id": str(u["_id"]), "email": u["email"], "name": u["profile"].get("name"),
            "role": u.get("role", "user"), "disabled": bool(u.get("disabled")),
            "items": item_counts.get(u["_id"], 0), "created_at": u.get("created_at")}


@router.get("/users")
def list_users(request: Request, q: str = "", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = request.app.state.db
    query = {"email": {"$regex": re.escape(q.lower())}} if q else {}
    total = db.users.count_documents(query)
    users = list(db.users.find(query).sort("created_at", -1).skip((page - 1) * size).limit(size))
    counts = {r["_id"]: r["n"] for r in db.items.aggregate([
        {"$match": {"user_id": {"$in": [u["_id"] for u in users]}}},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}}])}
    return {"total": total, "page": page, "size": size, "users": [user_row(u, counts) for u in users]}


class UserUpdate(BaseModel):
    disabled: bool | None = None
    role: Literal["user", "admin"] | None = None


def other_user(request, admin, user_id):
    oid = object_id(user_id)
    user = oid and request.app.state.db.users.find_one({"_id": oid})
    if not user:
        raise HTTPException(404, "User not found")
    if user["_id"] == admin["_id"]:
        raise HTTPException(400, "You cannot change or delete your own admin account here")
    return user


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserUpdate, request: Request, admin=Depends(current_admin)):
    user = other_user(request, admin, user_id)
    changes = body.model_dump(exclude_unset=True)
    if changes:
        request.app.state.db.users.update_one({"_id": user["_id"]}, {"$set": changes})
    user = request.app.state.db.users.find_one({"_id": user["_id"]})
    return user_row(user, {user["_id"]: request.app.state.db.items.count_documents({"user_id": user["_id"]})})


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, request: Request, admin=Depends(current_admin)):
    user = other_user(request, admin, user_id)
    db = request.app.state.db
    for coll in ("items", "candidates", "chats", "events", "outfit_feedback"):
        db[coll].delete_many({"user_id": user["_id"]})
    db.users.delete_one({"_id": user["_id"]})
    shutil.rmtree(request.app.state.settings.storage_dir / str(user["_id"]), ignore_errors=True)


# ------------------------------------------------------------------ formula
def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@router.get("/formula")
def get_formula(request: Request):
    folder = request.app.state.settings.mappings_dir
    return {
        "settings": [{"name": r["name"], "value": float(r["value"]), "note": r["note"]}
                     for r in read_csv(folder / WEIGHTS_FILE)],
        "colour_harmony": read_csv(folder / "colour_harmony.csv"),
        "pattern_mixing": read_csv(folder / "pattern_mixing.csv"),
        "file": f"mappings/{WEIGHTS_FILE}",
    }


class FormulaUpdate(BaseModel):
    values: dict[str, float]


@router.put("/formula")
def put_formula(body: FormulaUpdate, request: Request):
    """Change values in mappings/compatibility_weights.csv (notes and order kept),
    then reload the formula so the app uses them at once."""
    path = request.app.state.settings.mappings_dir / WEIGHTS_FILE
    rows = read_csv(path)
    current = {r["name"]: float(r["value"]) for r in rows}
    unknown = sorted(set(body.values) - set(current))
    if unknown:
        raise HTTPException(422, f"Unknown settings: {unknown}")
    new = {**current, **body.values}
    if any(v < 0 for v in new.values()):
        raise HTTPException(422, "Values cannot be negative")
    if sum(v for k, v in new.items() if k.startswith("weight_")) <= 0:
        raise HTTPException(422, "At least one weight must be above 0")
    if new["style_low"] >= new["style_high"]:
        raise HTTPException(422, "style_low must be below style_high")
    for r in rows:
        v = new[r["name"]]
        r["value"] = str(int(v)) if v.is_integer() and r["value"].isdigit() else f"{v:g}"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "value", "note"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    compatibility.reload_rules(request.app.state.settings.mappings_dir)
    return {**get_formula(request),
            "note": "Saved. Commit mappings/compatibility_weights.csv so the team keeps this change, "
                    "and re-measure with: python src/evaluate_compatibility.py"}


# ------------------------------------------------------------------ listing sources
def run_out(run):
    if not run:
        return None
    return {"result": run["result"], "mode": run.get("mode", ""), "message": run.get("message", ""),
            "counts": run.get("counts", {}), "started_at": run["started_at"].isoformat(),
            "finished_at": run["finished_at"].isoformat()}


@router.get("/sources")
def sources(request: Request):
    """Every source the team listed, whether the collector may run it, its last
    run (ok / blocked / error) and how many of its listings the app shows."""
    db = request.app.state.db
    out = []
    for s in load_sources(request.app.state.settings.mappings_dir):
        sid = s["source_id"]
        out.append({
            **s, "refused": usable(s),
            "last_run": run_out(last_run(db, sid)), "last_ok": run_out(last_run(db, sid, "ok")),
            "active": db.listings.count_documents({"source_id": sid, "status": "active"}),
            "in_stock": db.listings.count_documents({"source_id": sid, "status": "active", "in_stock": True}),
        })
    return {"sources": out, "file": "mappings/listing_sources.csv"}
