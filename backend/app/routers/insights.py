"""
Wardrobe insights: what the wardrobe is made of (categories, colours, patterns),
how many good outfits it makes, which pieces never fit in one, what is missing,
and which pieces are near twins. The outfit logic is compatibility.wardrobe_insights;
this file only counts fields and turns item ids into answers for the app.
"""

from collections import Counter

from fastapi import APIRouter, Depends, Request

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..security import current_user
from ..vocab import CATEGORIES, PATTERNS
from ..wardrobe import describe, to_compat
from .outfits import user_profile, wardrobe

router = APIRouter(tags=["outfits"])

TOP_VERSATILE = 3      # main pieces shown as "works with the most"


@router.get("/insights")
def insights(request: Request, user=Depends(current_user)):
    docs, by_id = wardrobe(request, user)
    items = [to_compat(d) for d in docs]
    facts = compatibility.wardrobe_insights(items, user_profile(user, docs, request))
    piece = lambda i: describe(i, by_id)
    group = compatibility.RULES.group

    categories = Counter(d["category"] for d in docs)
    patterns = Counter(d["pattern"] for d in docs if d.get("pattern"))
    colours = Counter(d["colour"] for d in docs if d.get("colour"))
    use = facts["outfit_use"]

    return {
        "total": len(docs),
        "categories": [{"category": c, "count": categories[c]} for c in CATEGORIES if categories[c]],
        # neutral colours (black, white, navy...) go with almost anything: the app shows their share
        "colours": [{"colour": c, "count": n, "neutral": group.get(c) == "neutral"}
                    for c, n in colours.most_common()],
        "patterns": [{"pattern": p, "count": patterns[p]} for p in PATTERNS if patterns[p]],
        # empty fields the user can fill so the filters (modesty, season, occasion) can work
        "to_confirm": {
            "colour": sum(not d.get("colour") for d in docs),
            "coverage": sum(d.get("coverage") is None for d in docs),
            "season": sum(not d.get("season") for d in docs),
            "usage": sum(not d.get("usage") for d in docs),
        },
        "outfits": {"good": facts["good_outfits"], "complete": facts["complete"],
                    "good_score": int(compatibility.RULES.settings["good_outfit"])},
        "versatile": [{**piece(i), "outfits": use[i["id"]]} for i in facts["versatile"][:TOP_VERSATILE]],
        "unmatched": [piece(i) for i in facts["unmatched"]],
        "filtered": len(facts["filtered"]),
        "new_pairs": facts["new_pairs"],
        "missing": facts["missing"],
        "twins": [{"items": [piece(a), piece(b)], "similarity": round(s, 3)}
                  for a, b, s in facts["twins"]],
    }
