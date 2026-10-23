"""
Dress (step 2 of the upgrade): what to put on today. Labels and a confidence for the suggested
outfits, and the recent-wear penalty. Pure functions: data in, data out, no MongoDB, no files except
the rules CSV. The scoring itself stays in compatibility.py and is never touched here.

    label_outfits(outfits, items_by_id, taste_vector, rules, usable=None) -> the same outfits, same
        order, each with two added keys:
            "label"       "safe" | "bolder" | "experimental", from the cosine similarity between the
                          outfit's vector and the user's taste vector; None when there is no taste vector
            "confidence"  "low" | "high"
    apply_wear_penalty(outfits, worn_ids, rules, n) -> the n best outfits after taking points off the
        pieces worn recently (only the ORDER changes, never a score)

An outfit is a compatibility result: {"score", "parts", "reasons", "items": [item dicts...]}. An item
is the dict of compatibility.py (id, vector...); `items_by_id` also carries `predicted` and `corrected`
(wardrobe.candidate_view builds that). A missing value is "unknown" and never guessed.

The numbers are the team's, in mappings/dress_rules.csv (all REVIEW), never in this file.
"""

import csv
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import numpy as np

import compatibility as C
from item_images import ROOT

RULES_CSV = ROOT / "mappings" / "dress_rules.csv"
REQUIRED = ("safe_cut", "bolder_cut", "min_wardrobe_items", "wear_penalty_days", "wear_penalty_points")
TUNIS = ZoneInfo("Africa/Tunis")            # "today" for the wear log is the date in Tunis
FIELDS = ("category", "sub_category", "pattern", "colour")     # the labels a model guesses


def load_rules(path=RULES_CSV):
    """{name: number} from the team's file (read at each call: an edit applies at once)."""
    with open(path, encoding="utf-8", newline="") as f:
        rules = {row["name"]: float(row["value"]) for row in csv.DictReader(f)}
    missing = [name for name in REQUIRED if name not in rules]
    if missing:
        raise ValueError(f"{path}: missing rows {missing}")
    return rules


def tunis_date(now):
    """The calendar date in Tunis at `now` (a timezone-aware datetime, e.g. datetime.now(timezone.utc))."""
    return now.astimezone(TUNIS).date()


# ------------------------------------------------------------------ labels and confidence
# TODO(step 2): the label is a first version: the similarity of the whole outfit to the taste vector, with
# two cuts. The full version could label per piece ("the shoes are the bold part"), use the occasion, and
# check that the cuts feel right on real wardrobes (the start values come from the frozen golden one).
def label_for(similarity, rules):
    if similarity >= rules["safe_cut"]:
        return "safe"
    return "bolder" if similarity >= rules["bolder_cut"] else "experimental"


def has_unsure_field(item):
    """True when a label of the piece is still a flagged model guess that the user did not correct."""
    corrected = set(item.get("corrected") or [])
    predicted = item.get("predicted") or {}
    return any((predicted.get(f) or {}).get("unsure") and f not in corrected for f in FIELDS)


# TODO(step 2): the confidence rule is a first version (a small wardrobe, or one unsure label on a piece).
# The full version could count how many labels are unsure, use the model's confidence numbers, or look at
# how far the outfit is from every other one.
def outfit_confidence(outfit, items_by_id, rules, usable):
    if usable < rules["min_wardrobe_items"]:
        return "low"
    if any(has_unsure_field(items_by_id.get(i["id"], {})) for i in outfit.get("items", [])):
        return "low"
    return "high"


def label_outfits(outfits, items_by_id, taste_vector, rules, usable=None):
    """The same outfits in the same order with `label` and `confidence` added (see the module docstring).
    `usable` = how many pieces of the wardrobe are usable for this request (default: all of items_by_id)."""
    usable = len(items_by_id) if usable is None else usable
    out = []
    for outfit in outfits:
        vector = C.outfit_vector(outfit.get("items", []))
        label = None
        if taste_vector is not None and vector is not None:
            label = label_for(float(np.dot(vector, np.asarray(taste_vector, np.float32))), rules)
        out.append({**outfit, "label": label, "confidence": outfit_confidence(outfit, items_by_id, rules, usable)})
    return out


# ------------------------------------------------------------------ recent-wear penalty
def penalty_active(rules):
    """The penalty applies only when both numbers are above 0 (the start values are 0: nothing changes)."""
    return rules["wear_penalty_days"] > 0 and rules["wear_penalty_points"] > 0


def recently_worn(entries, today, days):
    """The ids of pieces worn in the last `days` days, today included. `entries` = wear_log documents
    ({"item_ids": [...], "worn_on": "YYYY-MM-DD"})."""
    first = today - timedelta(days=int(days) - 1)
    return {i for e in entries if date.fromisoformat(e["worn_on"]) >= first for i in e["item_ids"]}


# TODO(step 2): the penalty is a flat number of points per recently worn piece, used only to re-order the
# suggestions. The full version could fade it with the days since (worn yesterday costs more than 3 days ago),
# treat an accessory or shoes differently from a main piece, and decide whether the shown score should include it.
def apply_wear_penalty(outfits, worn_ids, rules, n):
    """The n best outfits after each piece worn recently costs `wear_penalty_points`. A stable sort, so
    outfits that tie keep their order; the `score` of an outfit is never changed."""
    if not penalty_active(rules) or not worn_ids:
        return outfits[:n]
    points = rules["wear_penalty_points"]
    rank = lambda o: o["score"] - points * sum(1 for i in o["items"] if i["id"] in worn_ids)
    return sorted(outfits, key=rank, reverse=True)[:n]
