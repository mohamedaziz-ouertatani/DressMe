"""
The DressMe outfit compatibility formula: a weighted sum of four parts, each
from 0 (bad) to 1 (good), turned into a score from 0 to 100 with reasons.

    style      do the pieces look like they belong together and suit the user?
               (pairwise FashionCLIP similarity, blended with the user's taste)
    colour     colour harmony between every pair of items, plus a penalty for
               too many bold (non-neutral) colours
    pattern    at most one bold pattern among the clothes
    structure  is it wearable? (top + bottom, or a dress / full piece) + shoes,
               and no category over its limit

The weights and every rule are set by the TEAM in CSV files (never in code):
    mappings/compatibility_weights.csv   weights and settings
    mappings/colour_groups.csv           palette colour -> group (neutral, warm...)
    mappings/colour_harmony.csv          score of a group pair or a colour pair
    mappings/pattern_mixing.csv          score of a pattern pair
    mappings/outfit_structure.csv        slot and item limit per category
The data only measures the formula (src/evaluate_compatibility.py).

A part that cannot be computed (e.g. no colours known) is left out, and the
weights of the other parts are rescaled: unknown is never guessed.

An item is a dict; only `category` is required:
    {"id": "...", "category": "top", "sub_category": "t-shirt", "colour": "black", "pattern": "striped",
     "pattern_conf": 0.9, "vector": <FashionCLIP vector>, "coverage": 4,
     "season": {"summer"}, "usage": {"casual"}}

Main functions (used by the API):
    score_outfit(items)                     -> score, parts, reasons
    filter_items(items, profile)            personal filters (modesty, season, occasion)
    suggest_outfits(wardrobe, profile, n)   the best outfits of a wardrobe
    buy_advice(candidate, wardrobe, profile)  "should I buy this?": counts the good
                                            outfits where the new item beats what you own
    complete_outfit(items, candidates, profile, k)  the best missing piece
    clashes(items)                          why the items can't be worn together
"""

from itertools import combinations

import numpy as np
import pandas as pd

from item_images import ROOT

MAP_DIR = ROOT / "mappings"
PARTS = ["style", "colour", "pattern", "structure"]
CLOTHES_SLOTS = {"upper", "lower", "full", "layer"}   # where a pattern matters


# ------------------------------------------------------------------ rules
class Rules:
    """All team-editable settings, read from the CSV files in mappings/."""

    def __init__(self, map_dir=MAP_DIR):
        read = lambda name: pd.read_csv(map_dir / name, dtype=str, keep_default_na=False)
        w = read("compatibility_weights.csv").set_index("name")["value"].astype(float)
        self.settings = w.to_dict()
        self.weights = {p: self.settings[f"weight_{p}"] for p in PARTS}
        self.group = read("colour_groups.csv").set_index("colour")["group"].to_dict()
        self.colour_pairs = self._pairs(read("colour_harmony.csv"))
        self.pattern_pairs = self._pairs(read("pattern_mixing.csv"))
        s = read("outfit_structure.csv")
        self.slot = dict(zip(s["category"], s["slot"]))
        self.max_items = dict(zip(s["category"], s["max_items"].astype(int)))

    @staticmethod
    def _pairs(table):
        """Symmetric lookup: (a, b) and (b, a) give the same score."""
        pairs = {}
        for r in table.itertuples():
            pairs[(r.a, r.b)] = pairs[(r.b, r.a)] = float(r.score)
        return pairs

    def colour_score(self, a, b):
        """Colour pair rule first (e.g. red + pink), else the group pair rule."""
        if a == b:   # same colour twice: always fine for neutrals, a bit flat otherwise
            return 1.0 if self.group[a] == "neutral" else self.settings["same_colour"]
        if (a, b) in self.colour_pairs:
            return self.colour_pairs[(a, b)]
        return self.colour_pairs[(self.group[a], self.group[b])]


RULES = Rules()


def reload_rules(map_dir=MAP_DIR):
    """Re-read the CSV files into the SAME Rules object (the functions below use it
    as their default), e.g. after an admin edits the weights in the app."""
    RULES.__init__(map_dir)


