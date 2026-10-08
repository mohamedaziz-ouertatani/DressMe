"""
The Seller assistant agent: "what should I sell, and for how much?". It advises and
prepares, never acts: prepare_sell only builds a link to the Sell page, where the user
adds their city and contact and presses Send (then an admin reviews the listing).
"""

from urllib.parse import urlencode

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..db import object_id, vector_from_bson
from ..listings import SELLERS
from ..resale import load_rules, price_range
from ..routers.outfits import user_profile, wardrobe
from ..wardrobe import describe, to_compat
from .common import Agent, list_wardrobe_tool

TOP = 5                # pieces listed per answer: keeps the prompt small
MAX_LISTINGS = 10
MAX_PRICE = 100000     # same limit as POST /listings/sell


def tools(request, user):
    """The Seller assistant's tools, bound to this user."""
    def own_piece(item_id):
        """The user's wardrobe item, or (no id) their last scan, as (document, kind), or (None, '')."""
        db = request.app.state.db
        if item_id:
            oid = object_id(item_id)
            doc = oid and db.items.find_one({"_id": oid, "user_id": user["_id"]})
            return (doc, "item") if doc else (None, "")
        doc = db.candidates.find_one({"user_id": user["_id"]}, sort=[("created_at", -1)])
        return (doc, "candidate") if doc else (None, "")

    def pieces_to_sell() -> dict:
        """Pieces worth selling: main pieces that go with nothing in the wardrobe, and for each
        pair of near-identical pieces, the second one."""
        docs, by_id = wardrobe(request, user)
        items = [to_compat(d) for d in docs]
        facts = compatibility.wardrobe_insights(items, user_profile(user, docs, request))
        return {"unmatched": [describe(i, by_id) for i in facts["unmatched"][:TOP]],
                "twins": [{"keep": describe(a, by_id), "sell": describe(b, by_id), "similarity": round(s, 3)}
                          for a, b, s in compatibility.near_twins(items)[:TOP]]}

    def price_hint(item_id: str = "") -> dict:
        """A fair friperie price range (TND) for one of the user's items (id from list_wardrobe)
        or, with no id, for the last photo they analysed, from similar listings."""
        doc, _ = own_piece(item_id)
        if not doc or not doc.get("vector"):
            return {"error": "no such item or analysed photo"}
        rules = load_rules()
        hits = request.app.state.listing_index.search(
            request.app.state.db, vector_from_bson(doc["vector"]), k=rules["neighbours"],
            category=doc["category"], exclude_seller=user["_id"])
        return price_range(hits, rules) or {"error": "no similar listings with a price yet"}

    def my_listings() -> dict:
        """The user's own friperie listings, newest first: price and status (pending = waiting
        for an admin, active = visible, rejected = see review_note, gone = sold or removed)."""
        docs = (request.app.state.db.listings
                .find({"source_id": SELLERS, "seller_id": user["_id"]}, {"vector": 0})
                .sort([("created_at", -1), ("_id", -1)]).limit(MAX_LISTINGS))
        return {"listings": [{"id": str(d["_id"]), "title": d.get("title", ""),
                              "price_tnd": d.get("price_tnd"), "category": d.get("category", ""),
                              "sub_category": d.get("sub_category", ""), "colour": d.get("colour", ""),
                              "status": d.get("status", ""), "review_note": d.get("review_note", ""),
                              "image_url": f"/listings/{d['_id']}/image"}
                             for d in docs]}

    def prepare_sell(price_tnd: float, item_id: str = "", title: str = "", size: str = "") -> dict:
        """Prepare the Sell form for one of the user's items (id from list_wardrobe) or, with
        no id, their last analysed photo: the app shows a button that opens it already filled.
        Nothing is posted: the user adds their city and contact and sends it."""
        doc, kind = own_piece(item_id)
        if not doc:
            return {"error": "no such item or analysed photo"}
        price = float(price_tnd)
        if not 0 < price <= MAX_PRICE:
            return {"error": "the price must be more than 0 TND"}
        query = {kind: str(doc["_id"]), "price": f"{price:g}"}
        if title.strip():
            query["title"] = title.strip()[:80]
        if size.strip():
            query["size"] = size.strip()[:20]
        folder = "items" if kind == "item" else "candidates"
        return {"action": {"kind": "sell", "url": "/sell?" + urlencode(query)},
                "item": {"id": str(doc["_id"]), "category": doc["category"],
                         "sub_category": doc.get("sub_category", ""), "colour": doc.get("colour", ""),
                         "image_url": f"/{folder}/{doc['_id']}/image"}}

    functions = (list_wardrobe_tool(request, user), pieces_to_sell, price_hint, my_listings, prepare_sell)
    return {f.__name__: f for f in functions}


AGENT = Agent(
    name="seller", title="Seller assistant",
    description="selling clothes the user owns: what to sell, at what price, writing the listing, their listings",
    job=("help the user sell pieces they do not wear, at a fair friperie price. Use pieces_to_sell to "
         "find candidates, price_hint for a price (say it is a range from similar listings), write a "
         "short honest title (category, colour, size if known; never invent a brand or the condition), "
         "and finish with prepare_sell so the user gets a ready-filled Sell form. Tell them an admin "
         "checks each listing before others see it. my_listings shows their listings and status."),
    tools=tools)
