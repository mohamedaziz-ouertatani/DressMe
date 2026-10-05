"""
Today's weather, so the Today page suggests outfits for the real day instead of
the calendar month (a warm October day is still "summer" to wear).

Source: Open-Meteo (https://open-meteo.com), free, no API key, non-commercial use.
Settings (see config.py):
    WEATHER_ENGINE   open-meteo (default) or off (then /weather answers 503)
    WEATHER_LAT / WEATHER_LON   the place used when the app sends none (default Tunis)

Privacy: the app's coordinates are rounded to 0.1 degree (~10 km) before they are
sent to Open-Meteo, and they are never stored. Answers are kept in memory for
30 minutes per rounded place, so the free service is not asked again on every visit.

The season thresholds are TEAM rules in mappings/weather_seasons.csv (never tuned
from data without the team).

Check it by hand (from backend/):   python -m app.weather [lat lon]
"""

import csv
import threading
import time

from .config import ROOT

URL = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 30 * 60

# WMO weather codes (what Open-Meteo sends) -> one simple word for the app
CONDITIONS = [
    ((0,), "clear"),
    ((1, 2, 3), "cloudy"),
    ((45, 48), "fog"),
    ((51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82), "rain"),
    ((71, 73, 75, 77, 85, 86), "snow"),
    ((95, 96, 99), "storm"),
]


class WeatherUnavailable(Exception):
    """Open-Meteo could not be reached or sent something unexpected (502)."""


def load_rules(path=ROOT / "mappings" / "weather_seasons.csv"):
    with open(path, encoding="utf-8") as f:
        return {r["name"]: float(r["value"]) for r in csv.DictReader(f)}


RULES = load_rules()


def condition(code):
    for codes, word in CONDITIONS:
        if code in codes:
            return word
    return None


def season_for(feels_min, feels_max, rules=RULES):
    """The season to dress for, from the day's feels-like temperatures (°C)."""
    mean = (feels_min + feels_max) / 2
    if mean >= rules["summer_from"]:
        return "summer"
    if mean < rules["winter_below"]:
        return "winter"
    return "mid-season"


def round_place(lat, lon):
    """~10 km precision: enough for the weather, not enough to find a home."""
    return round(lat, 1), round(lon, 1)


class OpenMeteo:
    def __init__(self, settings, timeout=8.0):
        self.settings = settings
        self.timeout = timeout
        self._cache = {}                 # (lat, lon) -> (time, answer)
        self._lock = threading.Lock()

    def fetch(self, lat, lon):
        """The raw Open-Meteo answer (replaced by a fake in the tests)."""
        import httpx
        params = {
            "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1,
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_min,temperature_2m_max,apparent_temperature_min,"
                     "apparent_temperature_max,precipitation_probability_max,weather_code",
        }
        try:
            r = httpx.get(URL, params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise WeatherUnavailable(f"Open-Meteo: {e}") from e

    def today(self, lat, lon):
        """Today's weather at (lat, lon), already simplified for the app."""
        place = round_place(lat, lon)
        with self._lock:
            hit = self._cache.get(place)
            if hit and time.time() - hit[0] < CACHE_SECONDS:
                return hit[1]
        answer = self.simplify(self.fetch(*place))
        with self._lock:
            self._cache[place] = (time.time(), answer)
        return answer

    @staticmethod
    def simplify(raw):
        try:
            now, day = raw["current"], raw["daily"]
            first = lambda key: day[key][0]
            feels_min, feels_max = first("apparent_temperature_min"), first("apparent_temperature_max")
            rain = first("precipitation_probability_max")
            return {
                "temperature": round(now["temperature_2m"]),
                "feels_like": round(now["apparent_temperature"]),
                "min": round(first("temperature_2m_min")),
                "max": round(first("temperature_2m_max")),
                "condition": condition(now["weather_code"]),
                "rain_probability": None if rain is None else int(rain),
                "rain_likely": rain is not None and rain >= RULES["rain_likely_from"],
                "season": season_for(feels_min, feels_max),
            }
        except (KeyError, IndexError, TypeError) as e:
            raise WeatherUnavailable(f"Unexpected Open-Meteo answer: {e!r}") from e


def make_weather(settings):
    """The weather engine, or None when WEATHER_ENGINE=off."""
    return OpenMeteo(settings) if settings.weather_engine == "open-meteo" else None


if __name__ == "__main__":
    import json
    import sys

    from .config import Settings

    s = Settings()
    lat, lon = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) == 3 else (s.weather_lat, s.weather_lon)
    print(json.dumps(OpenMeteo(s).today(lat, lon), indent=2))
