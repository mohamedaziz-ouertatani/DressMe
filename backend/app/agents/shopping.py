"""
The Shopping advisor agent: "should I buy this? where can I find one?".
"""

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..db import object_id, vector_from_bson
from ..listings import listing_out, listing_query
from ..routers.outfits import user_profile, wardrobe
from ..wardrobe import outfit_out, to_compat
from .common import Agent, list_wardrobe_tool


def short_listing(doc_out):
    """The few fields the model needs about a listing. The seller's contact is left
    out on purpose: the app shows it, the language model never receives it."""
    keep = ("id", "title", "brand", "source_id", "price_tnd", "category", "sub_category",
            "colour", "url", "image_url", "snapshot", "checked_at")
    row = {k: doc_out.get(k) for k in keep}
    if doc_out.get("seller"):
        row["city"] = doc_out["seller"]["city"]
    if "score" in doc_out:
        row["similarity"] = doc_out["score"]
    return row


def tools(request, user):
    """The Shopping advisor's tools, bound to this user."""
    def buy_advice_last_scan() -> dict:
        """'Should I buy this?' for the last photo the user analysed in the app (buy / think / skip)."""
        cand = request.app.state.db.candidates.find_one({"user_id": user["_id"]},
                                                        sort=[("created_at", -1)])
        if not cand:
            return {"error": "no analysed photo in the last 24 hours"}
        docs, by_id = wardrobe(request, user)
        by_id[str(cand["_id"])] = cand
        advice = compatibility.buy_advice(
            to_compat(cand), [to_compat(d) for d in docs],
            user_profile(user, docs, request))
        return {"item": {"id": str(cand["_id"]), "category": cand["category"],
                         "sub_category": cand["sub_category"], "colour": cand["colour"],
                         "image_url": f"/candidates/{cand['_id']}/image"},
                "verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
                "reasons": advice["reasons"], "best": [outfit_out(o, by_id) for o in advice["best"]]}

    def search_listings(category: str = "", sub_category: str = "", colour: str = "",
                        max_price: float = 0, n: int = 5) -> dict:
        """Clothes for sale now (Tunisian shops and friperie sellers), in stock, newest first.
        category / sub_category / colour: optional filters with the app's values (e.g. top,
        jeans, black). max_price: in TND, 0 = no limit. n: how many (1-10)."""
        db = request.app.state.db
        query = listing_query(category or None, sub_category or None, colour or None,
                              max_price=max_price or None)
        docs = (db.listings.find(query, {"vector": 0}).sort([("created_at", -1), ("_id", -1)])
                .limit(max(1, min(int(n), 10))))
        return {"total": db.listings.count_documents(query),
                "listings": [short_listing(listing_out(d)) for d in docs]}

    def find_similar(item_id: str = "", n: int = 5) -> dict:
        """Things to buy that look like one of the user's items (id from list_wardrobe) or,
        with no id, like the last photo they analysed: H&M products (no price) and listings
        in stock now. n: how many of each (1-10)."""
        db = request.app.state.db
        if item_id:
            oid = object_id(item_id)
            doc = oid and db.items.find_one({"_id": oid, "user_id": user["_id"]})
        else:
            doc = db.candidates.find_one({"user_id": user["_id"]}, sort=[("created_at", -1)])
        if not doc or not doc.get("vector"):
            return {"error": "no such item or analysed photo"}
        query, k = vector_from_bson(doc["vector"]), max(1, min(int(n), 10))
        shop = request.app.state.catalog.search_shop(query, k=k, category=doc["category"])
        for c in shop:
            c["image_url"] = f"/catalog/{c['id']}/image"
        listings = request.app.state.listing_index.search(db, query, k=k, category=doc["category"])
        return {"shop": shop, "listings": [short_listing(x) for x in listings]}

    functions = (list_wardrobe_tool(request, user), buy_advice_last_scan, search_listings, find_similar)
    return {f.__name__: f for f in functions}


AGENT = Agent(
    name="shopping", title="Shopping advisor",
    description="should I buy this, where to find a piece, shop and friperie listings and prices",
    job=("help the user spend little and buy only what works with their clothes. Use "
         "buy_advice_last_scan for 'should I buy this?', search_listings to find pieces for sale "
         "(prices are in TND), and find_similar for look-alikes of an item or of their last scan. "
         "Say when a price comes from a snapshot (snapshot = true: stock may have changed)."),
    tools=tools)
