"""
Admin > Explainability (XAI sub-project 4; admins only, like the rest of /admin).

    GET /admin/xai            the XAI evaluations' numbers (src/phase4/xai_results.py), the
                              "not sure" flag on real uploads, chat trace statistics, the team's
                              XAI settings and concept list
    PUT /admin/xai/settings   edit mappings/xai_settings.csv (notes and order kept)
"""

import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from .. import ml  # noqa: F401  (puts src/ on the import path)
import explain
import explain_similarity
import xai_results

from ..config import ROOT
from ..security import current_admin
from ..wardrobe import PREDICTED_FIELDS

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(current_admin)])
SETTINGS_FILE = "xai_settings.csv"
COUNTS = {"near_miss", "min_swap_gain"}      # in points (0 or more); every other setting is 0-1


def settings_rows(request):
    """The rows of the team's XAI settings file, in the app's mappings folder."""
    with open(request.app.state.settings.mappings_dir / SETTINGS_FILE, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def real_use(request):
    """Per predicted field, on the users' real wardrobe items: how many have stored
    alternatives, how many are flagged "not sure" (with the current team cuts), and how
    often the user corrected the value, among unsure and sure guesses."""
    cuts = {r["setting"]: float(r["value"]) for r in settings_rows(request)}
    items = list(request.app.state.db.items.find({}, {"predicted": 1, "corrected": 1,
                                                      **{f: 1 for f in PREDICTED_FIELDS}}))
    fields = []
    for f in PREDICTED_FIELDS:
        rows = [d for d in items if (d.get("predicted", {}).get(f) or {}).get("alternatives")]
        counts = {"unsure": 0, "unsure_corrected": 0, "sure_corrected": 0}
        for d in rows:
            flagged = explain.is_unsure(f, d["predicted"][f]["alternatives"], cuts)
            changed = f in d.get("corrected", []) and d.get(f) != d["predicted"][f]["value"]
            counts["unsure"] += flagged
            counts["unsure_corrected" if flagged else "sure_corrected"] += changed
        sure = len(rows) - counts["unsure"]
        fields.append({"field": f, "items": len(rows), **counts,
                       "unsure_corrected_rate": round(counts["unsure_corrected"] / counts["unsure"], 3)
                       if counts["unsure"] else None,
                       "sure_corrected_rate": round(counts["sure_corrected"] / sure, 3) if sure else None})
    before = sum(1 for d in items if not any((d.get("predicted", {}).get(f) or {}).get("alternatives")
                                             for f in PREDICTED_FIELDS))
    return {"items": len(items), "before_xai": before, "fields": fields}


def trace_stats(request, days):
    """Chat answers of the last `days` days: per tool, calls / errors / agents
    ("How I answered" traces), and Explainer answers that called no tool."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    docs = list(request.app.state.db.chats.find(
        {"role": "model", "created_at": {"$gte": since}, "trace": {"$exists": True}},
        {"agent": 1, "trace": 1}))
    tools = defaultdict(lambda: {"calls": 0, "errors": 0, "agents": set()})
    for d in docs:
        for step in d.get("trace", []):
            t = tools[step["tool"]]
            t["calls"] += 1
            t["errors"] += str(step.get("result", "")).startswith(("error:", "failed:"))
            t["agents"].add(d.get("agent", ""))
    explainer = [d for d in docs if d.get("agent") == "explainer"]
    return {"days": days, "answers": len(docs),
            "tools": sorted(({"tool": name, "calls": t["calls"], "errors": t["errors"],
                              "agents": sorted(t["agents"])} for name, t in tools.items()),
                            key=lambda r: -r["calls"]),
            "explainer_answers": len(explainer),
            "explainer_without_tools": sum(1 for d in explainer if not d.get("trace"))}


@router.get("/xai")
def xai_overview(request: Request, days: int = Query(30, ge=1, le=365)):
    return {"evaluations": xai_results.results(ROOT),
            "real_use": real_use(request),
            "traces": trace_stats(request, days),
            "settings": [{"name": r["setting"], "value": float(r["value"]), "note": r["note"]}
                         for r in settings_rows(request)],
            "concepts": explain_similarity.load_concepts(request.app.state.settings.mappings_dir
                                                         / "style_concepts.csv"),
            "file": f"mappings/{SETTINGS_FILE}"}


class XaiSettingsUpdate(BaseModel):
    values: dict[str, float]


@router.put("/xai/settings")
def put_xai_settings(body: XaiSettingsUpdate, request: Request):
    """Change values in mappings/xai_settings.csv; the app reads the file on each
    use, so the change applies at once. Cuts are 0-1, point thresholds 0 or more."""
    rows = settings_rows(request)
    known = {r["setting"] for r in rows}
    unknown = sorted(set(body.values) - known)
    if unknown:
        raise HTTPException(422, f"Unknown settings: {unknown}")
    for name, v in body.values.items():
        if v < 0 or (name not in COUNTS and v > 1):
            raise HTTPException(422, f"{name} must be {'0 or more' if name in COUNTS else 'between 0 and 1'}")
    for r in rows:
        if r["setting"] in body.values:
            v = body.values[r["setting"]]
            r["value"] = str(int(v)) if v.is_integer() and r["setting"] in COUNTS else f"{v:g}"
    path = request.app.state.settings.mappings_dir / SETTINGS_FILE
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["setting", "value", "note"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {**xai_overview(request, 30),
            "note": "Saved. Commit mappings/xai_settings.csv so the team keeps this change, and "
                    "re-measure with: python src/phase4/evaluate_explanations.py"}
