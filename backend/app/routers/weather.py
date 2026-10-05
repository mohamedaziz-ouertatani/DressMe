"""
GET /weather: today's weather and the season to dress for (see weather.py).
The app sends its rounded position if the user allowed it; otherwise the
default place (WEATHER_LAT / WEATHER_LON, Tunis) is used.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..security import current_user
from ..weather import WeatherUnavailable, round_place

router = APIRouter(tags=["weather"])


@router.get("/weather")
async def weather(request: Request, lat: float | None = Query(None, ge=-90, le=90),
                  lon: float | None = Query(None, ge=-180, le=180), user=Depends(current_user)):
    engine = request.app.state.weather
    if engine is None:
        raise HTTPException(503, "Weather is switched off (WEATHER_ENGINE=off)")
    if (lat is None) != (lon is None):
        raise HTTPException(422, "Give both lat and lon, or neither")
    settings = request.app.state.settings
    here = lat is not None
    if not here:
        lat, lon = settings.weather_lat, settings.weather_lon
    try:
        today = await run_in_threadpool(engine.today, lat, lon)   # a network call: off the event loop
    except WeatherUnavailable as e:
        raise HTTPException(502, str(e))
    lat, lon = round_place(lat, lon)
    return {**today, "place": "here" if here else settings.weather_place, "lat": lat, "lon": lon}
