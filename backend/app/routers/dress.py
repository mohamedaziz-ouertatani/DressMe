"""
The Dress page (step 2b of the upgrade): three outfits for today, and three outfits around the pieces you pick.

    GET  /outfits/occasions                    the occasion chips, in the team's order (mappings/dress_occasions.csv)
    GET  /outfits/today?occasion=&shuffle=     the three outfits of the day
    POST /outfits/build  {item_ids, occasion?, shuffle?}   up to three outfits around the chosen pieces

Both outfit routes label the candidates and hand them to `dress.pick_three` (one function, two callers).
The candidates come from the same functions as /outfits/suggest (`ranked_suggestions`) and /outfits/complete
(`compatibility.complete_outfit`); their own answers do not change. The choice is random but seeded: the same
user, day (in Tunis), occasion and shuffle give the same outfits, "New outfits" counts `shuffle` up.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility
import dress

from ..schemas import BuildIn
from ..security import gendered_user
from ..weather import WeatherUnavailable
from ..wardrobe import outfit_out, to_compat
from .items import own_item
from .outfits import labelled_outfits, ranked_suggestions, rules_of, user_profile, wardrobe

router = APIRouter(tags=["dress"])

CANDIDATES = 20          # outfits fetched per usage value; pick_three chooses among the best of each label


def chip_named(name):
    """The occasion chip from the team's table, or 422."""
    chip = next((c for c in dress.load_occasions() if c["chip"] == name), None)
    if chip is None:
        raise HTTPException(422, f"occasion must be one of {[c['chip'] for c in dress.load_occasions()]}")
    return chip


def weather_today(request, lat, lon):
    """Today's weather as {temp_c, condition, season}, or None when the service is off or unreachable
    (the page then uses the calendar's season)."""
    engine = request.app.state.weather
    if engine is None:
        return None
    settings = request.app.state.settings
    if lat is None or lon is None:
        lat, lon = settings.weather_lat, settings.weather_lon
    try:
        raw = engine.today(lat, lon)
    except WeatherUnavailable:
        return None
    return {"temp_c": raw["temperature"], "condition": raw.get("condition"), "season": raw["season"]}


def shown(outfits, by_id, rules, occasion, weather, extra=None):
    """The outfits as JSON, each with the reason that it fits today (`fits_context`) added to its explanations."""
    out = []
    for o in outfits:
        body = outfit_out(o, by_id, explain=True, rules=rules)
        body["explanations"] = body["explanations"] + dress.context_reasons(o, occasion, weather)
        out.append({**body, **(extra or {}).get(id(o), {})})
    return out


@router.get("/outfits/occasions")
def occasions(user=Depends(gendered_user)):
    return [{"chip": c["chip"], "main": c["main"]} for c in dress.load_occasions()]


@router.get("/outfits/today")
def today(request: Request, occasion: str = "everyday", shuffle: int = Query(0, ge=0, le=1_000_000),
          lat: float | None = Query(None, ge=-90, le=90), lon: float | None = Query(None, ge=-180, le=180),
          user=Depends(gendered_user)):
    chip = chip_named(occasion)
    rules, dress_rules = rules_of(user), dress.load_rules()
    day = dress.tunis_date(datetime.now(timezone.utc))
    weather = weather_today(request, lat, lon)
    beach = chip["mode"] == "beach"
    season = "summer" if beach else (weather["season"] if weather else dress.calendar_season(day))
    docs, by_id = wardrobe(request, user)

    # candidates: the suggestions of each usage value of the chip, merged
    lists, first = [], None
    for usage in chip["usage_values"] or [None]:
        prof = user_profile(user, docs, request, season, usage)
        prof["beach"] = beach
        first = first or prof
        lists.append(ranked_suggestions(request, user, docs, prof, rules, dress_rules, CANDIDATES))
    labelled = labelled_outfits(dress.merge_candidates(lists), docs, first, rules, dress_rules)
    seed = dress.make_seed(user["_id"], day.isoformat(), chip["chip"], shuffle)
    picked = dress.pick_three(labelled, seed, dress_rules)

    missing = []
    if not picked:                      # what the wardrobe lacks: the same logic as GET /insights
        missing = compatibility.wardrobe_insights([to_compat(d) for d in docs], first, rules)["missing"]
    return {"date": day.isoformat(), "occasion": chip["chip"], "season": season, "weather": weather,
            "outfits": shown(picked, by_id, rules, chip["chip"], weather), "missing": missing}


@router.post("/outfits/build")
def build(body: BuildIn, request: Request, user=Depends(gendered_user)):
    rules, dress_rules = rules_of(user), dress.load_rules()
    docs, by_id = wardrobe(request, user)
    ids = list(dict.fromkeys(body.item_ids))
    for item_id in ids:
        own_item(request, user, item_id)                        # 404: not theirs
    chip = chip_named(body.occasion) if body.occasion else None
    compat = {str(d["_id"]): to_compat(d) for d in docs}
    # a piece that clashes with an earlier one replaces it (what the Build page always did), and says so
    chosen, notes = dress.resolve_clashes([compat[i] for i in ids], rules)
    taken = {c["id"] for c in chosen}
    others = [c for i, c in compat.items() if i not in taken]

    lists, first = [], None
    for usage in (chip["usage_values"] if chip and chip["mode"] == "usage" else []) or [None]:
        prof = user_profile(user, docs, request, "summer" if chip and chip["mode"] == "beach" else None, usage)
        first = first or prof
        lists.append(dress.complete_fully(chosen, others, prof, rules))
    pick = None
    if dress.is_complete(chosen, rules):
        pick = {**compatibility.score_outfit(chosen, rules, style_profile=first["style_vector"]), "items": chosen}
    labelled = labelled_outfits(([pick] if pick else []) + dress.merge_candidates(lists), docs, first, rules, dress_rules)
    pick_out, candidates = (labelled[0], labelled[1:]) if pick else (None, labelled)

    seed = dress.make_seed(user["_id"], dress.tunis_date(datetime.now(timezone.utc)).isoformat(),
                           "build:" + (chip["chip"] if chip else ""), ",".join(sorted(taken)), body.shuffle)
    picked = dress.pick_three(candidates, seed, dress_rules, n=3 - (1 if pick_out else 0),
                              exclude_keys=[dress.outfit_key(pick_out)] if pick_out else (),
                              skip_labels=[pick_out["label"]] if pick_out and pick_out["label"] else ())
    chosen_outfits = ([pick_out] if pick_out else []) + picked
    extra = {id(pick_out): {"pick": True}} if pick_out else {}
    outfits = shown(chosen_outfits, by_id, rules, chip["chip"] if chip else None, None, extra)
    outfits = [{"pick": False, **o} for o in outfits]
    return {"occasion": chip["chip"] if chip else None, "outfits": outfits, "notes": notes,
            "used_item_ids": [c["id"] for c in chosen]}
