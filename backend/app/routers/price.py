"""
GET /price-estimate: a second-hand price band for a wardrobe item or a scan,
from the trained price model (src/phase4/price.py, `train_price.py`).

The model reads the piece's STORED FashionCLIP vector (never re-embedded) and
answers a band (low / median / high, TND) for one channel: `friperie` (default)
or `classified`. Typical error is still about x1.5, so the app always shows the
band with its `note`, never a bare number.

    503  the model file is missing (run src/phase4/train_price.py)
    404  not your item / scan (or it expired)
    200 with nulls  the model cannot price this channel: it says so, never 0
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..db import vector_from_bson
from ..security import gendered_user
from .items import own_item

router = APIRouter(tags=["price"])

# what the app sees: a hand-built whitelist, nothing internal (no vector, no percentile)
BAND = ("low", "median", "high", "based_on", "count", "typical_error_factor")


@router.get("/price-estimate")
def price_estimate(request: Request, item_id: str | None = None, candidate_id: str | None = None,
                   channel: str = "friperie", user=Depends(gendered_user)):
    model = request.app.state.price
    if model is None:
        raise HTTPException(503, "The price model is not available (run src/phase4/train_price.py)")
    if bool(item_id) == bool(candidate_id):
        raise HTTPException(422, "Give exactly one of item_id or candidate_id")
    doc = own_item(request, user, item_id or candidate_id,
                   collection="items" if item_id else "candidates")
    vector = vector_from_bson(doc.get("vector"))
    band = model.estimate(vector, category=doc.get("category"), channel=channel) \
        if vector is not None else None
    if band is None:
        return {**{k: None for k in BAND}, "channel": channel,
                "note": "No price estimate for this channel."}
    return {**{k: band.get(k) for k in BAND}, "channel": band["channel"], "note": band["note"]}
