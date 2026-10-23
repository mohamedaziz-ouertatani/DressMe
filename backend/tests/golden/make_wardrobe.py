"""
Builds backend/tests/golden/wardrobe.json: the FROZEN test wardrobe of the golden tests
(backend/tests/test_golden.py). Run it once, in the backend container, from backend/:

    docker exec -w /app/backend dressme-backend-1 python tests/golden/make_wardrobe.py
    docker exec -w /app/backend dressme-backend-1 python tests/golden/make_wardrobe.py --search   # how the candidates were found

No photo is written: only labels, the model's predictions and the FashionCLIP vectors
(base64 of the float16 bytes, exactly how the API stores them), read from data/processed/.
The script is deterministic: running it again gives the same file.

What is in it
- items: the 17 PolyVore pieces `python -m app.seed_demo` puts in the demo wardrobe (same
  filter, same `sample(random_state=11)`), as the app would have stored them: category,
  sub_category and pattern are the CLASSIFIER's predictions, colour is the colour model's
  guess (empty below confidence 0.7, the guess stays in `predicted`).
- user confirmations: a user opens an item and fixes what is empty. To exercise the filters
  (modesty, season, occasion) a few fields are set by hand in CONFIRMATIONS, and an empty
  colour is filled with the model's guess when its confidence is >= COLOUR_CONFIRM_MIN.
  Those fields are listed in `corrected`, like in the app.
- candidates: three scans (PolyVore pieces from other outfits) chosen so that today's
  verdicts are skip (a near twin of an owned piece), think and buy.
- listing: one shop product (an H&M article, labels from hm.csv) for POST
  /listings/{id}/candidate then /buy-advice.
- scenarios: the fixed inputs of the golden tests.

Stable on purpose: the script refuses to write the file if any outfit that decides a verdict
scores within 1 point of the good-outfit threshold (60), or within 1 point of the owned piece
it is compared with, so the golden tolerance (+-0.5) can never flip a verdict. The checks are
in `buy_margins`, `wardrobe_margins` and `order_gaps`.
"""

import argparse
import base64
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
from app.config import SRC_DIRS  # noqa: E402

sys.path[:0] = [str(d) for d in SRC_DIRS]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import compatibility as C  # noqa: E402
import similarity  # noqa: E402
from item_images import DATA  # noqa: E402

OUT = Path(__file__).resolve().parent / "wardrobe.json"

# ---------------------------------------------------------------- what is frozen
SEED_PLAN = [("top", 5), ("bottom", 3), ("dress", 2), ("outerwear", 2), ("shoes", 3), ("bag", 2)]
SEED_RANDOM_STATE = 11                  # the same as app/seed_demo.py
COLOUR_CONFIRM_MIN = 0.5                # the user confirms the model's colour guess from here
USER = {"email": "golden@example.com", "password": "golden-pass-123", "name": "Golden",
        "gender": "women", "min_coverage": 2}

# Fields a user confirmed on the item page (hand-set; REVIEW if the seed pieces change).
# Keys are PolyVore ids; values are what the user typed.
CONFIRMATIONS = {
    "pv_top_207372331_1": {"coverage": 3, "usage": ["casual"]},
    "pv_skirt_214043869_2": {"coverage": 2, "season": ["summer", "mid-season"]},
    "pv_pants_203204213_1": {"coverage": 1, "season": ["summer"], "usage": ["casual"]},   # shorts: below min_coverage 2
    "pv_dress_209560697_1": {"coverage": 3, "season": ["summer"], "usage": ["casual"]},
    "pv_dress_216723827_1": {"coverage": 4, "usage": ["formal", "wedding"]},
    "pv_outwear_189078408_2": {"coverage": 4, "season": ["winter", "mid-season"], "usage": ["casual"]},
    "pv_outwear_61316292_8": {"coverage": 5, "season": ["winter"]},                          # the scarf
    "pv_shoes_215446269_2": {"usage": ["formal"]},
    "pv_shoes_136099030_2": {"usage": ["formal", "wedding"]},
}

