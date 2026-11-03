"""
The shopping agent's tools (step 3e.5): what the shops sell now, and whether it is worth buying. No new logic; each
tool calls the function a screen calls (the Shops page, the Similar page, the Buy? page) and SHORTENS the answer.

    search_listings        GET  /listings        (routers/listings.py list_listings: the gender filter is the route's)
    similar_pieces         GET  /similar         (routers/outfits.py similar) for ONE of the user's pieces
    buy_advice             POST /listings/{id}/candidate, then POST /buy-advice (routers/outfits.py buy_advice)
    price_estimate_listing GET  /price-estimate?listing_id=  (routers/price.py: only friperie sellers' listings get a band)

LISTINGS ARE NOT PIECES. A listing gets its own number from ctx.listings ("listing 3"), used only as the `listing`
argument of a tool and never written as {n}; {n} stays for the user's own wardrobe pieces. A listing is shown to the
model as {listing, title, price_tnd, shop, category, colour}: NEVER the seller's name, city or contact, and for a
friperie seller's listing not even the title (free text the seller typed, which may hold a phone number).
"""

from typing import Literal, Optional

from fastapi import HTTPException
from pydantic import Field

from ..db import object_id
from ..listings import SELLERS
from ..routers import listings as listing_routes
from ..routers import outfits as outfit_routes
from ..routers import price as price_routes
from ..schemas import BuyAdvice
from ..vocab import CATEGORIES, COLOURS
from .tools import Tool, ToolError
from .tools_analyst import piece
from .tools_stylist import Strict, screen

MAX_LIST = 5          # the longest list a tool shows the model
MAX_OUTFITS = 3       # the best outfits shown for a buy verdict

Category = Literal[tuple(CATEGORIES)]
Colour = Literal[tuple(COLOURS)]


def listing_for_model(ctx, listing):
    """A listing answer of the app -> what the model sees. `listing` is a listing_out dict (or a /similar hit)."""
    from_seller = listing.get("source_id") == SELLERS
    title = f"{listing.get('colour', '')} {listing.get('sub_category', '')}".strip() if from_seller \
        else (listing.get("title") or "")[:60]
    return {"listing": ctx.listings.add(listing["id"]), "title": title, "price_tnd": listing.get("price_tnd"),
            "shop": listing.get("shop_name") or "friperie", "category": listing.get("category"),
            "colour": listing.get("colour")}


# ---------------------------------------------------------------- search_listings
class SearchListingsArgs(Strict):
    category: Optional[Category] = None
    colour: Optional[Colour] = None
    max_price: Optional[float] = Field(default=None, ge=0, le=100000)      # TND


def search_listings(ctx, args):
    page = screen(ctx, listing_routes.list_listings, category=args.category, sub_category=None, colour=args.colour,
                  size=None, source=None, max_price=args.max_price, in_stock=True, sort="new", gender="mine",
                  page=1, per_page=MAX_LIST)
    return {"total": page["total"], "listings": [listing_for_model(ctx, x) for x in page["items"][:MAX_LIST]]}


# ---------------------------------------------------------------- similar_pieces
class SimilarArgs(Strict):
    piece: int


def similar_pieces(ctx, args):
    answer = screen(ctx, outfit_routes.similar, item_id=args.piece, candidate_id=None, k=MAX_LIST, gender="mine",
                    all_prices=False)
    own = answer["wardrobe"][0] if answer["wardrobe"] else None
    return {"piece": ctx.ledger.add(args.piece),
            "listings": [{**listing_for_model(ctx, x), "similarity": x["score"]} for x in answer["listings"][:MAX_LIST]],
            "closest_own_piece": {**piece(ctx, own), "similarity": own["similarity"]} if own else None}


# ---------------------------------------------------------------- buy_advice
class ListingArgs(Strict):
    listing: int


def buy_advice(ctx, args):
    """args.listing is the listing's id here (the registry translated the number)."""
    existing = ctx.db.candidates.find_one({"user_id": ctx.user_id, "listing_id": object_id(args.listing)}, {"_id": 1})
    candidate_id = str(existing["_id"]) if existing else \
        screen(ctx, listing_routes.listing_candidate, args.listing)["id"]       # a candidate lives 24 h: reuse it
    advice = screen(ctx, outfit_routes.buy_advice, BuyAdvice(candidate_id=candidate_id))
    outfits = [{"pieces": [ctx.ledger.add(i["id"]) for i in o["items"] if i["id"] != candidate_id],   # the user's own pieces
                "score": round(o["score"])} for o in advice["best"][:MAX_OUTFITS]]
    return {"listing": ctx.listings.add(args.listing), "verdict": advice["verdict"],
            "confidence": advice["confidence"], "good_outfits": advice["good_outfits"],
            "codes": advice["codes"], "best_outfits_with_it": outfits}


# ---------------------------------------------------------------- price_estimate_listing
def price_estimate_listing(ctx, args):
    try:
        answer = price_routes.price_estimate(ctx.request, item_id=None, candidate_id=None, listing_id=args.listing,
                                             channel="friperie", condition="good", user=ctx.user)
    except HTTPException as error:
        if error.status_code == 503:
            raise ToolError("no_price_model", "There is no price model on this server, so no price can be given.") \
                from error
        raise ToolError("refused", str(error.detail)) from error
    return {"listing": ctx.listings.add(args.listing), "low": answer["low"], "median": answer["median"],
            "high": answer["high"], "tag": answer.get("tag"), "note": answer["note"]}


SEARCH_LISTINGS = Tool("search_listings", (
    "Shop and friperie listings on sale now, newest first, at most 5, each with a listing number, title, price in TND "
    "and shop. All arguments are optional: category, colour, max_price (TND). "
    "Example: search_listings(category='bag', colour='black', max_price=50) for 'a black bag under 50 dinars'. "
    "Do not use it for the user's own clothes (use search_wardrobe)."),
    SearchListingsArgs, search_listings)
SIMILAR_PIECES = Tool("similar_pieces", (
    "Listings in the shops that look like ONE of the user's pieces (its number from this turn), at most 5, and the "
    "user's closest other piece. Example: similar_pieces(piece=2) for 'shoes like my brown shoes'. "
    "Do not use it with a number you were not given in this turn."),
    SimilarArgs, similar_pieces, piece_args=("piece",))
BUY_ADVICE = Tool("buy_advice", (
    "Should the user buy ONE listing (its listing number from this turn): the verdict (buy / think / skip), how sure "
    "it is, how many good outfits it makes with what the user owns, reason codes, and the best outfits. "
    "Example: buy_advice(listing=2). Report the verdict as it is; never tell the user to buy. "
    "Do not use it with a number you were not given in this turn."),
    ListingArgs, buy_advice, listing_args=("listing",))
PRICE_ESTIMATE_LISTING = Tool("price_estimate_listing", (
    "Is a friperie seller's listing priced well: a price band (low, median, high, TND) and a tag (good_deal / "
    "priced_high). Shop listings (new clothes) have no band: the values are null. Example: "
    "price_estimate_listing(listing=2). Null values mean no estimate: never invent a price. "
    "Do not use it for the user's own pieces."),
    ListingArgs, price_estimate_listing, listing_args=("listing",))
