"""
Confidence and reason codes for "should I buy this?" (step 1 of the upgrade).

`compatibility.buy_advice` answers buy / think / skip. This module adds how much to trust
that answer and why, WITHOUT changing it:

    assess(advice, candidate, wardrobe, profile, insights, rules) -> {
        "confidence": "high" | "medium" | "low",
        "codes": [{"code": "small_wardrobe", "params": {...}}, ...]}

It is pure (data in, data out, no MongoDB, no files except the rules CSV) and never modifies what it
is given. The route calls `buy_advice` and `wardrobe_insights` and hands both results here.

Codes that LOWER the confidence (the answer may be unreliable):
    small_wardrobe   {owned, minimum}   fewer usable pieces than `min_wardrobe_items`
    no_pairing_piece {slot}             no owned piece can make an outfit with the new one
                                        (`slot` = what is missing: "top", "bottom" or "main")
    guessed_field    {field, conf}      a label of the new piece is still a flagged model guess
                                        (`predicted[field].unsure`) that the user did not correct

Codes that only INFORM:
    fills_gap        {slot}             the piece's slot is in what wardrobe_insights reports as missing
    far_from_style   {similarity}       cosine similarity to the user's taste vector below `far_from_style_cut`
    over_budget      {price, budget, share}   price > budget * `budget_share` (share = price / budget)

Confidence: `small_wardrobe` gives low. Otherwise 0 lowering codes give high, 1 gives medium,
2 or more give low.

The numbers are the team's, in mappings/verdict_rules.csv (all REVIEW), never in this file.

An item is the dict of compatibility.py (id, category, sub_category, colour, pattern, vector...);
the candidate also carries `predicted`, `corrected` and `price_tnd`, and the profile may carry
`budget_tnd` and `style_vector`. A missing value is "unknown" and never guessed: no price means
no over_budget, no taste vector means no far_from_style.
"""

import csv

import numpy as np

import compatibility as C
from item_images import ROOT

RULES_CSV = ROOT / "mappings" / "verdict_rules.csv"
REQUIRED = ("min_wardrobe_items", "far_from_style_cut", "budget_share")
FIELDS = ("category", "sub_category", "pattern", "colour")     # the labels a model guesses
LOWERING = ("small_wardrobe", "no_pairing_piece", "guessed_field")

# which `missing` labels of wardrobe_insights a piece of each outfit slot fills
FILLS = {"feet": ("shoes",), "upper": ("top", "main"), "lower": ("bottom", "main"), "full": ("main",)}


def load_rules(path=RULES_CSV):
    """{name: number} from the team's file (read at each call: an edit applies at once)."""
    with open(path, encoding="utf-8", newline="") as f:
        rules = {row["name"]: float(row["value"]) for row in csv.DictReader(f)}
    missing = [name for name in REQUIRED if name not in rules]
    if missing:
        raise ValueError(f"{path}: missing rows {missing}")
    return rules


def line(code, **params):
    return {"code": code, "params": params}


def cosine(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b) / norm if norm else 0.0


def pairing_gap(candidate, advice, profile, insights, rules):
    """What the wardrobe lacks for the new piece to make any outfit, or None when it can.
    The source of truth is buy_advice itself: no outfit with the piece in it (and the piece was
    not filtered out by the user's profile, which buy_advice reports in its own reasons) means
    nothing could be paired."""
    if advice["detail"]["outfits"] or not C.filter_items([candidate], profile, rules)[0]:
        return None
    slot = rules.slot[candidate["category"]]
    if slot == "upper":
        return "bottom"
    if slot == "lower":
        return "top"
    return next((m for m in insights.get("missing", []) if m in ("bottom", "top", "main")), "main")


# TODO(step 1): verdict-moving rules are NOT built. Today the codes only inform or lower the
# confidence; they never change buy / think / skip. Step 6 decides if over_budget, far_from_style or a
# repeated "left it" for similar pieces should move the verdict (that means a change in compatibility.py,
# which step 1 leaves untouched), and later the verdict weights could be learned from `decisions`.
def assess(advice, candidate, wardrobe, profile, insights, rules, settings=None):
    """Confidence and codes for one candidate (see the module docstring). `settings` = the
    verdict rules (default: read mappings/verdict_rules.csv)."""
    settings = settings or load_rules()
    profile = profile or {}
    codes = []

    # ---- lowering codes
    # TODO(step 1): the cut of each code is a first guess (mappings/verdict_rules.csv, all REVIEW;
    # guessed_field relies on mappings/xai_settings.csv). Tune them on real scans once users have answered
    # Bought it / Left it, and decide how many pieces are really "enough" per category, not in total.
    usable, _ = C.filter_items(wardrobe, profile, rules)
    minimum = int(settings["min_wardrobe_items"])
    if len(usable) < minimum:
        codes.append(line("small_wardrobe", owned=len(usable), minimum=minimum))
    gap = pairing_gap(candidate, advice, profile, insights, rules)
    if gap:
        codes.append(line("no_pairing_piece", slot=gap))
    corrected = set(candidate.get("corrected") or [])
    predicted = candidate.get("predicted") or {}
    for field in FIELDS:
        guess = predicted.get(field) or {}
        if guess.get("unsure") and field not in corrected:
            codes.append(line("guessed_field", field=field, conf=round(float(guess.get("conf", 0.0)), 3)))

    # ---- informing codes
    for label in FILLS.get(rules.slot.get(candidate["category"]), ()):
        if label in insights.get("missing", []):
            codes.append(line("fills_gap", slot=label))
            break
    taste, vector = profile.get("style_vector"), candidate.get("vector")
    if taste is not None and vector is not None:
        similarity = cosine(taste, vector)
        if similarity < settings["far_from_style_cut"]:
            codes.append(line("far_from_style", similarity=round(similarity, 3)))
    price, budget = candidate.get("price_tnd"), profile.get("budget_tnd")
    if price and budget and price > budget * settings["budget_share"]:
        codes.append(line("over_budget", price=round(float(price), 3), budget=round(float(budget), 3),
                          share=round(float(price) / float(budget), 2)))

    lowering = [c for c in codes if c["code"] in LOWERING]
    # TODO(step 1): first-version confidence rule (small_wardrobe = low, else 0 / 1 / 2+ lowering
    # codes = high / medium / low). The full version could weigh the codes (a guessed colour matters less than
    # a guessed category) and take the verdict's margin into account (a verdict close to a cut is less sure).
    if any(c["code"] == "small_wardrobe" for c in lowering):
        confidence = "low"
    else:
        confidence = {0: "high", 1: "medium"}.get(len(lowering), "low")
    return {"confidence": confidence, "codes": codes}