# Chosen with --search (see CANDIDATE_POOL): PolyVore ids for the scans, one H&M article.
CHOSEN = {
    "near_twin": "pv_top_161929959_1",     # a top, similarity 0.933 to the owned top_3: skip, 0 good outfits
    "think": "pv_top_60728884_1",          # a shirt that beats the owned tops in 2 good outfits
    "buy": "pv_outwear_205997829_2",       # a coat: the wardrobe has one jacket, the coat beats it in 12 outfits
}
LISTING_ID = "hm_0735648002"            # a navy skirt ("Heather"): think, 1 good outfit

# Fixed inputs of the golden tests. Items are named by key (category_number, in wardrobe order).
SCENARIOS = {
    "suggest": {
        "default": {"n": 5},
        "summer_casual": {"season": "summer", "occasion": "casual", "n": 5},
        "formal": {"occasion": "formal", "n": 3},
    },
    "score": {
        "full_outfit": ["top_1", "bottom_1", "shoes_2", "bag_2"],
        "dress_look": ["dress_2", "shoes_1", "bag_1"],
        "clash_two_tops": ["top_1", "top_2"],               # 422: the same category twice
    },
    "complete": {
        "from_top": {"item_ids": ["top_1"], "k": 3},
        "from_top_and_bottom": {"item_ids": ["top_2", "bottom_3"], "k": 3},
        "from_dress": {"item_ids": ["dress_2"], "k": 3},
    },
}


# ---------------------------------------------------------------- data
class Tables:
    """The processed data files, loaded once."""

    def __init__(self):
        self.df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False)
        self.pred = pd.read_csv(DATA / "processed" / "predicted_attributes.csv", dtype=str,
                                keep_default_na=False).set_index("id")
        self.col = pd.read_csv(DATA / "processed" / "colour_estimates.csv", dtype=str,
                               keep_default_na=False).set_index("id")
        self.idx = similarity.SimilarityIndex.load()
        self._hm = self._hm_idx = None

    @property
    def hm(self):
        """hm.csv (the shop catalogue), loaded when first needed."""
        if self._hm is None:
            self._hm = pd.read_csv(DATA / "processed" / "hm.csv", dtype=str, keep_default_na=False).set_index("id")
        return self._hm

    @property
    def hm_idx(self):
        if self._hm_idx is None:
            self._hm_idx = similarity.SimilarityIndex.load_shop()
        return self._hm_idx


def b64(vector16):
    return base64.b64encode(np.asarray(vector16, np.float16).tobytes()).decode("ascii")


def unb64(text):
    return np.frombuffer(base64.b64decode(text), np.float16).astype(np.float32)


def guess(value, conf):
    """A `predicted` entry as the API stores it (one alternative, never 'unsure')."""
    return {"value": value, "conf": float(conf), "alternatives": [{"value": value, "conf": float(conf)}],
            "unsure": False}


def stored_item(t, pv_id, hex_id, created_at, confirm=None, confirm_colour=False):
    """One document as POST /items (or /analyze) would have stored it, JSON-ready.
    `confirm` = fields the user then typed (coverage / season / usage)."""
    p, c = t.pred.loc[pv_id], t.col.loc[pv_id]
    colour_conf = float(c["colour_confidence"])
    colour = c["primary_colour"] if colour_conf >= 0.7 else ""     # the app's own rule
    corrected = []
    if confirm_colour and not colour and colour_conf >= COLOUR_CONFIRM_MIN:
        colour = c["predicted_colour"]
        corrected.append("colour")
    doc = {
        "id": hex_id, "dataset_id": pv_id,
        "category": p["pred_category"], "sub_category": p["pred_sub_category"],
        "pattern": p["pred_pattern"], "colour": colour,
        "coverage": None, "season": [], "usage": [],
        "predicted": {"category": guess(p["pred_category"], p["pred_category_conf"]),
                      "sub_category": guess(p["pred_sub_category"], p["pred_sub_category_conf"]),
                      "pattern": guess(p["pred_pattern"], p["pred_pattern_conf"]),
                      "colour": guess(c["predicted_colour"], colour_conf)},
        "corrected": corrected, "created_at": created_at,
        "vector_b64": b64(t.idx.vector(pv_id)),
    }
    for field, value in (confirm or {}).items():
        doc[field] = value
        doc["corrected"].append(field)
    doc["corrected"] = sorted(set(doc["corrected"]))
    return doc


