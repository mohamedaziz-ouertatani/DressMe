"""
Why an outfit gets its score, and why "should I buy this?" says what it says
(XAI sub-project 2). Pure functions on the results of compatibility.py:

    contributions(result, weights)  points of each part (they add up to the score)
    strengths(items, parts)         what works ("+" lines; the "-" lines come from score_outfit)
    swaps(items, wardrobe)          for each piece, the best replacement you own and its gain
    weakest(swap_list)              the piece whose swap gains the most
    pair_map(items)                 style / colour / pattern score of every pair of pieces
    buy_explanation(advice)         path to the verdict, what it beats, what would change it

Thresholds of the "+" lines and of near misses are TEAM settings
(mappings/xai_settings.csv, REVIEW). Nothing here changes a score.
"""

from itertools import combinations

import numpy as np

import compatibility as C
import explain

WHY_NOT = {"style": "no_vectors", "colour": "no_colours", "pattern": "no_patterns",
           "structure": "no_items"}


def _round_to(raw, target):
    """Round the values to 0.1 so that they add up exactly to `target`
    (largest remainder: the parts closest to the next 0.1 get it)."""
    tenths = {p: v * 10 for p, v in raw.items()}
    out = {p: int(np.floor(v + 1e-9)) for p, v in tenths.items()}
    left = int(round(target * 10)) - sum(out.values())
    for p in sorted(raw, key=lambda p: tenths[p] - out[p], reverse=True)[:max(left, 0)]:
        out[p] += 1
    return {p: v / 10 for p, v in out.items()}


def contributions(result, weights):
    """Points of each part: 100 x weight x value / (sum of the counted weights)."""
    parts = result["parts"]
    counted = {p for p in C.PARTS if parts[p] is not None and weights[p] > 0}
    total = sum(weights[p] for p in counted)
    raw = {p: (100 * weights[p] * parts[p] / total if p in counted else 0.0) for p in C.PARTS}
    points = _round_to(raw, result["score"])
    rows = []
    for p in C.PARTS:
        row = {"part": p, "weight": weights[p], "counted": p in counted,
               "value": None if parts[p] is None else round(float(parts[p]), 3)}
        if p in counted:
            row.update(points=points[p], max_points=round(100 * weights[p] / total, 1), why_not=None)
        else:
            row.update(points=0.0, max_points=0.0,
                       why_not="weight_zero" if weights[p] <= 0 else WHY_NOT[p])
        rows.append(row)
    return rows


def strengths(items, parts, rules=None, settings=None):
    """What works in the outfit, from the same rule tables as the score."""
    rules = rules or C.RULES
    settings = settings or explain.load_settings()
    out = []
    coherence = C.style_coherence(items, rules)
    if coherence is not None and coherence >= settings["strength_style"]:
        out.append(C.line("style", "+", "style_coherent"))
    colours = [i["colour"] for i in items if i.get("colour")]
    if len(colours) >= 2:
        pairs = [(a, b, rules.colour_score(a, b)) for a, b in combinations(colours, 2)]
        if min(s for _, _, s in pairs) >= 0.5:                       # no clash
            distinct = [p for p in pairs if p[0] != p[1]] or pairs
            best = max(distinct, key=lambda p: p[2])
            neutrals = [c for c in colours if rules.group[c] == "neutral"]
            # one colour line only: the best pair says it, else a calm neutral base
            if best[2] >= settings["strength_colour_pair"] and best[0] != best[1]:
                out.append(C.line("colour", "+", "colour_pair", a=best[0], b=best[1]))
            elif len(neutrals) >= 2:
                out.append(C.line("colour", "+", "colour_neutral_base", n=len(neutrals)))
    patterns = C.clothing_patterns(items, rules)
    bold = [p for p in patterns if p != "solid"]
    if len(bold) == 1:
        out.append(C.line("pattern", "+", "pattern_one_bold", pattern=bold[0]))
    elif len(patterns) >= 2 and not bold:
        out.append(C.line("pattern", "+", "pattern_calm"))
    if parts.get("structure") == 1.0:
        out.append(C.line("structure", "+", "structure_complete"))
    return out


