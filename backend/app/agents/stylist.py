"""
The Stylist agent: "what do I wear?". It builds and scores outfits from the
user's real wardrobe.
"""

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..routers.outfits import user_profile, wardrobe
from ..wardrobe import outfit_out, to_compat
from .common import list_wardrobe_tool


def tools(request, user):
    """The Stylist's tools, bound to this user."""
    def suggest_outfits(season: str = "", occasion: str = "", n: int = 1) -> list[dict]:
        """Recommend one best outfit from the user's wardrobe. season: summer, winter or
        mid-season. occasion: casual, formal, sport, wedding, eid or work. n: how many
        when the user explicitly asks for more (1-10)."""
        docs, by_id = wardrobe(request, user)
        outfits = compatibility.suggest_outfits(
            [to_compat(d) for d in docs], user_profile(
                user, docs, request, season or None, occasion or None),
            n=max(1, min(int(n), 10)))
        return [outfit_out(o, by_id) for o in outfits]

    def score_outfit(item_ids: list[str]) -> dict:
        """Score (0-100) and reasons for an outfit made of the user's items (ids from list_wardrobe)."""
        docs, by_id = wardrobe(request, user)
        chosen = [by_id[i] for i in item_ids if i in by_id]
        if not chosen:
            return {"error": "none of these ids are in the wardrobe"}
        items = [to_compat(d) for d in chosen]
        clash = compatibility.clashes(items)
        if clash:          # same hard rule as /outfits/score
            return {"error": "these pieces can't be worn together: " + "; ".join(clash)}
        return outfit_out({**compatibility.score_outfit(
            items, style_profile=user_profile(user, docs, request)["style_vector"]),
            "items": items}, by_id)

    functions = (list_wardrobe_tool(request, user), suggest_outfits, score_outfit)
    return {f.__name__: f for f in functions}