def compat_item(doc):
    """The dict the compatibility formula wants (what app.wardrobe.to_compat builds)."""
    pattern_conf = 1.0 if "pattern" in doc["corrected"] else doc["predicted"]["pattern"]["conf"]
    return {"id": doc["id"], "category": doc["category"], "sub_category": doc["sub_category"],
            "colour": doc["colour"], "pattern": doc["pattern"], "pattern_conf": pattern_conf,
            "vector": unb64(doc["vector_b64"]), "coverage": doc["coverage"],
            "season": set(doc["season"]), "usage": set(doc["usage"])}


def hex_id(kind, n):
    return f"5f0c{kind:02x}{n:018x}"      # 24 hex characters: a fixed ObjectId


def build_wardrobe(t):
    """The 17 seed pieces, in seed_demo's order, with keys like top_1."""
    pv = t.df[(t.df["dataset"] == "polyvore") & (t.df["split"] == "test") & (t.df["duplicate"] != "True")]
    seed = pd.concat([pv[pv["category"] == c].sample(n, random_state=SEED_RANDOM_STATE) for c, n in SEED_PLAN])
    items, counts = [], {}
    for n, pv_id in enumerate(seed["id"], start=1):
        doc = stored_item(t, pv_id, hex_id(1, n), f"2026-10-01T10:{n:02d}:00Z",
                          CONFIRMATIONS.get(pv_id), confirm_colour=True)
        counts[doc["category"]] = counts.get(doc["category"], 0) + 1
        doc["key"] = f"{doc['category']}_{counts[doc['category']]}"
        items.append(doc)
    unknown = set(CONFIRMATIONS) - set(seed["id"])
    assert not unknown, f"CONFIRMATIONS for pieces that are not in the wardrobe: {unknown}"
    return items


def profile_for(items_c, rules, season=None, occasion=None):
    """What routers.outfits.user_profile builds (no outfit feedback in the golden user)."""
    return {"min_coverage": USER["min_coverage"], "season": season, "occasion": occasion,
            "style_vector": C.user_style_profile(items_c, [], rules), "disliked_outfits": set()}


# ---------------------------------------------------------------- stability checks
GOOD = 60.0
NEAR = 55.0          # good_outfit - near_miss (mappings/xai_settings.csv): where a near miss starts
BAND = 1.0           # a score this close to a cut could flip with the +-0.5 tolerance
TWIN_BAND = 0.003
GAP = 0.15           # two scores closer than this could swap places in a list


def read_cuts(rules):
    global GOOD, NEAR
    import explain
    GOOD = rules.settings["good_outfit"]
    NEAR = GOOD - explain.load_settings()["near_miss"]


def buy_margins(advice, cand_vector_sims, rules):
    """Problems that could make a verdict unstable (empty list = stable)."""
    problems = []
    for row in advice["detail"]["outfits"]:
        s = row["score"]
        if abs(s - GOOD) < BAND:
            problems.append(f"an outfit scores {s} (good = {GOOD})")
        elif abs(s - NEAR) < BAND:
            problems.append(f"an outfit scores {s} (near-miss line = {NEAR})")
        if s >= NEAR - BAND and row["owned_id"] and abs(s - row["owned_score"]) < BAND:
            problems.append(f"new {s} vs owned {row['owned_score']}")
    for sim in cand_vector_sims:
        if abs(sim - rules.settings["similar_item"]) < TWIN_BAND:
            problems.append(f"twin similarity {sim:.4f} is on the cut")
    return problems + order_gaps([o["score"] for o in advice["best"]], "best outfits")


