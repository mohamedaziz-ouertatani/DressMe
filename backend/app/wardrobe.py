"""
Helpers shared by the routers: turn model output into item fields, item
documents into API answers, and items into the dicts the compatibility formula
(src/compatibility.py) expects.
"""

from .db import vector_from_bson
from .ml import colour_min_confidence

PREDICTED_FIELDS = ["category", "sub_category", "pattern", "colour"]


def fields_from_analysis(analysis):
    """Model answers become the item's fields. A colour below the confidence cut
    stays empty (never guess); the guess is still kept in `predicted`."""
    fields = {f: analysis[f]["value"] for f in PREDICTED_FIELDS}
    if analysis["colour"]["conf"] < colour_min_confidence():
        fields["colour"] = ""
    predicted = {f: analysis[f] for f in PREDICTED_FIELDS}
    return fields, predicted


def item_out(doc, kind="items"):
    """An item (or candidate) document as JSON for the app."""
    out = {
        "id": str(doc["_id"]),
        "category": doc["category"], "sub_category": doc["sub_category"],
        "pattern": doc["pattern"], "colour": doc["colour"],
        "coverage": doc.get("coverage"), "season": doc.get("season", []),
        "usage": doc.get("usage", []),
        "predicted": doc.get("predicted", {}), "corrected": doc.get("corrected", []),
    }
    if kind == "items":
        out["image_url"] = f"/items/{out['id']}/image"
    return out


def to_compat(doc):
    """The item as the compatibility formula wants it. A field the user corrected
    counts as certain; a predicted pattern keeps the model's confidence."""
    pattern_conf = 1.0 if "pattern" in doc.get("corrected", []) \
        else doc.get("predicted", {}).get("pattern", {}).get("conf", 1.0)
    return {
        "id": str(doc["_id"]), "category": doc["category"], "colour": doc["colour"],
        "pattern": doc["pattern"], "pattern_conf": pattern_conf,
        "vector": vector_from_bson(doc.get("vector")), "coverage": doc.get("coverage"),
        "season": set(doc.get("season", [])), "usage": set(doc.get("usage", [])),
    }


def describe(compat_item, docs_by_id):
    """Short readable form of an item inside an outfit answer."""
    doc = docs_by_id[compat_item["id"]]
    return {"id": compat_item["id"], "category": doc["category"],
            "sub_category": doc["sub_category"], "colour": doc["colour"],
            "image_url": f"/items/{compat_item['id']}/image"}


def outfit_out(result, docs_by_id):
    """A compatibility result (score, parts, reasons, items) as JSON."""
    return {"score": result["score"],
            "parts": {k: (round(v, 3) if v is not None else None) for k, v in result["parts"].items()},
            "reasons": result["reasons"],
            "items": [describe(i, docs_by_id) for i in result.get("items", [])]}
