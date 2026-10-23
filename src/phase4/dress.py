"""
Dress (steps 2 and 2b of the upgrade): what to put on today. Labels and a confidence for outfits, the
three outfits of the Dress page, and the recent-wear penalty. Pure functions: data in, data out, no
MongoDB, no files except the rules CSVs. The scoring itself stays in compatibility.py and is never touched.

    label_outfits(outfits, items_by_id, taste_vector, rules, usable=None) -> the same outfits, same order,
        each with three added keys:
            "label"               "safe" | "bolder" | "experimental", from the cosine similarity between the
                                  outfit's vector and the user's taste vector; None without a taste vector
            "confidence"          "high" | "medium" | "low": 0 / 1 / 2 or more lowering factors
            "confidence_reasons"  the factors: [{"code": "small_wardrobe", "params": {owned, minimum}},
                                  {"code": "guessed_field", "params": {item_id, field}}, ...]
    pick_three(outfits, seed, rules) -> at most three outfits, one per label when the candidates allow it
    context_reasons(outfit, occasion, weather) -> [the "fits_context" line] for an outfit that passed the filters
    apply_wear_penalty(outfits, worn_ids, rules, n) -> the n best outfits after taking points off the
        pieces worn recently (only the ORDER changes, never a score)

An outfit is a compatibility result: {"score", "parts", "reasons", "items": [item dicts...]}. An item
is the dict of compatibility.py (id, vector...); `items_by_id` also carries `predicted` and `corrected`
(wardrobe.candidate_view builds that). A missing value is "unknown" and never guessed.

The numbers and lists are the team's, in mappings/dress_rules.csv and mappings/dress_occasions.csv (all
REVIEW), never in this file.
"""

import csv
import hashlib
import random
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import numpy as np

import compatibility as C
from item_images import ROOT

RULES_CSV = ROOT / "mappings" / "dress_rules.csv"
OCCASIONS_CSV = ROOT / "mappings" / "dress_occasions.csv"
REQUIRED = ("safe_cut", "bolder_cut", "min_wardrobe_items", "wear_penalty_days", "wear_penalty_points", "pick_pool")
TUNIS = ZoneInfo("Africa/Tunis")            # "today" for the wear log is the date in Tunis
FIELDS = ("category", "sub_category", "pattern", "colour")     # the labels a model guesses
LABELS = ("safe", "bolder", "experimental")


def load_rules(path=RULES_CSV):
    """{name: number} from the team's file (read at each call: an edit applies at once)."""
    with open(path, encoding="utf-8", newline="") as f:
        rules = {row["name"]: float(row["value"]) for row in csv.DictReader(f)}
    missing = [name for name in REQUIRED if name not in rules]
    if missing:
        raise ValueError(f"{path}: missing rows {missing}")
    return rules


# TODO(step 2): the occasion chips are a first mapping from a chip to the usage values of the pieces
# (mappings/dress_occasions.csv, REVIEW). The full version could use the event name, the time of day, or the
# user's own habits; "university" and "everyday" are the same today (casual).
def load_occasions(path=OCCASIONS_CSV):
    """The occasion chips, in the team's order: [{chip, usage_values: [...], mode: usage | beach, order, main}]."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = [{"chip": r["chip"], "usage_values": [u for u in r["usage_values"].split("|") if u],
                 "mode": r["mode"], "order": int(r["order"]), "main": r["main"].strip().lower() == "yes"}
                for r in csv.DictReader(f)]
    return sorted(rows, key=lambda r: r["order"])


def tunis_date(now):
    """The calendar date in Tunis at `now` (a timezone-aware datetime, e.g. datetime.now(timezone.utc))."""
    return now.astimezone(TUNIS).date()


def calendar_season(day):
    """The season by the calendar in Tunisia (the app's own rule): used when the weather is not available."""
    if 6 <= day.month <= 9:
        return "summer"
    if day.month == 12 or day.month <= 2:
        return "winter"
    return "mid-season"


def make_seed(*parts):
    """A stable integer from any parts (user, date, occasion, shuffle...). sha256, not hash(): Python's own
    hash of a string changes at every start, and the same day must give the same outfits."""
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16], 16)


