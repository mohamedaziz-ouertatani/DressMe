"""
The explainer's tools (step 3e.3): why an outfit got its score. No new logic; each tool calls code the app already
has and SHORTENS the answer (the model's memory is small). The explainer also uses list_wardrobe, search_wardrobe and
score_outfit as they are.

    explain_outfit     POST /outfits/explain (routers/outfits.py explain_outfit_route): the weakest piece and the
                       best swap for each piece, at most MAX_SWAPS
    how_scoring_works  the team's weights (compatibility.Rules.weights, mappings/compatibility_weights.csv), as the
                       share of the score each part gives, and the score from which an outfit counts as good

Pieces are ledger refs (the model never sees an id).
"""

from pydantic import Field

from ..routers import outfits as outfit_routes
from ..schemas import ItemIds
from .tools import Tool
from .tools_analyst import NoArgs, piece
from .tools_stylist import Strict, screen

MAX_SWAPS = 3        # the swaps shown to the model

# what each part of the score looks at (the part names are the ones score_outfit answers with)
PART_MEANING = {
    "style": "how alike the pieces look (FashionCLIP similarity)",
    "colour": "how well the colours go together",
    "pattern": "whether the patterns can be worn together",
    "structure": "whether the outfit is complete (top and bottom, or a dress; shoes) and within the limits",
}


# ---------------------------------------------------------------- explain_outfit
class ExplainArgs(Strict):
    pieces: list[int] = Field(min_length=2, max_length=6)


def explain_outfit(ctx, args):
    answer = screen(ctx, outfit_routes.explain_outfit_route, ItemIds(item_ids=args.pieces), clash_code="pieces_clash")
    swaps = sorted(answer["swaps"], key=lambda s: s["gain"], reverse=True)[:MAX_SWAPS]
    return {"weakest": ctx.ledger.add(answer["weakest"]) if answer["weakest"] else None,
            "swaps": [{"piece": ctx.ledger.add(s["item_id"]), "gain": round(s["gain"], 1),
                       "better": piece(ctx, s["swap"]) if s["swap"] else None} for s in swaps]}


# ---------------------------------------------------------------- how_scoring_works
def how_scoring_works(ctx, args):
    rules = outfit_routes.rules_of(ctx.user)
    total = sum(rules.weights.values())
    return {"parts": [{"part": name, "share_percent": round(100 * weight / total), "looks_at": PART_MEANING[name]}
                      for name, weight in rules.weights.items()],
            "good_from": int(rules.settings["good_outfit"]),
            "note": "A part that cannot be computed is left out and the other parts count more."}


EXPLAIN_OUTFIT = Tool("explain_outfit", (
    "For 2 to 6 of the user's pieces worn together: the weakest piece (the one a swap would improve most) and, for "
    "each piece, the best swap from the user's own wardrobe with the points it would gain. "
    "Example: explain_outfit(pieces=[1, 3]) for 'which piece weakens my outfit?'. "
    "Do not use it to get the score itself (use score_outfit)."),
    ExplainArgs, explain_outfit, piece_args=("pieces",))
HOW_SCORING_WORKS = Tool("how_scoring_works", (
    "How the outfit score is made: the four parts, how much of the score each gives, and the score from which an "
    "outfit counts as good. Example: how_scoring_works() for 'how are the points calculated?'. "
    "Do not use it for the score of one outfit (use score_outfit)."),
    NoArgs, how_scoring_works)
