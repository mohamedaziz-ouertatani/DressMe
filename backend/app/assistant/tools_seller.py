"""
The seller's tool (step 3e.3): a second-hand price band for one of the user's own pieces. No new logic; it calls
the function behind GET /price-estimate (routers/price.py) and shows the model the band, never an id. The seller also
uses list_wardrobe, search_wardrobe and near_twins as they are.

    price_estimate   the trained price model's band (low / median / high, TND) for ONE piece, for one channel,
                     scaled by the condition the user says (the model reads the photo, it cannot see damage).
                     No model file (503 in the app) is the tool error no_price_model. A channel the model cannot
                     price answers nulls and a note, never 0.
"""

from typing import Literal

from fastapi import HTTPException

from .. import ml  # noqa: F401  (puts src/ on the import path)
import price as price_model

from ..routers import price as price_routes
from .tools import Tool, ToolError
from .tools_stylist import Strict


class PriceArgs(Strict):
    piece: int
    channel: Literal["friperie", "classified"] = "friperie"
    condition: Literal[price_model.CONDITIONS] = "good"


def price_estimate(ctx, args):
    try:                                                   # args.piece is the item id here (the registry translated it)
        answer = price_routes.price_estimate(ctx.request, item_id=args.piece, candidate_id=None, listing_id=None,
                                             channel=args.channel, condition=args.condition, user=ctx.user)
    except HTTPException as error:
        if error.status_code == 503:
            raise ToolError("no_price_model", "There is no price model on this server, so no price can be given.") \
                from error
        raise ToolError("refused", str(error.detail)) from error
    return {"piece": ctx.ledger.add(args.piece), "channel": answer["channel"], "condition": answer["condition"],
            "low": answer["low"], "median": answer["median"], "high": answer["high"],
            "typical_error_factor": answer["typical_error_factor"], "note": answer["note"]}


PRICE_ESTIMATE = Tool("price_estimate", (
    "A second-hand price band in TND (low, median, high) for ONE of the user's pieces, given by its number from this "
    "turn. channel: friperie (default) or classified (online resale). condition: new_tags, like_new, good (default), "
    "stained or torn. Example: price_estimate(piece=2) for 'how much could I ask for my jacket?'. "
    "The band is a rough guide (typical error about x1.5): say it as a range. Null values mean no estimate: never "
    "invent a price. Do not use it for shop items."),
    PriceArgs, price_estimate, piece_args=("piece",))