def wardrobe_margins(items_c, profile, rules):
    """The same for wardrobe_insights: every completed outfit of the filtered wardrobe."""
    kept, _ = C.filter_items(items_c, profile, rules)
    scores = [r["score"] for r, _ in C._outfits(kept, rules, style_profile=profile["style_vector"])]
    problems = [f"an outfit scores {s} (good = {GOOD})" for s in scores if abs(s - GOOD) < BAND]
    return problems + order_gaps(sorted(scores, reverse=True)[:8], "wardrobe outfits")


def order_gaps(scores, what):
    """Consecutive scores of a ranked list that are closer than GAP (an order that depends on a tie)."""
    return [f"{what}: {a} and {b} are {abs(a - b):.2f} apart" for a, b in zip(scores, scores[1:])
            if abs(a - b) < GAP]


def evaluate(cand_doc, items_c, profile, rules):
    """Run the real buy advice for a candidate; return its advice and any stability problems."""
    cand = compat_item(cand_doc)
    advice = C.buy_advice(cand, items_c, profile, rules)
    sims = [t["similarity"] for t in advice["detail"]["twins"]]
    # twins just under the cut do not show up in `twins`: look at all same-category pieces
    sims += [float(w["vector"] @ cand["vector"]) for w in items_c
             if w["category"] == cand["category"] and w.get("vector") is not None]
    return advice, buy_margins(advice, sims, rules)


# ---------------------------------------------------------------- candidates
def scan_doc(t, pv_id, hex_id_):
    return stored_item(t, pv_id, hex_id_, "2026-10-02T09:00:00Z")


def candidate_pool(t, wardrobe_ids, per_category=80):
    """PolyVore pieces that are not in the wardrobe (val + test pictures), a sample per category."""
    pv = t.df[(t.df["dataset"] == "polyvore") & (t.df["split"].isin(["val", "test"])) & (t.df["duplicate"] != "True")]
    pv = pv[~pv["id"].isin(wardrobe_ids) & pv["id"].isin(t.pred.index) & pv["id"].isin(t.col.index)
            & pv["id"].isin(t.idx.row_of.index)]
    parts = [pv[pv["category"] == c].sample(min(per_category, (pv["category"] == c).sum()), random_state=3)
             for c in ("top", "bottom", "dress", "outerwear", "shoes", "bag")]
    return pd.concat(parts)["id"].tolist()


def near_twin_pool(t, items_c, wardrobe_ids, low=0.90, high=0.985):
    """Pieces of the same category as an owned one whose picture is almost the same (similarity in [low, high])."""
    pv = t.df[(t.df["dataset"] == "polyvore") & (t.df["split"].isin(["val", "test", "train"])) & (t.df["duplicate"] != "True")]
    pv = pv[~pv["id"].isin(wardrobe_ids) & pv["id"].isin(t.pred.index) & pv["id"].isin(t.col.index)
            & pv["id"].isin(t.idx.row_of.index)]
    ids = pv["id"].tolist()
    matrix = np.stack([t.idx.vector(i) for i in ids])
    found = []
    for w in items_c:
        sims = matrix @ w["vector"]
        for j in np.where((sims >= low) & (sims <= high))[0]:
            if t.pred.loc[ids[j], "pred_category"] == w["category"]:
                found.append((ids[j], w["id"], float(sims[j])))
    return found


HM_PRICE_TND = 59.9      # made up: hm.csv has no price (only the listing's labels and picture vector matter)


def hm_doc(t, hm_id, hex_id_):
    """A shop product as a listing would store it: the labels of hm.csv (not model predictions,
    so every `predicted` confidence is 1.0) and the H&M picture vector."""
    r = t.hm.loc[hm_id]
    return {
        "id": hex_id_, "dataset_id": hm_id,
        "category": r["category"], "sub_category": r["sub_category"], "pattern": r["pattern"],
        "colour": r["primary_colour"],
        "predicted": {f: guess(r[f if f != "colour" else "primary_colour"], 1.0)
                      for f in ("category", "sub_category", "pattern", "colour")},
        "corrected": [], "coverage": None, "season": [], "usage": [],
        "vector_b64": b64(t.hm_idx.vector(hm_id)),
        "title": r["name"], "shop_colour": r["original_colour"], "gender": r["gender"],
    }