# ------------------------------------------------------------------ the four parts
def user_style_profile(items, feedback=None, rules=None):
    """Return a normalized taste vector from wardrobe and outfit feedback."""
    rules = rules or RULES
    vectors = [np.asarray(i["vector"], np.float32) for i in items if i.get("vector") is not None]
    if len(vectors) < int(rules.settings["style_profile_min_items"]):
        profile = np.zeros(512, dtype=np.float32)
    else:
        profile = np.mean(vectors, axis=0)
    feedback_count = 0
    for entry in feedback or []:
        vector = entry.get("vector")
        if vector is None:
            continue
        value = float(entry.get("rating", 0))
        if value not in (-1.0, 1.0):
            continue
        profile += value * np.asarray(vector, np.float32)
        feedback_count += 1
    if len(vectors) < int(rules.settings["style_profile_min_items"]) and not feedback_count:
        return None
    norm = float(np.linalg.norm(profile))
    return profile / norm if norm else None


def outfit_vector(items):
    """Return the normalized mean FashionCLIP vector for an outfit."""
    vectors = [np.asarray(i["vector"], np.float32) for i in items if i.get("vector") is not None]
    if not vectors:
        return None
    value = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(value))
    return value / norm if norm else None


def style_part(items, rules, style_profile=None):
    vecs = [np.asarray(i["vector"], np.float32) for i in items if i.get("vector") is not None]
    if len(vecs) < 2:
        return None, []
    sims = [float(a @ b) for a, b in combinations(vecs, 2)]
    lo, hi = rules.settings["style_low"], rules.settings["style_high"]
    coherence = float(np.clip((np.mean(sims) - lo) / (hi - lo), 0, 1))
    part = coherence
    reasons = []
    if style_profile is not None:
        user_sims = [float(style_profile @ vector) for vector in vecs]
        user_fit = float(np.clip((np.mean(user_sims) - lo) / (hi - lo), 0, 1))
        personal_weight = rules.settings["style_personal_weight"]
        part = ((1 - personal_weight) * coherence) + (personal_weight * user_fit)
        if user_fit < 0.3:
            reasons.append("the outfit is unlike your usual style")
    if coherence < 0.3:
        reasons.append("the pieces have quite different styles")
    return part, reasons


def colour_part(items, rules):
    colours = [i["colour"] for i in items if i.get("colour")]
    if len(colours) < 2:
        return None, []
    pairs = [(a, b, rules.colour_score(a, b)) for a, b in combinations(colours, 2)]
    part = float(np.mean([s for _, _, s in pairs]))
    reasons = []
    worst = min(pairs, key=lambda p: p[2])
    if worst[2] < 0.5:
        reasons.append(f"{worst[0]} and {worst[1]} clash")
    bold = {c for c in colours if rules.group[c] not in ("neutral", "metal")}
    extra = len(bold) - rules.settings["max_bold_colours"]
    if extra > 0:
        part -= extra * rules.settings["bold_colour_penalty"]
        reasons.append(f"many bold colours ({', '.join(sorted(bold))})")
    return float(max(part, 0)), reasons


def pattern_part(items, rules):
    patterns = [i["pattern"] for i in items
                if i.get("pattern") and rules.slot.get(i["category"]) in CLOTHES_SLOTS
                and i.get("pattern_conf", 1.0) >= rules.settings["min_pattern_conf"]]
    if not patterns:
        return None, []
    if len(patterns) == 1:
        return 1.0, []
    pairs = [(a, b, rules.pattern_pairs[(a, b)]) for a, b in combinations(patterns, 2)]
    worst = min(pairs, key=lambda p: p[2])        # one clash is enough to spoil it
    reasons = [f"two bold patterns ({worst[0]} + {worst[1]})"] if worst[2] < 0.5 else []
    return worst[2], reasons


def structure_part(items, rules):
    counts = pd.Series([i["category"] for i in items]).value_counts().to_dict()
    slots = pd.Series([rules.slot[i["category"]] for i in items]).value_counts().to_dict()
    full, upper, lower = slots.get("full", 0), slots.get("upper", 0), slots.get("lower", 0)
    core = full >= 1 or (upper >= 1 and lower >= 1)
    reasons = []
    if core and slots.get("feet", 0):
        part = 1.0
    elif core:
        part = rules.settings["structure_no_shoes"]
        reasons.append("no shoes")
    else:
        part = rules.settings["structure_incomplete"]
        reasons.append("missing a top or a bottom" if upper or lower else "no main piece")
    if full and lower:       # e.g. a dress with trousers: unusual
        part *= rules.settings["structure_over_limit"]
        reasons.append("a full piece and a bottom together")
    for cat, n in counts.items():
        if n > rules.max_items[cat]:
            part *= rules.settings["structure_over_limit"] ** (n - rules.max_items[cat])
            reasons.append(f"{n} items of {cat}")
    return part, reasons


