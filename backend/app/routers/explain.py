"""
Why did the models give these labels? (XAI, see src/phase4/explain.py)

    GET /items/{id}/explain         a wardrobe item
    GET /candidates/{id}/explain    a scan or shop listing (kept 24 h)
        ?head=pattern&value=striped -> only that field, for that answer ("why not striped?")

The stored answer (value, conf, alternatives) is what is explained; the
pictures are computed now from the stored photo and never saved.
"""

import io

from fastapi import APIRouter, Depends, HTTPException, Request
from PIL import Image

from ..ml import unsure
from ..security import current_user
from .items import load_photo, own_item
from .tryon import as_data_url

router = APIRouter(tags=["explain"])


def explanation(request, user, doc, head, value):
    if value is not None and head is None:
        raise HTTPException(422, "value needs head")
    data = load_photo(request, user, doc)
    if data is None:
        raise HTTPException(404, "Image missing")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    try:
        model = request.app.state.analyzer.explain(img, head=head, value=value)
    except ValueError as e:
        raise HTTPException(422, str(e))
    fields = {}
    for field, entry in model.items():
        stored = doc.get("predicted", {}).get(field) or {}
        # items saved before the XAI layer have no stored alternatives: use the fresh ones
        alternatives = stored.get("alternatives") or entry["alternatives"]
        out = {k: (as_data_url(v) if k in ("heatmap", "pixels") else v) for k, v in entry.items()}
        out.update(value=stored.get("value", entry["shown"]), conf=stored.get("conf"),
                   alternatives=alternatives, unsure=unsure(field, alternatives),
                   corrected=field in doc.get("corrected", []))
        fields[field] = out
    return {"fields": fields}


@router.get("/items/{item_id}/explain")
def explain_item(item_id: str, request: Request, head: str | None = None, value: str | None = None,
                 user=Depends(current_user)):
    return explanation(request, user, own_item(request, user, item_id), head, value)


@router.get("/candidates/{candidate_id}/explain")
def explain_candidate(candidate_id: str, request: Request, head: str | None = None,
                      value: str | None = None, user=Depends(current_user)):
    doc = own_item(request, user, candidate_id, collection="candidates")
    return explanation(request, user, doc, head, value)
