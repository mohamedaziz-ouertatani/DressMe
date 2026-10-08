"""
The Explainer agent: "why?" (see AGENTS.md). It explains how DressMe reached an
answer, with the XAI functions of src/phase4/explain_outfit.py (outfit scores, buy
verdicts) and the label guesses stored with each item (src/phase4/explain.py).
It never makes a new kind of answer: it only shows how an existing one was made.
"""

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility
import explain_outfit

from ..db import object_id
from ..ml import unsure
from ..routers.outfits import user_profile, wardrobe
from ..wardrobe import describe, to_compat
from .common import Agent, list_wardrobe_tool

FIELDS = ["category", "sub_category", "pattern", "colour"]

# The explanation codes of the formula as short English facts (the model then
# answers in the user's language). Same codes as frontend/src/i18n/explain.ts.
FACTS = {
    "style_coherent": "the pieces share one style",
    "style_mixed": "the pieces have quite different styles",
    "style_unlike_you": "the outfit is unlike the user's usual style",
    "colour_pair": "{a} and {b} go together",
    "colour_neutral_base": "a calm base of {n} neutral colours",
    "colour_clash": "{a} and {b} clash",
    "colour_too_bold": "too many bold colours ({colours})",
    "pattern_one_bold": "one statement pattern ({pattern})",
    "pattern_calm": "calm, plain pieces",
    "pattern_clash": "two bold patterns ({a} + {b})",
    "structure_complete": "a complete outfit with shoes",
    "structure_no_shoes": "no shoes",
    "structure_full_and_bottom": "a full piece and a bottom together",
    "structure_over_limit": "{n} pieces of {category}",
    "structure_pair": "{a} and {b} don't go together",
}

PARTS_MEANING = {
    "style": "how alike the pieces look (FashionCLIP picture similarity), partly how close they are "
             "to the user's usual taste",
    "colour": "how well every pair of colours goes together (the team's colour table), minus points "
              "for too many bold colours",
    "pattern": "at most one bold pattern among the clothes (the worst pattern pair counts)",
    "structure": "is it wearable: a top and a bottom or a full piece, shoes, not too many pieces of one "
                 "kind, and types of piece that go together",
}


def fact(line):
    """One structured explanation line as a short English sentence."""
    p = dict(line["params"])
    if line["code"] == "structure_incomplete":
        return "no main piece" if p.get("missing") == "main_piece" else "missing a top or a bottom"
    if "colours" in p:
        p["colours"] = ", ".join(p["colours"])
    return FACTS.get(line["code"], line["code"]).format(**p)


