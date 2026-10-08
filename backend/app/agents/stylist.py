"""
The Stylist agent: "what do I wear?". It builds and scores outfits from the
user's real wardrobe.
"""

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..routers.outfits import user_profile, wardrobe
from ..wardrobe import describe, outfit_out, to_compat
from ..weather import WeatherUnavailable
from .common import Agent, list_wardrobe_tool


def tools(request, user):
    """The Stylist's tools, bound to this user."""
    def suggest_outfits(season: str = "", occasion: str = "", n: int = 1) -> list[dict]:
        """Recommend one best outfit from the user's wardrobe. season: summer, winter or
        mid-season. occasion: casual, formal, sport, wedding, eid or work. n: how many
        when the user explicitly asks for more (1-10)."""
        docs, by_id = wardrobe(request, user)
        outfits = compatibility.suggest_outfits(
            [to_compat(d) for d in docs], user_profile(
                user, docs, request, season or None, occasion or None),
            n=max(1, min(int(n), 10)))
        return [outfit_out(o, by_id) for o in outfits]

    def score_outfit(item_ids: list[str]) -> dict:
        """Score (0-100) and reasons for an outfit made of the user's items (ids from list_wardrobe)."""
        docs, by_id = wardrobe(request, user)
        chosen = [by_id[i] for i in item_ids if i in by_id]
        if not chosen:
            return {"error": "none of these ids are in the wardrobe"}
        items = [to_compat(d) for d in chosen]
        clash = compatibility.clashes(items)
        if clash:          # same hard rule as /outfits/score
            return {"error": "these pieces can't be worn together: " + "; ".join(clash)}
        return outfit_out({**compatibility.score_outfit(
            items, style_profile=user_profile(user, docs, request)["style_vector"]),
            "items": items}, by_id)

    def complete_outfit(item_ids: list[str], k: int = 3) -> dict:
        """The best pieces of the user's wardrobe to add to these items (ids from
        list_wardrobe), with the score of the outfit each one makes. k: how many (1-5)."""
        docs, by_id = wardrobe(request, user)
        chosen = [by_id[i] for i in item_ids if i in by_id]
        if not chosen:
            return {"error": "none of these ids are in the wardrobe"}
        items = [to_compat(d) for d in chosen]
        clash = compatibility.clashes(items)
        if clash:
            return {"error": "these pieces can't be worn together: " + "; ".join(clash)}
        candidates = [to_compat(d) for d in docs if str(d["_id"]) not in item_ids]
        ranked = compatibility.complete_outfit(
            items, candidates, user_profile(user, docs, request), k=max(1, min(int(k), 5)))
        return {"completions": [
            {**outfit_out({**r, "items": items + [r["item"]]}, by_id), "added": describe(r["item"], by_id)}
            for r in ranked]}

    def get_weather() -> dict:
        """Today's weather in the user's city: temperature, condition, rain chance and
        the season to dress for (summer, winter or mid-season)."""
        engine = request.app.state.weather
        if engine is None:                       # WEATHER_ENGINE=off
            return {"error": "weather unavailable"}
        settings = request.app.state.settings
        try:   # the default place only: no user position ever reaches the model
            today = engine.today(settings.weather_lat, settings.weather_lon)
        except WeatherUnavailable:
            return {"error": "weather unavailable"}
        return {**today, "place": settings.weather_place}

    functions = (list_wardrobe_tool(request, user), suggest_outfits, score_outfit,
                 complete_outfit, get_weather)
    return {f.__name__: f for f in functions}


AGENT = Agent(
    name="stylist", title="Stylist",
    description="what to wear today or for an occasion, outfits from the user's clothes, the weather",
    job=("help the user decide what to wear. Use suggest_outfits for a new outfit (check get_weather "
         "first when they talk about today), score_outfit to judge one they picked, and "
         "complete_outfit when they have some pieces and want the rest."),
    tools=tools)