# ------------------------------------------------------------------ labels and confidence
# TODO(step 2): the label is a first version: the similarity of the whole outfit to the taste vector, with
# two cuts. The full version could label per piece ("the shoes are the bold part"), use the occasion, and
# check that the cuts feel right on real wardrobes (the start values come from the frozen golden one).
def label_for(similarity, rules):
    if similarity >= rules["safe_cut"]:
        return "safe"
    return "bolder" if similarity >= rules["bolder_cut"] else "experimental"


# TODO(step 2): the confidence rule is a first version: each lowering factor counts one (a small wardrobe;
# every unsure label of every piece), 0 = high, 1 = medium, 2 or more = low. The full version could weigh the
# factors (a guessed colour matters less than a guessed category) or use the model's confidence numbers.
def confidence_reasons(outfit, items_by_id, rules, usable):
    """What lowers the confidence of an outfit, as codes the app turns into sentences."""
    reasons = []
    if usable < rules["min_wardrobe_items"]:
        reasons.append({"code": "small_wardrobe", "params": {"owned": usable, "minimum": int(rules["min_wardrobe_items"])}})
    for piece in outfit.get("items", []):
        doc = items_by_id.get(piece["id"], {})
        corrected = set(doc.get("corrected") or [])
        predicted = doc.get("predicted") or {}
        for field in FIELDS:        # a label that is still a flagged model guess the user did not correct
            if (predicted.get(field) or {}).get("unsure") and field not in corrected:
                reasons.append({"code": "guessed_field", "params": {"item_id": piece["id"], "field": field}})
    return reasons


def confidence_level(reasons):
    return {0: "high", 1: "medium"}.get(len(reasons), "low")


def label_outfits(outfits, items_by_id, taste_vector, rules, usable=None):
    """The same outfits in the same order with `label`, `confidence` and `confidence_reasons` added.
    `usable` = how many pieces of the wardrobe are usable for this request (default: all of items_by_id)."""
    usable = len(items_by_id) if usable is None else usable
    out = []
    for outfit in outfits:
        vector = C.outfit_vector(outfit.get("items", []))
        label = None
        if taste_vector is not None and vector is not None:
            label = label_for(float(np.dot(vector, np.asarray(taste_vector, np.float32))), rules)
        reasons = confidence_reasons(outfit, items_by_id, rules, usable)
        out.append({**outfit, "label": label, "confidence": confidence_level(reasons), "confidence_reasons": reasons})
    return out


# ------------------------------------------------------------------ the three outfits of the Dress page
def outfit_key(outfit):
    return "|".join(sorted(i["id"] for i in outfit["items"]))


def merge_candidates(lists):
    """Several candidate lists (one per usage value of an occasion) as one: each set of pieces once, with its
    best score, best first."""
    best = {}
    for outfits in lists:
        for o in outfits:
            key = outfit_key(o)
            if key not in best or o["score"] > best[key]["score"]:
                best[key] = o
    return sorted(best.values(), key=lambda o: o["score"], reverse=True)


# TODO(step 2): the choice rule is a first version: one outfit per label, drawn at random (from the seed) among
# the `pick_pool` best of that label, avoiding pieces already chosen. The full version could weigh the draw by
# score, keep a piece out of the next days' picks (with the wear log), or let the user pin one outfit.
def pick_three(outfits, seed, rules, n=3, exclude_keys=(), skip_labels=()):
    """At most `n` outfits from labelled candidates (compatibility results with `label`), deterministic for a seed.
    - at most one outfit per label (safe, bolder, experimental); within a label a random choice among the
      `pick_pool` best by score; a piece is not reused across the chosen outfits when an alternative exists;
    - a label with no candidate is filled by the next best unused outfit, which keeps its TRUE label;
    - without labels (no taste vector) the slots have no label: the best distinct outfits, drawn the same way.
    `exclude_keys` = outfit_key()s that must not come back (an outfit already shown); `skip_labels` = labels
    already shown, which are not used as slots."""
    rng = random.Random(seed)
    pool_size = max(1, int(rules["pick_pool"]))
    seen, distinct = set(exclude_keys), []
    for o in sorted(outfits, key=lambda o: o["score"], reverse=True):       # stable: ties keep their order
        key = outfit_key(o)
        if key not in seen:
            seen.add(key)
            distinct.append(o)
    labelled = any(o.get("label") for o in distinct)
    slots = [name for name in LABELS if name not in skip_labels][:n] if labelled else [None] * n

    chosen, used = [], set()

    def ids(outfit):
        return {i["id"] for i in outfit["items"]}

    for slot in slots:
        candidates = [o for o in distinct if o.get("label") == slot and o not in chosen]
        fresh = [o for o in candidates if not (ids(o) & used)]
        pool = (fresh or candidates)[:pool_size]
        if pool:
            pick = rng.choice(pool)
            chosen.append(pick)
            used |= ids(pick)
    while len(chosen) < n:                                                  # a label with no candidate
        rest = [o for o in distinct if o not in chosen]
        if not rest:
            break
        fresh = [o for o in rest if not (ids(o) & used)]
        pick = (fresh or rest)[0]                                           # the next best, its own label kept
        chosen.append(pick)
        used |= ids(pick)
    return chosen