def tools(request, user):
    """The Explainer's tools, bound to this user."""

    def outfit_items(item_ids):
        """(wardrobe docs, docs by id, compat items) or an error dict: only the user's own ids."""
        docs, by_id = wardrobe(request, user)
        unknown = [i for i in item_ids if i not in by_id]
        if not item_ids or unknown:
            return None, None, {"error": "unknown item ids (use list_wardrobe): " + ", ".join(unknown)}
        items = [to_compat(by_id[i]) for i in item_ids]
        why = compatibility.clashes(items)
        if why:
            return None, None, {"error": "these pieces can't be worn together: " + "; ".join(why)}
        return docs, by_id, items

    def scored(items, docs):
        """The app's score of these items (same personal style profile as /outfits/score)."""
        prof = user_profile(user, docs, request)
        result = compatibility.score_outfit(items, style_profile=prof["style_vector"])
        points = {c["part"]: {"points": c["points"], "max": c["max_points"], "counted": c["counted"],
                              **({"why_not_counted": c["why_not"]} if not c["counted"] else {})}
                  for c in explain_outfit.contributions(result, compatibility.RULES.weights)}
        return result, prof, {"score": result["score"], "points": points,
                              "works": [fact(l) for l in explain_outfit.strengths(items, result["parts"])],
                              "problems": [fact(l) for l in result["problems"]]}

    def explain_outfit_tool(item_ids: list[str]) -> dict:
        """Why an outfit of the user's pieces gets its score (0-100): the points each part earns
        (style, colour, pattern, structure), what works, what does not, the weakest piece with the
        best swap from the wardrobe, and the pair of pieces that look least alike.
        item_ids: ids from list_wardrobe."""
        docs, by_id, items = outfit_items(item_ids)
        if docs is None:
            return items
        result, prof, out = scored(items, docs)
        pool, _ = compatibility.filter_items([to_compat(d) for d in docs], prof)
        swaps = explain_outfit.swaps(items, pool, style_profile=prof["style_vector"])
        min_gain = explain_outfit.explain.load_settings()["min_swap_gain"]
        weakest = explain_outfit.weakest(swaps, min_gain=min_gain)
        swap = next((s for s in swaps if s["item_id"] == weakest), None)
        out["weakest"] = ({"piece": describe({"id": weakest}, by_id),
                           "swap_for": describe({"id": swap["best_swap_id"]}, by_id), "gain": swap["gain"]}
                          if swap else f"no piece of the wardrobe would add {min_gain:g} points or more")
        pairs = [p for p in explain_outfit.pair_map(items) if p["style"] is not None]
        if pairs:
            worst = min(pairs, key=lambda p: p["style"])
            out["least_alike_pair"] = {"pieces": [describe({"id": worst["a"]}, by_id),
                                                  describe({"id": worst["b"]}, by_id)],
                                       "style_match": worst["style"]}
        out["items"] = [describe(i, by_id) for i in items]
        return out

    explain_outfit_tool.__name__ = "explain_outfit"     # the name the model sees

    def what_if(item_ids: list[str], remove_id: str = "", add_id: str = "") -> dict:
        """What happens to an outfit's score if one piece is taken out (remove_id) and/or
        another of the user's pieces is put in (add_id): score and points before and after."""
        docs, by_id, items = outfit_items(item_ids)
        if docs is None:
            return items
        new_ids = [i for i in item_ids if i != remove_id] + ([add_id] if add_id else [])
        _, _, new_items = outfit_items(new_ids)
        if isinstance(new_items, dict):
            return new_items
        _, _, before = scored(items, docs)
        _, _, after = scored(new_items, docs)
        out = {"before": before, "after": after, "change": round(after["score"] - before["score"], 1)}
        if remove_id:
            out["removed"] = describe({"id": remove_id}, by_id)
        if add_id:
            out["added"] = describe({"id": add_id}, by_id)
        return out

    def explain_labels(item_id: str) -> dict:
        """Why the app labelled a piece as it did: for category, type, pattern and colour, the
        model's guess, its confidence, the other answers it considered, whether it is unsure and
        whether the user corrected it. item_id: an id from list_wardrobe, or "last_scan"."""
        db = request.app.state.db
        if item_id == "last_scan":
            doc = db.candidates.find_one({"user_id": user["_id"]}, sort=[("created_at", -1)])
            image_url = doc and f"/candidates/{doc['_id']}/image"
        else:
            oid = object_id(item_id)
            doc = oid and db.items.find_one({"_id": oid, "user_id": user["_id"]})
            image_url = doc and f"/items/{doc['_id']}/image"
        if not doc:
            return {"error": "unknown item (use list_wardrobe, or 'last_scan' for the last photo analysed)"}
        fields = {}
        for f in FIELDS:
            guess = doc.get("predicted", {}).get(f)
            if not guess:
                fields[f] = {"current_value": doc.get(f, ""), "model_guess": None}
                continue
            alternatives = guess.get("alternatives") or []
            fields[f] = {"model_guess": guess["value"], "confidence": guess["conf"],
                         "alternatives": alternatives,
                         "unsure": unsure(f, alternatives) if alternatives else None,
                         "corrected_by_user": f in doc.get("corrected", []),
                         "current_value": doc.get(f, "")}
        out = {"item": {"id": str(doc["_id"]), "category": doc["category"], "sub_category": doc["sub_category"],
                        "colour": doc["colour"], "image_url": image_url},
               "fields": fields,
               "note": "labels are model guesses from the photo; an empty colour means the guess was below "
                       "the confidence cut, so the user should choose it"}
        if item_id != "last_scan":     # the app's panel with the heatmaps (wardrobe items only)
            out["action"] = {"kind": "explain", "url": f"/wardrobe/{doc['_id']}?why=1"}
        return out

    def explain_verdict() -> dict:
        """Why the last photo the user analysed got its buy / think / skip verdict: how many good
        outfits it makes against the team's thresholds, which owned pieces it beats or loses to,
        near misses, and pieces the user already owns that look almost the same."""
        cand = request.app.state.db.candidates.find_one({"user_id": user["_id"]}, sort=[("created_at", -1)])
        if not cand:
            return {"error": "no analysed photo in the last 24 hours"}
        docs, by_id = wardrobe(request, user)
        advice = compatibility.buy_advice(to_compat(cand), [to_compat(d) for d in docs],
                                          user_profile(user, docs, request))
        why = explain_outfit.buy_explanation(advice)
        return {"item": {"id": str(cand["_id"]), "category": cand["category"],
                         "sub_category": cand["sub_category"], "colour": cand["colour"],
                         "image_url": f"/candidates/{cand['_id']}/image"},
                "verdict": advice["verdict"], "good_outfits": advice["good_outfits"], "path": why["path"],
                "to_next_verdict": why["to_next_verdict"],
                "beats": [{"owned": describe({"id": b["owned_id"]}, by_id) if b["owned_id"] else None,
                           "margin": b["margin"]} for b in why["beats"][:3]],
                "lost_to": [{"owned": describe({"id": l["owned_id"]}, by_id), "outfits": l["outfits"]}
                            for l in why["lost_to"][:3]],
                "near_misses": why["near_misses"],
                "twins": [{"item": describe({"id": t["id"]}, by_id), "similarity": t["similarity"]}
                          for t in why["twins"]]}

    def how_scoring_works() -> dict:
        """How DressMe scores outfits and gives buy verdicts: the four parts, the team's current
        weights and thresholds, and when a label counts as unsure."""
        s, x = compatibility.RULES.settings, explain_outfit.explain.load_settings()
        return {"parts": PARTS_MEANING, "weights": compatibility.RULES.weights,
                "weights_note": "score = weighted mean of the parts (0-100); a part that cannot be "
                                "computed is left out and the other weights are rescaled",
                "good_outfit": s["good_outfit"],
                "verdict": {"buy": f"at least {s['buy_min_outfits']:g} good outfits where the new piece "
                                   "beats what the user already owns",
                            "think": f"at least {s['think_min_outfits']:g}", "skip": "fewer"},
                "near_twin_similarity": s["similar_item"],
                "label_unsure": {"min_confidence": {f: x[f"min_conf_{f}"] for f in FIELDS},
                                 "margin_over_second_answer": x["margin"]},
                "set_by": "the DressMe team, in the mappings/ files; the data only measures them"}

    functions = (list_wardrobe_tool(request, user), explain_outfit_tool, what_if, explain_labels,
                 explain_verdict, how_scoring_works)
    return {f.__name__: f for f in functions}


AGENT = Agent(
    name="explainer", title="Explainer",
    description="why an outfit has its score, what would change it, why a piece got its labels, "
                "why a buy verdict, how DressMe scores",
    job=("explain how DressMe reached its answers. Use explain_outfit for why an outfit has its score "
         "(and the weakest piece), what_if for 'what if I wear X instead', explain_labels for why a piece "
         "got its category, type, pattern or colour, explain_verdict for why the last scan got buy / think / "
         "skip, and how_scoring_works for how scoring works in general. Only give reasons that appear in a "
         "tool result; never invent a rule, a number or a cause. Labels are guesses from a photo: give their "
         "confidence, and say when the app is unsure. If no tool says why, say it is not known. When a "
         "tool gives an 'explain' action, tell the user they can open it to see the picture."),
    tools=tools)
