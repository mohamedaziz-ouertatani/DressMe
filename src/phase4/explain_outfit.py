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
