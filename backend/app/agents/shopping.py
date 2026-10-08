"""
The Shopping advisor agent: "should I buy this? where can I find one?".
"""

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..routers.outfits import user_profile, wardrobe
from ..wardrobe import outfit_out, to_compat
from .common import list_wardrobe_tool


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

    functions = (list_wardrobe_tool(request, user), buy_advice_last_scan)
    return {f.__name__: f for f in functions}