# TODO(step 2): the context reason is one fixed sentence ("right for <occasion> at <temp>"). The full version
# could say what in the outfit fits (a light fabric on a hot day, a jacket when it rains) and use the rain chance.
def context_reasons(outfit, occasion, weather):
    """The "fits_context" line for an outfit that passed the occasion and season filters (the caller only gives
    outfits that did). Same shape as an explanation line of the outfit routes: {code, part, sign, params}.
    `weather` = {"temp_c": ...} or None: the temperature is then left out."""
    if not occasion:
        return []
    temp = (weather or {}).get("temp_c")
    return [{"code": "fits_context", "part": "context", "sign": "+", "params": {"occasion": occasion, "temp_c": temp}}]


# ------------------------------------------------------------------ the Build mode
def is_complete(items, rules):
    """A main piece (top + bottom, or a full piece) and shoes; a swimsuit needs no shoes."""
    slots = {rules.slot.get(i["category"]) for i in items}
    main = "full" in slots or {"upper", "lower"} <= slots
    swim = any(i["category"] == "swimwear" for i in items)
    return main and ("feet" in slots or swim)


def resolve_clashes(items, rules):
    """The chosen pieces in order; a piece that clashes with an earlier one (the same sub_category, or a
    category over its limit) replaces it, like the Build page always did. Returns (kept, notes) with a
    `clash_swapped` note {dropped, kept} per replaced piece."""
    kept, notes = [], []
    for item in items:
        same_sub = [k for k in kept if item.get("sub_category") and k.get("sub_category") == item["sub_category"]]
        kept = [k for k in kept if k["id"] not in {d["id"] for d in same_sub}]
        same_cat = [k for k in kept if k["category"] == item["category"]]
        over = len(same_cat) - (rules.max_items.get(item["category"], 1) - 1)
        oldest = same_cat[:max(0, over)]
        kept = [k for k in kept if k["id"] not in {d["id"] for d in oldest}]
        notes += [{"code": "clash_swapped", "params": {"dropped": d["id"], "kept": item["id"]}} for d in same_sub + oldest]
        kept.append(item)
    return kept, notes


def complete_fully(chosen, others, profile, rules, k=8, max_add=5):
    """Outfits around the chosen pieces: the k best first additions (compatibility.complete_outfit, the same
    function /outfits/complete uses), each then extended piece by piece until the outfit is complete. Returns
    scored outfits: {score, parts, reasons, items}."""
    style = (profile or {}).get("style_vector")
    out = []
    for first in C.complete_outfit(chosen, others, profile, k=k, rules=rules):
        current = chosen + [first["item"]]
        for _ in range(max_add - 1):
            if is_complete(current, rules):
                break
            taken = {c["id"] for c in current}
            more = C.complete_outfit(current, [o for o in others if o["id"] not in taken], profile, k=1, rules=rules)
            if not more:
                break
            current = current + [more[0]["item"]]
        out.append({**C.score_outfit(current, rules, style_profile=style), "items": current})
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

    def rank(outfit):
        return outfit["score"] - points * sum(1 for i in outfit["items"] if i["id"] in worn_ids)

    return sorted(outfits, key=rank, reverse=True)[:n]
