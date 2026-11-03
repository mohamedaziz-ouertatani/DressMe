"""
The wardrobe analyst's tools (step 3e.2): the wardrobe as a whole. No new logic; each tool calls code the app already
has and then SHORTENS the answer, because the model's memory is small (num_ctx 8192) and a small model reads long
lists badly:

    wardrobe_insights  GET /insights (routers/insights.py -> compatibility.wardrobe_insights): totals, the top
                       colours, good outfits, what is missing, the most / least used pieces, the top twins
    near_twins         compatibility.near_twins: pairs of pieces that look almost the same

Every list is cut to MAX_LIST items. Pieces are shown as ledger refs (the model never sees an id): a piece is
{"ref", "type", "colour"}, a twin pair is {"pieces": [ref, ref], "similarity"}.
"""

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from pydantic import BaseModel, ConfigDict

from ..routers import insights as insights_routes
from ..routers import outfits as outfit_routes
from ..wardrobe import to_compat
from .tools import Tool
from .tools_stylist import screen

MAX_LIST = 5          # the longest list a tool shows the model
MAX_TWINS = 3         # the twins listed in the insights summary (near_twins gives up to MAX_LIST)


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def piece(ctx, item):
    """A piece as the model sees it: its ref and two words. `item` is an app answer with an id."""
    return {"ref": ctx.ledger.add(item["id"]), "type": item.get("sub_category") or item["category"],
            "colour": item.get("colour")}


def twin_pairs(ctx, pairs):
    """[(a, b, similarity)] (a, b = items with an id) -> the short form, most alike first, at most MAX_LIST."""
    return [{"pieces": [ctx.ledger.add(a["id"]), ctx.ledger.add(b["id"])], "similarity": round(s, 2)}
            for a, b, s in pairs[:MAX_LIST]]


# ---------------------------------------------------------------- wardrobe_insights
def wardrobe_insights(ctx, args):
    facts = screen(ctx, insights_routes.insights)
    return {
        "total": facts["total"],
        "categories": facts["categories"][:MAX_LIST],
        "top_colours": facts["colours"][:MAX_LIST],
        "neutral_share": (round(sum(c["count"] for c in facts["colours"] if c["neutral"]) / facts["total"], 2)
                          if facts["total"] and facts["colours"] else None),
        "patterns": facts["patterns"][:MAX_LIST],
        "good_outfits": facts["outfits"]["good"],
        "good_outfits_is_lower_bound": not facts["outfits"]["complete"],
        "missing": facts["missing"][:MAX_LIST],            # "shoes", "top", "bottom" or "main"
        "most_used": [{**piece(ctx, p), "outfits": p["outfits"]} for p in facts["versatile"][:MAX_LIST]],
        "never_used": [piece(ctx, p) for p in facts["unmatched"][:MAX_LIST]],
        "new_pairs_one_more_piece_makes": facts["new_pairs"],
        "twins": [{"pieces": [ctx.ledger.add(t["items"][0]["id"]), ctx.ledger.add(t["items"][1]["id"])],
                   "similarity": t["similarity"]} for t in facts["twins"][:MAX_TWINS]],
        "to_confirm": facts["to_confirm"],                 # fields still empty, so some filters cannot work
    }


# ---------------------------------------------------------------- near_twins
def near_twins(ctx, args):
    docs, by_id = screen(ctx, outfit_routes.wardrobe)       # a (docs, by id) pair; the gender check is the same
    rules = outfit_routes.rules_of(ctx.user)
    pairs = compatibility.near_twins([to_compat(d) for d in docs], rules)
    return {"total": len(pairs), "twins": twin_pairs(ctx, pairs)}


WARDROBE_INSIGHTS = Tool("wardrobe_insights", (
    "A short summary of the user's whole wardrobe: how many pieces, the main colours, how many good outfits it makes, "
    "what is missing (shoes, top, bottom), the pieces used most and never used, and near-identical pieces. "
    "Example: wardrobe_insights() for 'what am I missing?' or 'how balanced is my wardrobe?'. "
    "Do not use it to choose an outfit (use suggest_outfits) or to find one piece (use search_wardrobe)."),
    NoArgs, wardrobe_insights)
NEAR_TWINS = Tool("near_twins", (
    "Pairs of the user's pieces that look almost the same (same category), most alike first, at most 5. "
    "Example: near_twins() for 'which of my pieces are too similar?'. "
    "Do not use it for pieces that are only the same colour or for shop items."),
    NoArgs, near_twins)