PART_FUNCTIONS = {"style": style_part, "colour": colour_part,
                  "pattern": pattern_part, "structure": structure_part}


def score_outfit(items, rules=RULES, weights=None, style_profile=None):
    """Score from 0 to 100, the value of each part (None = not computable), and reasons."""
    weights = weights or rules.weights
    parts, reasons = {}, []
    for name, fn in PART_FUNCTIONS.items():
        if name == "style":
            parts[name], why = fn(items, rules, style_profile)
        else:
            parts[name], why = fn(items, rules)
        reasons += why
    used = {p: weights[p] for p, v in parts.items() if v is not None and weights[p] > 0}
    total = sum(used.values())
    score = 100 * sum(weights[p] * parts[p] for p in used) / total if total else 0.0
    return {"score": round(score, 1), "parts": parts, "reasons": reasons}


# ------------------------------------------------------------------ hard constraints
def clashes(items, rules=RULES):
    """Why these items can't be one outfit ([] = they can): two pieces with the
    same sub_category (two pairs of jeans), or a category over its max_items in
    mappings/outfit_structure.csv (two tops). Unlike structure_part, which only
    lowers the score, this is a hard rule the app enforces when building."""
    reasons = []
    subs = pd.Series([i.get("sub_category") for i in items if i.get("sub_category")])
    for sub, n in subs.value_counts().items():
        if n > 1:
            reasons.append(f"{n} items of {sub}")
    cats = pd.Series([i["category"] for i in items], dtype=object)
    for cat, n in cats.value_counts().items():
        if n > rules.max_items[cat]:
            reasons.append(f"{n} items of {cat} (max {rules.max_items[cat]})")
    return reasons


# ------------------------------------------------------------------ personal filters
def filter_items(items, profile=None):
    """Keep the items that fit the user's profile; unknown fields always pass.

    profile: {"min_coverage": 3, "season": "summer", "occasion": "work"} (all optional)
    Returns (kept items, {item id: reason} for the removed ones).
    """
    profile = profile or {}
    kept, removed = [], {}
    for item in items:
        why = None
        if profile.get("min_coverage") and item.get("coverage") is not None \
                and item["coverage"] < profile["min_coverage"]:
            why = f"coverage {item['coverage']} is below your level {profile['min_coverage']}"
        elif profile.get("season") and item.get("season") and profile["season"] not in item["season"]:
            why = f"not for {profile['season']}"
        elif profile.get("occasion") and item.get("usage") and profile["occasion"] not in item["usage"]:
            why = f"not for {profile['occasion']}"
        if why:
            removed[item.get("id")] = why
        else:
            kept.append(item)
    return kept, removed


# ------------------------------------------------------------------ building outfits
EXTRA_ORDER = ["shoes", "outerwear", "bag", "accessory"]   # pieces added around a core
TOP_CORES = 60          # only the best cores are completed (keeps it fast)


def _by_category(items):
    groups = {}
    for i in items:
        groups.setdefault(i["category"], []).append(i)
    return groups


def _cores(groups, rules, must=None):
    """Main pieces: every top + bottom pair, and every full piece (dress...)."""
    uppers = [i for c, l in groups.items() if rules.slot[c] == "upper" for i in l]
    lowers = [i for c, l in groups.items() if rules.slot[c] == "lower" for i in l]
    fulls = [i for c, l in groups.items() if rules.slot[c] == "full" for i in l]
    cores = [[u, l] for u in uppers for l in lowers] + [[f] for f in fulls]
    if must is not None and rules.slot[must["category"]] in ("upper", "lower", "full"):
        cores = [c for c in cores if any(i is must for i in c)]
    return cores