def hm_pool(t, k=250):
    """Women's H&M products with a colour and a pattern label (a sample of k)."""
    hm = t.hm[(t.hm["gender"] == "women") & (t.hm["primary_colour"] != "") & (t.hm["pattern"] != "")
              & t.hm["category"].isin(["top", "bottom", "dress", "outerwear", "shoes", "bag"])]
    hm = hm[hm.index.isin(t.hm_idx.row_of.index)]
    return hm.sample(k, random_state=5).index.tolist()


def search(t, items, items_c, profile, rules):
    """Development aid: how the candidates were found. Prints, per verdict, stable candidates."""
    wardrobe_ids = {d["dataset_id"] for d in items}
    pool = candidate_pool(t, wardrobe_ids)
    print(f"{len(pool)} pieces in the pool; twins:")
    twins = near_twin_pool(t, items_c, wardrobe_ids)
    print(f"  {len(twins)} pieces with a near twin in the wardrobe")
    results = {"skip": [], "think": [], "buy": []}
    for pv_id in [x[0] for x in twins][:60] + pool:
        advice, problems = evaluate(scan_doc(t, pv_id, hex_id(2, 1)), items_c, profile, rules)
        results[advice["verdict"]].append((pv_id, advice["good_outfits"], not problems, problems[:2]))
    for verdict, rows in results.items():
        stable = [r for r in rows if r[2]]
        print(f"\n{verdict}: {len(rows)} tried, {len(stable)} stable")
        for pv_id, good, _, _ in stable[:12]:
            p = t.pred.loc[pv_id]
            twin = [x for x in twins if x[0] == pv_id]
            print(f"   {pv_id:30s} good={good:2d} {p['pred_category']}/{p['pred_sub_category']}"
                  f"{' twin of ' + twin[0][1] + f' sim={twin[0][2]:.3f}' if twin else ''}")
    print("\nH&M products (for the shop listing):")
    shown = {"skip": 0, "think": 0, "buy": 0}
    for hm_id in hm_pool(t):
        advice, problems = evaluate(hm_doc(t, hm_id, hex_id(3, 1)), items_c, profile, rules)
        if not problems and shown[advice["verdict"]] < 4:
            shown[advice["verdict"]] += 1
            r = t.hm.loc[hm_id]
            print(f"   {hm_id:16s} {advice['verdict']:5s} good={advice['good_outfits']:2d} "
                  f"{r['category']}/{r['sub_category']} {r['primary_colour']} {r['pattern']} - {r['name']}")


