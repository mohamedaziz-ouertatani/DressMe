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
    GET    /admin/listings        friperie sellers' listings to review (?status=pending)
    PATCH  /admin/listings/{id}   approve (active) or reject one, with an optional note
    GET    /admin/listings/overview  the Listings dashboard: counts, sources, runs, jobs
    POST   /admin/sources/{id}/check  the read-only shop check (src/phase4/check_shop_source.py) from the
                                      page; saves the kind found, never switches the shop on
    GET    /admin/jobs            collector runs started from the app (newest first)
    POST   /admin/jobs            start one (one at a time; same source gate as the command line)
    GET    /admin/jobs/{id}       one run, with its live progress
    GET    /admin/jobs/{id}/log   its output from ?offset= (the page polls it)
    POST   /admin/jobs/{id}/stop  stop it (politely, then the whole process tree after 30 s)
"""

import csv
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import ml  # noqa: F401  (puts src/ on the import path)
import check_shop_source
import compatibility

from ..db import object_id
from ..events import EVENT_TYPES
from ..listings import SELLERS, SOURCES_FILE, last_run, listing_out, load_sources, usable
from .listings import delete_seller_listings
from ..jobs import JobBusy
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
    delete_seller_listings(db, request.app.state.settings.storage_dir, user["_id"])
    request.app.state.listing_index.invalidate()
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
                     for r in read_csv(folder / WEIGHTS_FILE) if not r.get("gender")],
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
    neutral = [r for r in rows if not r.get("gender")]      # gendered rows are edited in the CSV
    current = {r["name"]: float(r["value"]) for r in neutral}
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
    for r in neutral:
        v = new[r["name"]]
        r["value"] = str(int(v)) if v.is_integer() and r["value"].isdigit() else f"{v:g}"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    compatibility.reload_rules(request.app.state.settings.mappings_dir)
    return {**get_formula(request),
            "note": "Saved. Commit mappings/compatibility_weights.csv so the team keeps this change, "
                    "and re-measure with: python src/phase4/evaluate_compatibility.py"}


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


# ------------------------------------------------------------------ seller listings (moderation)
@router.get("/listings")
def review_queue(request: Request, status: Literal["pending", "active", "rejected", "gone"] = "pending",
                 page: int = Query(1, ge=1), size: int = Query(30, ge=1, le=100)):
    """Friperie sellers' listings, oldest first (the review queue), with the seller's email."""
    db = request.app.state.db
    query = {"source_id": SELLERS, "status": status}
    docs = list(db.listings.find(query, {"vector": 0}).sort("created_at", 1)
                .skip((page - 1) * size).limit(size))
    emails = {u["_id"]: u["email"] for u in db.users.find(
        {"_id": {"$in": [d["seller_id"] for d in docs]}}, {"email": 1})}
    return {"total": db.listings.count_documents(query),
            "listings": [{**listing_out(d), "seller_email": emails.get(d["seller_id"], "")} for d in docs]}


class Review(BaseModel):
    status: Literal["active", "rejected"]
    note: str = ""          # shown to the seller, e.g. why it was rejected


@router.patch("/listings/{listing_id}")
def review(listing_id: str, body: Review, request: Request):
    db = request.app.state.db
    oid = object_id(listing_id)
    doc = oid and db.listings.find_one({"_id": oid, "source_id": SELLERS})
    if not doc:
        raise HTTPException(404, "Listing not found")
    if doc["status"] == "gone":
        raise HTTPException(409, "The seller marked this item as sold")
    db.listings.update_one({"_id": oid}, {"$set": {"status": body.status, "review_note": body.note[:200],
                                                   "reviewed_at": datetime.now(timezone.utc)}})
    request.app.state.listing_index.invalidate()
    doc = db.listings.find_one({"_id": oid}, {"vector": 0})
    return listing_out(doc)


# ------------------------------------------------------------------ listings dashboard + collector jobs
def job_out(request, job):
    if not job:
        return None
    runner = request.app.state.jobs
    job = runner.refresh(job)
    progress = runner.progress(job["_id"])
    iso = lambda d: d.isoformat() if d else None   # noqa: E731
    return {"id": str(job["_id"]), "status": job["status"], "sources": job["sources"],
            "catalogue": job["catalogue"], "force": job["force"], "limit": job["limit"],
            "started_by": job.get("started_by", ""), "started_at": iso(job.get("started_at")),
            "finished_at": iso(job.get("finished_at")), "exit_code": job.get("exit_code"),
            "results": job.get("results") or progress.get("results", {}),
            "plan": job.get("plan") or progress.get("plan", {}),
            "progress": {k: progress.get(k) for k in ("phase", "source", "done", "total", "heartbeat")}}


class JobStart(BaseModel):
    sources: list[str] = []      # empty = every source that may run and is due
    catalogue: bool = False      # Inditex: read the whole catalogue, not only stock
    force: bool = False          # ignore refresh_days (never the enabled / approved gate)
    limit: int = Field(0, ge=0, le=10000)   # smoke test: stop after ~N products, nothing marked gone


@router.get("/jobs")
def list_jobs(request: Request, n: int = Query(20, ge=1, le=100)):
    jobs = request.app.state.db.listing_jobs.find().sort("started_at", -1).limit(n)
    return [job_out(request, j) for j in jobs]


@router.post("/jobs", status_code=201)
def start_job(body: JobStart, request: Request, admin=Depends(current_admin)):
    sources = {s["source_id"]: s for s in load_sources(request.app.state.settings.mappings_dir)}
    unknown = sorted(set(body.sources) - set(sources))
    if unknown:
        raise HTTPException(422, f"Unknown sources: {unknown}")
    refused = {sid: usable(sources[sid]) for sid in body.sources if usable(sources[sid])}
    if refused:   # never start a source the team has not enabled and approved
        raise HTTPException(422, "Not allowed to run: " + "; ".join(f"{k}: {v}" for k, v in refused.items()))
    try:
        job = request.app.state.jobs.start(body.sources, body.catalogue, body.force, body.limit, admin)
    except JobBusy as err:
        raise HTTPException(409, f"A run is already going on (job {err}): stop it or wait for it")
    return job_out(request, job)


def find_job(request, job_id):
    oid = object_id(job_id)
    job = oid and request.app.state.db.listing_jobs.find_one({"_id": oid})
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    return job_out(request, find_job(request, job_id))


@router.get("/jobs/{job_id}/log")
def job_log(job_id: str, request: Request, offset: int = Query(0, ge=0)):
    job = find_job(request, job_id)
    return {**request.app.state.jobs.log(job["_id"], offset), "status": job_out(request, job)["status"]}


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str, request: Request):
    job = find_job(request, job_id)
    return job_out(request, request.app.state.jobs.stop(job["_id"]))


@router.get("/listings/overview")
def listings_overview(request: Request, days: int = Query(30, ge=1, le=365)):
    """Everything the Listings dashboard shows, in one answer."""
    db = request.app.state.db
    count = db.listings.count_documents
    by_status = {r["_id"]: r["n"] for r in db.listings.aggregate(
        [{"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    per_source = {r["_id"]: r for r in db.listings.aggregate([{"$group": {
        "_id": "$source_id", "active": {"$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}},
        "in_stock": {"$sum": {"$cond": [{"$and": [{"$eq": ["$status", "active"]},
                                                 {"$eq": ["$in_stock", True]}]}, 1, 0]}},
        "gone": {"$sum": {"$cond": [{"$eq": ["$status", "gone"]}, 1, 0]}}}}])}
    categories = [{"category": r["_id"] or "", "count": r["n"]} for r in db.listings.aggregate([
        {"$match": {"status": "active"}}, {"$group": {"_id": "$category", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}])]
    since = datetime.now(timezone.utc) - timedelta(days=days)
    runs = {}
    for r in db.listing_runs.find({"finished_at": {"$gte": since}}, {"finished_at": 1, "result": 1}):
        day = r["finished_at"].strftime("%Y-%m-%d")
        runs.setdefault(day, {}).setdefault(r["result"], 0)
        runs[day][r["result"]] += 1
    sources = []
    for s in load_sources(request.app.state.settings.mappings_dir):
        sid = s["source_id"]
        counts = per_source.get(sid, {})
        sources.append({"source_id": sid, "kind": s.get("kind", ""), "brand": s.get("brand", ""),
                        "enabled": s.get("enabled", ""), "approved_on": s.get("approved_on", ""),
                        "refused": usable(s), "note": s.get("note", ""),
                        "active": counts.get("active", 0), "in_stock": counts.get("in_stock", 0),
                        "gone": counts.get("gone", 0),
                        "last_run": run_out(last_run(db, sid)), "last_ok": run_out(last_run(db, sid, "ok")),
                        "checkable": checkable(s), "last_check": check_out(last_check(db, sid))})
    sellers = per_source.get(SELLERS, {})
    running = request.app.state.jobs.running()
    last = db.listing_jobs.find_one(sort=[("started_at", -1)])
    return {
        "totals": {"active": by_status.get("active", 0), "gone": by_status.get("gone", 0),
                   "in_stock": count({"status": "active", "in_stock": True}),
                   "pending": count({"source_id": SELLERS, "status": "pending"}),
                   "rejected": count({"source_id": SELLERS, "status": "rejected"}),
                   "sellers_active": sellers.get("active", 0),
                   "sources_on": sum(1 for s in sources if not s["refused"]),
                   "sources_total": len(sources)},
        "sources": sources, "categories": categories,
        "runs_by_day": [{"day": d, **runs[d]} for d in sorted(runs)],
        "running": job_out(request, running), "last_job": job_out(request, last),
    }


# ------------------------------------------------------------------ shop check (from the page)
def checkable(source):
    """A shop the read-only check may look at: it has a site, and its kind is empty or a shop kind
    (never Inditex or the snapshot: those are not checked this way)."""
    return bool(source.get("base_url")) and source.get("kind", "") in check_shop_source.SHOP_KINDS


def last_check(db, source_id):
    return db.source_checks.find_one({"source_id": source_id}, sort=[("checked_at", -1)])


def check_out(doc):
    if not doc:
        return None
    return {"lines": doc["lines"], "kind": doc["kind"], "saved": doc["saved"],
            "checked_at": doc["checked_at"].isoformat(), "by": doc.get("by", "")}


@router.post("/sources/{source_id}/check")
def check_source(source_id: str, request: Request, admin=Depends(current_admin)):
    """Run src/phase4/check_shop_source.py's check on one shop, as `--save` does: robots.txt, then
    Shopify, WooCommerce and the sitemap route, ~4-6 polite requests (up to ~30 s). The kind
    found is written into listing_sources.csv; enabled / approved_on are never touched, so the
    shop stays off until a team member has read its terms."""
    settings, db = request.app.state.settings, request.app.state.db
    sources = {s["source_id"]: s for s in load_sources(settings.mappings_dir)}
    source = sources.get(source_id)
    if not source:
        raise HTTPException(404, "Unknown source")
    if not checkable(source):
        raise HTTPException(400, "Only shops with a site (base_url) and a shop kind can be checked here")
    if request.app.state.jobs.running():
        raise HTTPException(409, "A collector run is going on: check the shop when it has ended")
    lines, kind = check_shop_source.check(source["base_url"], pattern=source.get("product_pattern", ""))
    saved = bool(kind)
    if saved:
        check_shop_source.save_kind(settings.mappings_dir / SOURCES_FILE, source_id, kind)
    doc = {"source_id": source_id, "lines": lines, "kind": kind, "saved": saved,
           "checked_at": datetime.now(timezone.utc), "by": admin["email"]}
    db.source_checks.insert_one(doc)
    return {"source_id": source_id, **check_out(doc),
            "note": ("Saved. Commit mappings/listing_sources.csv so the team keeps this change. The shop "
                     "stays off until a team member has read its terms and set enabled + approved_on.")
            if saved else "No supported way to read this shop was found: it cannot be listed."}
