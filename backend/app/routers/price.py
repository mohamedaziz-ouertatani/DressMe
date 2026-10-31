"""
GET /price-estimate: a second-hand price band for a wardrobe item, a scan or a
friperie seller's listing, from the trained price model (src/phase4/price.py,
`train_price.py`).

The model reads the piece's STORED FashionCLIP vector (never re-embedded) and
answers a band (low / median / high, TND) for one channel: `friperie` (default)
or `classified`. Typical error is still about x1.5, so the app always shows the
band with its `note`, never a bare number.

    503  the model file is missing (run src/phase4/train_price.py)
    404  not your item / scan (or it expired), or a listing you cannot see
    200 with nulls  the model cannot price this channel: it says so, never 0

listing_id: only an ACTIVE friperie seller's listing gets a band, always against
friperie prices, plus a `tag` for its asked price (price.price_tag: "good_deal",
"priced_high" or null). Shop listings are new clothes, 3-4x friperie prices, so
they would all look "high": they get nulls and a null tag, never a band.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import ml  # noqa: F401  (puts src/ on the import path)
import price as price_model

from ..db import vector_from_bson
from ..listings import SELLERS
from ..security import gendered_user
from .items import own_item
from .listings import get_listing

router = APIRouter(tags=["price"])

# what the app sees: a hand-built whitelist, nothing internal (no vector, no percentile)
BAND = ("low", "median", "high", "based_on", "count", "typical_error_factor")


@router.get("/price-estimate")
def price_estimate(request: Request, item_id: str | None = None, candidate_id: str | None = None,
                   listing_id: str | None = None, channel: str = "friperie", user=Depends(gendered_user)):
    model = request.app.state.price
    if model is None:
        raise HTTPException(503, "The price model is not available (run src/phase4/train_price.py)")
    if sum(bool(x) for x in (item_id, candidate_id, listing_id)) != 1:
        raise HTTPException(422, "Give exactly one of item_id, candidate_id or listing_id")
    if listing_id:
        return listing_estimate(request, model, listing_id, channel, user)
    doc = own_item(request, user, item_id or candidate_id,
                   collection="items" if item_id else "candidates")
    vector = vector_from_bson(doc.get("vector"))
    band = model.estimate(vector, category=doc.get("category"), channel=channel) \
        if vector is not None else None
    if band is None:
        return {**{k: None for k in BAND}, "channel": channel,
                "note": "No price estimate for this channel."}
    return {**{k: band.get(k) for k in BAND}, "channel": band["channel"], "note": band["note"]}


def listing_estimate(request, model, listing_id, channel, user):
    """The band and tag of one listing (see the module docstring)."""
    if channel != "friperie":
        raise HTTPException(422, "A listing is only priced against friperie prices")
    doc = get_listing(request, listing_id, user)      # 404 for a listing this user cannot see
    nothing = {**{k: None for k in BAND}, "channel": channel,
               "note": "No price estimate for this listing.", "tag": None}
    if doc.get("source_id") != SELLERS or doc.get("status") != "active":
        return nothing
    stored = request.app.state.db.listings.find_one({"_id": doc["_id"]}, {"vector": 1})
    vector = vector_from_bson((stored or {}).get("vector"))
    rules = price_model.load_rules()
    band = model.estimate(vector, category=doc.get("category"), channel=channel, rules=rules) \
        if vector is not None else None
    if band is None:
        return nothing
    return {**{k: band.get(k) for k in BAND}, "channel": band["channel"], "note": band["note"],
            "tag": price_model.price_tag(doc.get("price_tnd"), band, rules)}