# ---------------------------------------------------------------- build
def check_scenarios(items, items_c, profile, rules):
    """Run every fixed input once with the real functions; return (problems, a short summary)."""
    problems, summary = [], {}
    by_key = {d["key"]: c for d, c in zip(items, items_c)}
    problems += [f"wardrobe: {p}" for p in wardrobe_margins(items_c, profile, rules)]
    facts = C.wardrobe_insights(items_c, profile, rules)
    summary["insights"] = {"good_outfits": facts["good_outfits"], "filtered": len(facts["filtered"]),
                           "unmatched": len(facts["unmatched"]), "missing": facts["missing"]}
    for name, p in SCENARIOS["suggest"].items():
        prof = profile_for(items_c, rules, p.get("season"), p.get("occasion"))
        out = C.suggest_outfits(items_c, prof, n=p["n"], rules=rules)
        scores = [o["score"] for o in out]
        problems += [f"suggest {name}: {m}" for m in order_gaps(scores, "outfits")]
        if not out:
            problems.append(f"suggest {name}: no outfit (the golden answer would be empty)")
        summary[f"suggest_{name}"] = scores
    for name, keys in SCENARIOS["score"].items():
        chosen = [by_key[k] for k in keys]
        clash = C.clashes(chosen, rules)
        score = C.score_outfit(chosen, rules, style_profile=profile["style_vector"])["score"]
        summary[f"score_{name}"] = {"score": score, "clashes": clash}
        if (name.startswith("clash")) != bool(clash):
            problems.append(f"score {name}: clash expectation not met ({clash})")
        if abs(score - GOOD) < BAND and not clash:
            problems.append(f"score {name}: scores {score} (good = {GOOD})")
    for name, p in SCENARIOS["complete"].items():
        chosen = [by_key[k] for k in p["item_ids"]]
        pool = [c for c in items_c if not any(c is x for x in chosen)]
        ranked = C.complete_outfit(chosen, pool, profile, k=p["k"] + 1, rules=rules)
        scores = [r["score"] for r in ranked]
        problems += [f"complete {name}: {m}" for m in order_gaps(scores, "ranking")]
        problems += [f"complete {name}: a result scores {s} (good = {GOOD})"
                     for s in scores[:p["k"]] if abs(s - GOOD) < BAND]
        if len(ranked) < p["k"]:
            problems.append(f"complete {name}: fewer than {p['k']} results")
        summary[f"complete_{name}"] = scores
    return problems, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", action="store_true", help="list stable candidates per verdict, write nothing")
    args = ap.parse_args()
    t = Tables()
    rules = C.rules_for(USER["gender"])
    read_cuts(rules)
    items = build_wardrobe(t)
    items_c = [compat_item(d) for d in items]
    profile = profile_for(items_c, rules)
    print(f"wardrobe: {len(items)} items, good_outfit={GOOD}, near-miss line={NEAR}")
    if args.search:
        search(t, items, items_c, profile, rules)
        return

    # --- the three scans and the shop listing: must give the verdicts we promise, stably
    wanted = {"near_twin": "skip", "think": "think", "buy": "buy"}
    candidates, checked = [], {}
    for n, (name, verdict) in enumerate(wanted.items(), start=1):
        doc = scan_doc(t, CHOSEN[name], hex_id(2, n))
        doc["key"] = name
        advice, problems = evaluate(doc, items_c, profile, rules)
        assert advice["verdict"] == verdict, f"{name}: verdict is {advice['verdict']}, expected {verdict}"
        assert not problems, f"{name}: unstable: {problems}"
        checked[name] = {"verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
                         "closest_to_good_line": round(min(abs(r["score"] - GOOD) for r in advice["detail"]["outfits"]), 2)}
        candidates.append(doc)
    listing = hm_doc(t, LISTING_ID, hex_id(3, 1))
    advice, problems = evaluate(listing, items_c, profile, rules)
    assert not problems, f"listing: unstable: {problems}"
    checked["listing"] = {"verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
                          "closest_to_good_line": round(min(abs(r["score"] - GOOD) for r in advice["detail"]["outfits"]), 2)}
    listing.update({"shop_id": "golden_shop", "brand": "H&M", "price_tnd": HM_PRICE_TND,
                    "sizes": ["S", "M"], "created_at": "2026-10-02T08:00:00Z"})

    problems, summary = check_scenarios(items, items_c, profile, rules)
    assert not problems, "unstable scenarios:\n  " + "\n  ".join(problems)

    data = {
        "format": 1,
        "about": "Frozen golden wardrobe. Generated by backend/tests/golden/make_wardrobe.py; "
                 "see that file for how every part was chosen. Do not edit by hand.",
        "user": USER,
        "items": items, "candidates": candidates, "listing": listing,
        "scenarios": SCENARIOS,
        "checked": {"candidates": checked, "scenario_scores": summary,
                    "good_outfit": GOOD, "near_miss_line": NEAR, "band": BAND},
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")
    print(json.dumps(data["checked"], indent=1))


if __name__ == "__main__":
    main()
