"""
The Stylist's outfit and weather tools (step 3d). Each one calls the SAME function a screen calls (one function, two
callers), so the chat and the app never disagree:

    get_weather      the Dress page's weather engine (30-minute cache), at the default city
    suggest_outfits  GET  /outfits/today   (routers/dress.py `today`: same seed, so the same three outfits today)
    build_outfit     POST /outfits/build   (routers/dress.py `build`)
    score_outfit     POST /outfits/score   (routers/outfits.py `score` -> compatibility.score_outfit)

The route functions are plain Python functions: the tool gives them the /chat request and the logged-in user. Their
answers hold item ids, so each tool translates them before the model sees anything: pieces become ledger refs, scores
whole numbers 0-100, reasons the explanation codes with their sign ("+colour_pair"). No id, no free text.
"""

from typing import Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import ml  # noqa: F401  (puts src/ on the import path)
import dress

from ..routers import dress as dress_routes
from ..routers import outfits as outfit_routes
from ..schemas import BuildIn, ItemIds
from ..security import user_gender
from ..weather import WeatherUnavailable
from .tools import Tool, ToolError

Occasion = Literal[tuple(c["chip"] for c in dress.load_occasions())]     # everyday, work, ... (dress_occasions.csv)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def screen(ctx, route, *args, clash_code="refused", **kwargs):
    """Call a screen's route function as the logged-in user; its HTTP refusals become tool errors."""
    if user_gender(ctx.user) is None:                     # the screens answer 409 until the app has asked it
        raise ToolError("gender_required", "The user has not said men or women yet; outfits need it.")
    try:
        return route(*args, request=ctx.request, user=ctx.user, **kwargs)
    except HTTPException as error:
        raise ToolError(clash_code if error.status_code == 422 else "refused", str(error.detail)) from error


def reasons(outfit):
    return [e["sign"] + e["code"] for e in outfit.get("explanations", [])]


def outfit_for_model(outfit, ledger):
    return {"pieces": [ledger.add(i["id"]) for i in outfit["items"]], "label": outfit.get("label"),
            "score": round(outfit["score"]), "complete": outfit.get("complete"), "missing": outfit.get("missing"),
            "reasons": reasons(outfit)}


# ---------------------------------------------------------------- get_weather
class WeatherArgs(Strict):
    pass                                                  # no arguments


def get_weather(ctx, args):
    state = ctx.request.app.state
    if state.weather is None:
        raise ToolError("weather_unavailable", "The weather is switched off.")
    try:                                                  # the server stores no position: the default city
        today = state.weather.today(state.settings.weather_lat, state.settings.weather_lon)
    except WeatherUnavailable as error:
        raise ToolError("weather_unavailable", "The weather service cannot be reached.") from error
    return {"location": "default city", "temp_c": round(today["temperature"]), "condition": today["condition"],
            "rain": bool(today["rain_likely"]), "season": today["season"]}


# ---------------------------------------------------------------- suggest_outfits
class SuggestArgs(Strict):
    occasion: Optional[Occasion] = None


def suggest_outfits(ctx, args):
    page = screen(ctx, dress_routes.today, occasion=args.occasion or "everyday", shuffle=0, lat=None, lon=None)
    return {"occasion": page["occasion"], "season": page["season"],
            "outfits": [outfit_for_model(o, ctx.ledger) for o in page["outfits"]], "missing": page["missing"]}


# ---------------------------------------------------------------- build_outfit
class BuildArgs(Strict):
    pieces: list[int] = Field(min_length=1, max_length=3)
    occasion: Optional[Occasion] = None


def build_outfit(ctx, args):
    page = screen(ctx, dress_routes.build, BuildIn(item_ids=args.pieces, occasion=args.occasion))
    return {"outfits": [outfit_for_model(o, ctx.ledger) for o in page["outfits"]],
            "notes": [n["code"] for n in page["notes"]]}


# ---------------------------------------------------------------- score_outfit
class ScoreArgs(Strict):
    pieces: list[int] = Field(min_length=2, max_length=6)


def score_outfit(ctx, args):
    result = screen(ctx, outfit_routes.score, ItemIds(item_ids=args.pieces), clash_code="pieces_clash")
    return {"score": round(result["score"]),
            "parts": {k: (None if v is None else round(v * 100)) for k, v in result["parts"].items()},
            "complete": result["complete"], "missing": result["missing"], "reasons": reasons(result)}


GET_WEATHER = Tool("get_weather", (
    "Today's weather at the user's city: temperature, condition, rain, and the season to dress for. "
    "Example: get_weather() before advising a jacket. Do not use it for other days or other cities."),
    WeatherArgs, get_weather)
SUGGEST_OUTFITS = Tool("suggest_outfits", (
    "Today's three outfits from the user's wardrobe, the same ones the Dress page shows, for an occasion. "
    "Example: suggest_outfits(occasion='work') for 'what should I wear to work?'. "
    "Do not use it to build around a piece the user names (use build_outfit)."),
    SuggestArgs, suggest_outfits)
BUILD_OUTFIT = Tool("build_outfit", (
    "Up to three outfits built around 1 to 3 of the user's pieces, given by their numbers from this turn. "
    "Example: build_outfit(pieces=[2]) for 'what goes with my black jeans?' after finding them as {2}. "
    "Do not use it with numbers you were not given in this turn."),
    BuildArgs, build_outfit, piece_args=("pieces",))
SCORE_OUTFIT = Tool("score_outfit", (
    "Score 0-100 for 2 to 6 of the user's pieces worn together, with the part scores and the reasons. "
    "Example: score_outfit(pieces=[1, 3]) for 'do these go together?'. "
    "Do not use it to find new outfits (use suggest_outfits or build_outfit)."),
    ScoreArgs, score_outfit, piece_args=("pieces",))