def _complete(core, groups, rules, must=None, style_profile=None):
    """Add shoes, then optional outerwear / bag / accessory when they raise the score.
    If `must` is an extra piece (e.g. shoes to buy), it is always used in its slot."""
    outfit = list(core)
    for cat in EXTRA_ORDER:
        options = groups.get(cat, [])
        if must is not None and must["category"] == cat:
            options = [must]
        if not options:
            continue
        best = max(options, key=lambda o: score_outfit(
            outfit + [o], rules, style_profile=style_profile)["score"])
        forced = cat == "shoes" or (must is not None and best is must)
        if forced or score_outfit(
                outfit + [best], rules, style_profile=style_profile)["score"] > score_outfit(
                    outfit, rules, style_profile=style_profile)["score"]:
            outfit.append(best)
    return outfit


def _outfits(items, rules, must=None, style_profile=None):
    """All completed outfits (best cores first), as (score result, items)."""
    groups = _by_category(items)
    cores = _cores(groups, rules, must)
    cores.sort(key=lambda c: score_outfit(c, rules, style_profile=style_profile)["score"], reverse=True)
    done = []
    for core in cores[:TOP_CORES]:
        outfit = _complete(core, groups, rules, must, style_profile)
        if must is None or any(i is must for i in outfit):
            done.append((score_outfit(outfit, rules, style_profile=style_profile), outfit))
    done.sort(key=lambda d: d[0]["score"], reverse=True)
    return done


def suggest_outfits(wardrobe, profile=None, n=5, rules=RULES):
    """The n best outfits; each item is used in at most 2 of them (variety)."""
    items, _ = filter_items(wardrobe, profile)
    style_profile = (profile or {}).get("style_vector")
    disliked = (profile or {}).get("disliked_outfits", set())
    chosen, uses = [], {}
    for result, outfit in _outfits(items, rules, style_profile=style_profile):
        if "|".join(sorted(i["id"] for i in outfit)) in disliked:
            continue
        if all(uses.get(id(i), 0) < 2 for i in outfit):
            chosen.append({**result, "items": outfit})
            for i in outfit:
                uses[id(i)] = uses.get(id(i), 0) + 1
        if len(chosen) == n:
            break
    return chosen


def buy_advice(candidate, wardrobe, profile=None, rules=RULES):
    """'Should I buy this?': how many good outfits the new item makes with the wardrobe."""
    kept, removed = filter_items([candidate], profile)
    if not kept:
        return {"verdict": "skip", "good_outfits": 0, "best": [],
                "reasons": [removed[candidate.get("id")]]}
    items, _ = filter_items(wardrobe, profile)
    style_profile = (profile or {}).get("style_vector")
    outfits = _outfits(items + [candidate], rules, must=candidate, style_profile=style_profile)
    # an outfit only counts if the new item beats every piece you already own
    # in the same slot (otherwise buying it changes nothing)
    same_cat = [w for w in items if w["category"] == candidate["category"]]
    good = []
    for result, outfit in outfits:
        if result["score"] < rules.settings["good_outfit"]:
            continue
        others = [i for i in outfit if i is not candidate]
        best_owned = max((score_outfit(
            others + [w], rules, style_profile=style_profile)["score"] for w in same_cat), default=0)
        if result["score"] > best_owned:
            good.append((result, outfit))
    s = rules.settings
    verdict = ("buy" if len(good) >= s["buy_min_outfits"]
               else "think" if len(good) >= s["think_min_outfits"] else "skip")
    reasons = []
    if candidate.get("vector") is not None:      # friperie items can't be returned
        twins = [w for w in items if w["category"] == candidate["category"]
                 and w.get("vector") is not None
                 and float(np.asarray(w["vector"], np.float32)
                           @ np.asarray(candidate["vector"], np.float32)) >= s["similar_item"]]
        if twins:
            reasons.append(f"you already own {len(twins)} very similar {candidate['category']} item(s)")
    return {"verdict": verdict, "good_outfits": len(good), "reasons": reasons,
            "best": [{**r, "items": o} for r, o in (good or outfits)[:3]]}


def complete_outfit(items, candidates, profile=None, k=5, rules=RULES):
    """The k candidates that best complete `items` (never a clash: see clashes())."""
    candidates, _ = filter_items(candidates, profile)
    style_profile = (profile or {}).get("style_vector")
    ranked = []
    for c in candidates:
        if clashes(items + [c], rules):
            continue
        ranked.append({**score_outfit(items + [c], rules, style_profile=style_profile), "item": c})
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:k]
