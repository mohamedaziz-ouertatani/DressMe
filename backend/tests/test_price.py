"""GET /price-estimate: the trained price model's band (a fake here, never the real file),
and PriceModel.estimate itself on a tiny model built in memory."""

import numpy as np

from app import ml  # noqa: F401  (puts src/ on the import path)
import price
from tests.conftest import BLUE, RED, FakePriceModel, photo, sign_up, upload

FIELDS = {"low", "median", "high", "channel", "based_on", "count", "typical_error_factor", "note"}
RULES = {"band_low_pct": 25, "band_high_pct": 75, "min_category_items": 8, "examples": 5, "round_to": 1}


def tiny_model(meta):
    """A 4-d PriceModel with no artifact: two channels, one reference distribution each."""
    rng = np.random.default_rng(0)
    return price.PriceModel(coef=[1, -1, 0.5, 0], intercept=0, mean=[0] * 4, scale=[1] * 4,
                            train_logp=rng.normal(size=50),
                            reference={"friperie": {"*": [10, 20, 25, 30, 40]},
                                       "classified": {"*": [40, 70, 100, 150, 300]}},
                            meta=meta)


def test_error_factor_is_the_channels_own():
    model = tiny_model({"error_factor": 1.94, "error_factor_by_channel": {"friperie": 1.53, "classified": 1.99}})
    v = [0.5, 0.2, 0.1, 0.8]
    assert model.estimate(v, channel="friperie", rules=RULES)["typical_error_factor"] == 1.53
    assert model.estimate(v, channel="classified", rules=RULES)["typical_error_factor"] == 1.99


def test_error_factor_falls_back_to_the_overall_one():
    v = [0.5, 0.2, 0.1, 0.8]
    only_overall = tiny_model({"error_factor": 1.94})
    assert only_overall.estimate(v, channel="friperie", rules=RULES)["typical_error_factor"] == 1.94
    partial = tiny_model({"error_factor": 1.94, "error_factor_by_channel": {"friperie": 1.53}})
    assert partial.estimate(v, channel="classified", rules=RULES)["typical_error_factor"] == 1.94


def test_band_is_never_narrower_than_the_typical_error():
    """A tight reference distribution (every price 38-42 TND) would give a band of about x1.05;
    the band must still span at least median / err to median * err."""
    model = price.PriceModel(coef=[1, -1, 0.5, 0], intercept=0, mean=[0] * 4, scale=[1] * 4,
                             train_logp=np.random.default_rng(0).normal(size=50),
                             reference={"friperie": {"*": [38, 39, 40, 40, 41, 42]}},
                             meta={"error_factor_by_channel": {"friperie": 1.53}})
    for v in ([0.5, 0.2, 0.1, 0.8], [-1, 1, 0, 0], [1, -1, 1, 0]):
        band = model.estimate(v, channel="friperie", rules=RULES)
        m = band["median"]
        assert 38 <= m <= 42
        assert band["low"] <= round(m / 1.53) and band["high"] >= round(m * 1.53)
        assert band["low"] <= m <= band["high"]


def test_band_is_not_widened_without_an_error_factor():
    model = price.PriceModel(coef=[1, -1, 0.5, 0], intercept=0, mean=[0] * 4, scale=[1] * 4,
                             train_logp=np.random.default_rng(0).normal(size=50),
                             reference={"friperie": {"*": [38, 39, 40, 40, 41, 42]}}, meta={})
    band = model.estimate([0.5, 0.2, 0.1, 0.8], channel="friperie", rules=RULES)
    assert 38 <= band["low"] and band["high"] <= 42


def scan(client, headers, rgb=RED):
    r = client.post("/analyze", files={"photo": photo(rgb)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_band_for_a_scan(make_client):
    model = FakePriceModel()
    client = make_client(price=model)
    headers = sign_up(client)
    r = client.get("/price-estimate", params={"candidate_id": scan(client, headers)}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == FIELDS                       # whitelist only: no vector, no percentile
    assert (body["low"], body["median"], body["high"]) == (20, 25, 32)
    assert body["channel"] == "friperie" and body["note"]
    assert model.calls == [(512, "top", "friperie")]    # the stored vector, the scan's category


def test_band_for_an_item_and_a_channel(make_client):
    model = FakePriceModel()
    client = make_client(price=model)
    headers = sign_up(client)
    item = upload(client, headers, BLUE)
    r = client.get("/price-estimate", params={"item_id": item["id"], "channel": "classified"}, headers=headers)
    assert r.status_code == 200 and r.json()["channel"] == "classified"
    assert model.calls == [(512, "bottom", "classified")]


def test_unknown_channel_gives_nulls_never_zero(client):
    headers = sign_up(client)
    r = client.get("/price-estimate", params={"candidate_id": scan(client, headers), "channel": "boutique"},
                   headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == FIELDS
    for k in ("low", "median", "high", "based_on", "count", "typical_error_factor"):
        assert body[k] is None
    assert body["channel"] == "boutique" and body["note"]


def test_switched_off(client):
    headers = sign_up(client)
    cand = scan(client, headers)
    client.app.state.price = None                    # no price_model.joblib
    assert client.get("/price-estimate", params={"candidate_id": cand}, headers=headers).status_code == 503


def test_another_users_scan_is_404(client):
    cand = scan(client, sign_up(client))
    other = sign_up(client, email="sami@example.com", name="Sami", gender="men")
    assert client.get("/price-estimate", params={"candidate_id": cand}, headers=other).status_code == 404


def test_exactly_one_id(client):
    headers = sign_up(client)
    assert client.get("/price-estimate", headers=headers).status_code == 422