def swaps(items, wardrobe, rules=None, style_profile=None):
    """For each piece: the wardrobe item of the same category that raises the score
    most when it takes the piece's place (never a clash), and how many points."""
    rules = rules or C.RULES
    base = C.score_outfit(items, rules, style_profile=style_profile)["score"]
    in_outfit = {i["id"] for i in items}
    out = []
    for k, piece in enumerate(items):
        rest = items[:k] + items[k + 1:]
        best, best_score = None, base
        for w in wardrobe:
            if w["id"] in in_outfit or w["category"] != piece["category"]:
                continue
            trial = rest + [w]
            if C.clashes(trial, rules):
                continue
            s = C.score_outfit(trial, rules, style_profile=style_profile)["score"]
            if s > best_score:
                best, best_score = w, s
        out.append({"item_id": piece["id"], "best_swap_id": best["id"] if best else None,
                    "gain": round(best_score - base, 1)})
    return out


def weakest(swap_list, positive_only=True, min_gain=0.0):
    """The piece whose best swap gains the most (None if no swap gains more than
    `min_gain`: the app passes the team's min_swap_gain, so a 0.2-point swap is not
    called a weakness). positive_only=False always names one (offline evaluation)."""
    rows = [s for s in swap_list if s["gain"] > min_gain] if positive_only else list(swap_list)
    return max(rows, key=lambda s: s["gain"])["item_id"] if rows else None


def pair_map(items, rules=None):
    """Style / colour / pattern score (0-1) of every pair of pieces; None = unknown."""
    rules = rules or C.RULES
    out = []
    for a, b in combinations(items, 2):
        style = colour = pattern = None
        if a.get("vector") is not None and b.get("vector") is not None:
            sim = float(np.asarray(a["vector"], np.float32) @ np.asarray(b["vector"], np.float32))
            style = round(C.rescale_style(sim, rules), 3)
        if a.get("colour") and b.get("colour"):
            colour = round(rules.colour_score(a["colour"], b["colour"]), 3)
        pa, pb = C.clothing_patterns([a], rules), C.clothing_patterns([b], rules)
        if pa and pb:
            pattern = round(rules.pattern_pairs[(pa[0], pb[0])], 3)
        out.append({"a": a["id"], "b": b["id"], "style": style, "colour": colour, "pattern": pattern})
    return out


def buy_explanation(advice, rules=None, settings=None):
    """The verdict made visible: good outfits vs the team's thresholds, what the new
    piece beats, which owned pieces beat it, near misses and near twins."""
    rules = rules or C.RULES
    settings = settings or explain.load_settings()
    s = rules.settings
    good_cut, near = s["good_outfit"], settings["near_miss"]
    beats, lost, near_misses = [], {}, 0
    for o in advice["detail"]["outfits"]:
        if o["score"] >= good_cut:
            if o["score"] > o["owned_score"]:
                beats.append({"item_ids": o["item_ids"], "owned_id": o["owned_id"],
                              "owned_score": o["owned_score"],
                              "margin": round(o["score"] - o["owned_score"], 1)})
            elif o["owned_id"]:
                lost[o["owned_id"]] = lost.get(o["owned_id"], 0) + 1
        elif o["score"] >= good_cut - near and o["score"] > o["owned_score"]:
            near_misses += 1
    good = advice["good_outfits"]
    next_cut = (s["think_min_outfits"] if advice["verdict"] == "skip"
                else s["buy_min_outfits"] if advice["verdict"] == "think" else None)
    return {"path": {"good": good, "buy_min": int(s["buy_min_outfits"]),
                     "think_min": int(s["think_min_outfits"]), "verdict": advice["verdict"]},
            "beats": beats,
            "lost_to": [{"owned_id": k, "outfits": n}
                        for k, n in sorted(lost.items(), key=lambda kv: -kv[1])],
            "near_misses": near_misses,
            "to_next_verdict": int(next_cut - good) if next_cut is not None else None,
            "twins": advice["detail"]["twins"]}
