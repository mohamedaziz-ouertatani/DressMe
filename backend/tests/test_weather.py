"""GET /weather and the weather -> season rules (no network: a fake Open-Meteo)."""

import pytest

from app.weather import OpenMeteo, WeatherUnavailable, condition, round_place, season_for

from .conftest import FakeWeather, open_meteo_answer, sign_up

RULES = {"summer_from": 24, "winter_below": 14, "rain_likely_from": 50}


@pytest.mark.parametrize("feels, season", [((22, 30), "summer"), ((18, 27), "mid-season"),
                                           ((6, 15), "winter"), ((9, 19), "mid-season")])
def test_season_from_feels_like(feels, season):
    assert season_for(*feels, rules=RULES) == season


def test_conditions_and_rounding():
    assert [condition(c) for c in (0, 3, 45, 63, 81, 75, 95, 42)] == \
        ["clear", "cloudy", "fog", "rain", "rain", "snow", "storm", None]
    assert round_place(36.8065, 10.1815) == (36.8, 10.2)


def test_unexpected_answer_is_502_material():
    with pytest.raises(WeatherUnavailable):
        OpenMeteo.simplify({"current": {}})


def test_default_place(make_client):
    weather = FakeWeather(open_meteo_answer(feels=(22, 30), rain=70, code=61))
    client = make_client(weather=weather)
    r = client.get("/weather", headers=sign_up(client))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["place"] == "Tunis" and body["season"] == "summer"
    assert body["condition"] == "rain" and body["rain_likely"] is True
    assert body["temperature"] == 26 and body["rain_probability"] == 70
    assert weather.calls == [(36.8, 10.2)]


def test_position_is_rounded_and_cached(make_client):
    weather = FakeWeather(open_meteo_answer(feels=(5, 12)))
    client = make_client(weather=weather)
    headers = sign_up(client)
    for lat in (35.8256, 35.8301):        # same ~10 km square
        r = client.get("/weather", params={"lat": lat, "lon": 10.6369}, headers=headers)
        assert r.status_code == 200
    assert r.json()["place"] == "here" and r.json()["season"] == "winter"
    assert weather.calls == [(35.8, 10.6)]   # only one call, with the rounded position


def test_errors(make_client):
    client = make_client()
    headers = sign_up(client)
    assert client.get("/weather").status_code == 401
    assert client.get("/weather", params={"lat": 36.8}, headers=headers).status_code == 422
    assert client.get("/weather", params={"lat": 120, "lon": 0}, headers=headers).status_code == 422

    class Down(FakeWeather):
        def fetch(self, lat, lon):
            raise WeatherUnavailable("Open-Meteo: timeout")
    assert make_client(weather=Down()).get("/weather", headers=headers).status_code == 502


def test_switched_off(client):
    client.app.state.weather = None          # what WEATHER_ENGINE=off gives
    assert client.get("/weather", headers=sign_up(client)).status_code == 503
