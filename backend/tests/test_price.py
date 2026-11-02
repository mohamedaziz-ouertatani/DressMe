"""GET /price-estimate: the trained price model's band (a fake here, never the real file),
and PriceModel.estimate itself on a tiny model built in memory."""

import numpy as np

from app import ml  # noqa: F401  (puts src/ on the import path)
import price
from tests.conftest import BLUE, RED, FakePriceModel, photo, sign_up, upload

FIELDS = {"low", "median", "high", "channel", "based_on", "count", "typical_error_factor", "note"}
# an item or a scan also says the condition used (default good)
ITEM_FIELDS = FIELDS | {"condition", "condition_factor"}
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


# ------------------------------------------------- the two model kinds and their artifacts
REFERENCE = {"friperie": {"*": [10, 20, 25, 30, 40, 55]}, "classified": {"*": [40, 70, 100, 150, 300]}}


def tiny_svr():
    """A 4-d RBF-SVR PriceModel, fitted in memory, as train_price.py builds it."""
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVR
    rng = np.random.default_rng(1)
    X = rng.normal(size=(60, 4))
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    y = X @ np.array([1.0, -1.0, 0.5, 0.0]) + rng.normal(scale=0.1, size=60)
    pipe = make_pipeline(StandardScaler(), SVR(kernel="rbf", gamma="scale", C=1, epsilon=0.1)).fit(X, y)
    return price.PriceModel(kind="svr", pipeline=pipe, train_logp=pipe.predict(X), reference=REFERENCE,
                            meta={"model": "svr", "error_factor_by_channel": {"friperie": 1.44}})


def test_svr_save_load_round_trip(tmp_path):
    model = tiny_svr()
    back = price.PriceModel.load(model.save(tmp_path / "svr.joblib"))
    assert back.kind == "svr" and back.meta == model.meta
    for v in ([0.5, 0.2, 0.1, 0.8], [-1, 1, 0, 0], [1, -1, 1, 0]):
        assert back.percentile_of(v) == model.percentile_of(v)
        assert back.estimate(v, channel="friperie", rules=RULES) == model.estimate(v, channel="friperie", rules=RULES)


def test_estimate_with_an_svr_model_returns_a_band():
    model = tiny_svr()
    band = model.estimate([0.5, 0.2, 0.1, 0.8], channel="friperie", rules=RULES)
    assert band["low"] <= band["median"] <= band["high"]
    assert band["typical_error_factor"] == 1.44 and band["channel"] == "friperie"
    assert model.estimate([0.5, 0.2, 0.1, 0.8], channel="boutique", rules=RULES) is None
    # an expensive-direction vector ranks above a cheap-direction one
    assert model.percentile_of([1, -1, 0.5, 0]) > model.percentile_of([-1, 1, -0.5, 0])


def test_old_linear_artifact_without_kind_still_loads(tmp_path):
    """Teammates have a price_model.joblib written before the svr kind: no "kind" key."""
    import joblib
    old = tiny_model({"error_factor_by_channel": {"friperie": 1.53}})
    path = tmp_path / "old.joblib"
    joblib.dump({"coef": old.coef, "intercept": old.intercept, "mean": old.mean, "scale": old.scale,
                 "train_logp": old.train_logp, "reference": old.reference, "meta": old.meta}, path)
    back = price.PriceModel.load(path)
    assert back.kind == "linear"
    v = [0.5, 0.2, 0.1, 0.8]
    band = back.estimate(v, channel="friperie", rules=RULES)
    assert band == old.estimate(v, channel="friperie", rules=RULES)
    assert band["typical_error_factor"] == 1.53


def test_unknown_kind_is_refused():
    import pytest
    with pytest.raises(ValueError):
        price.PriceModel(kind="forest", train_logp=[0, 1], reference=REFERENCE)


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
    assert set(body) == ITEM_FIELDS                  # whitelist only: no vector, no percentile
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
    assert set(body) == ITEM_FIELDS
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


# ------------------------------------------------- the garment's condition (the model does not see it)
def test_team_condition_factors():
    rules = price.load_rules()
    assert {c: rules[f"condition_{c}"] for c in price.CONDITIONS} == \
        {"new_tags": 1.43, "like_new": 1.20, "good": 1.00, "stained": 0.55, "torn": 0.21}


def test_each_condition_multiplies_the_band(client):
    headers = sign_up(client)
    cand = scan(client, headers)
    rules = price.load_rules()
    for condition in price.CONDITIONS:
        r = client.get("/price-estimate", params={"candidate_id": cand, "condition": condition}, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        f = rules[f"condition_{condition}"]
        assert body["condition"] == condition and body["condition_factor"] == f
        # the fake band is 20 / 25 / 32, rounded to round_to (1 TND)
        assert (body["low"], body["median"], body["high"]) == (round(20 * f), round(25 * f), round(32 * f))
        assert body["note"] and body["count"] == 53          # the rest of the answer is untouched


def test_default_is_good_and_unchanged(client):
    headers = sign_up(client)
    cand = scan(client, headers)
    plain = client.get("/price-estimate", params={"candidate_id": cand}, headers=headers).json()
    good = client.get("/price-estimate", params={"candidate_id": cand, "condition": "good"}, headers=headers).json()
    assert plain == good
    assert (plain["low"], plain["median"], plain["high"]) == (20, 25, 32)   # the model's own band
    assert plain["condition"] == "good" and plain["condition_factor"] == 1.0


def test_unknown_condition_is_422(client):
    headers = sign_up(client)
    cand = scan(client, headers)
    for bad in ("faded", "GOOD", ""):
        r = client.get("/price-estimate", params={"candidate_id": cand, "condition": bad}, headers=headers)
        assert r.status_code == 422, bad


def test_with_condition_rounds_and_keeps_nulls():
    rules = {**price.load_rules(), "round_to": 5}
    band = price.with_condition({"low": 20, "median": 40, "high": 60, "note": "n"}, "stained", rules)
    assert (band["low"], band["median"], band["high"]) == (10, 20, 35)     # 11, 22, 33 to the nearest 5
    assert band["note"] == "n" and band["condition_factor"] == 0.55
    assert price.with_condition({"low": None, "median": None, "high": None}, "torn", rules)["median"] is None


def test_missing_or_bad_condition_setting_stops_load_rules(tmp_path):
    import pytest
    lines = price.RULES_CSV.read_text(encoding="utf-8").splitlines()
    missing = tmp_path / "missing.csv"
    missing.write_text("\n".join(l for l in lines if not l.startswith("setting,condition_torn,")), encoding="utf-8")
    with pytest.raises(ValueError, match="condition_torn"):
        price.load_rules(missing)
    zero = tmp_path / "zero.csv"
    zero.write_text("\n".join(l.replace("condition_stained,0.55", "condition_stained,0") for l in lines),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="condition_stained"):
        price.load_rules(zero)


def test_a_listing_ignores_the_condition(make_client):
    """Seller listings have no condition field: band and tag stay the model's."""
    client = make_client()
    lid = listed(client, 30)
    headers = sign_up(client)
    plain = tag_of(client, headers, lid)
    torn = client.get("/price-estimate", params={"listing_id": lid, "condition": "torn"}, headers=headers).json()
    assert torn == plain and "condition" not in plain and plain["median"] == 25


# ------------------------------------------------- a friperie seller's listing: band + tag
def sell(client, headers, price_tnd):
    r = client.post("/listings/sell", files={"photo": photo(RED)}, headers=headers,
                    data={"price_tnd": str(price_tnd), "size": "M", "city": "Tunis", "contact": "@amira.friperie"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def listed(client, price_tnd):
    """An approved seller listing at this price (the fake model's median is 25 TND)."""
    from bson import ObjectId
    lid = sell(client, sign_up(client, email=f"seller{price_tnd}@example.com"), price_tnd)
    client.app.state.db.listings.update_one({"_id": ObjectId(lid)}, {"$set": {"status": "active"}})
    return lid


def tag_of(client, headers, lid):
    r = client.get("/price-estimate", params={"listing_id": lid}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def with_priced_high(monkeypatch, on):
    rules = price.load_rules()
    monkeypatch.setattr(price, "load_rules", lambda *a, **k: {**rules, "show_priced_high": on})


def test_team_settings_for_the_tag():
    rules = price.load_rules()
    assert rules["tag_factor"] == 2 and rules["show_priced_high"] == 1


def test_cheap_seller_listing_is_a_good_deal(make_client):
    model = FakePriceModel()
    client = make_client(price=model)
    buyer = sign_up(client)
    body = tag_of(client, buyer, listed(client, 10))           # 10 < 25 / 2
    assert body["tag"] == "good_deal"
    assert (body["low"], body["median"], body["high"]) == (20, 25, 32) and body["channel"] == "friperie"
    assert set(body) == FIELDS | {"tag"}                       # still no vector, no percentile
    assert model.calls == [(512, "top", "friperie")]           # the listing's stored vector and category


def test_dear_seller_listing_is_priced_high_only_when_switched_on(client, monkeypatch):
    buyer = sign_up(client)
    lid = listed(client, 60)                                   # 60 > 25 x 2
    with_priced_high(monkeypatch, 0)
    assert tag_of(client, buyer, lid)["tag"] is None           # switched off
    with_priced_high(monkeypatch, 1)
    assert tag_of(client, buyer, lid)["tag"] == "priced_high"


def test_above_the_band_but_within_x2_is_not_tagged(client, monkeypatch):
    """40 TND is above the band (high = 32), so the band-edge rule would call it high;
    the median x tag_factor rule (50) does not, even with priced_high switched on."""
    with_priced_high(monkeypatch, 1)
    buyer = sign_up(client)
    body = tag_of(client, buyer, listed(client, 40))
    assert body["high"] < 40 and body["tag"] is None


def test_shop_listing_gets_no_band_and_no_tag(make_client):
    from datetime import datetime, timezone
    from bson import ObjectId
    model = FakePriceModel()
    client = make_client(price=model)
    lid = ObjectId()
    client.app.state.db.listings.insert_one({
        "_id": lid, "source_id": "exist_tn", "external_id": "ex_1", "status": "active", "in_stock": True,
        "price_tnd": 10, "category": "top", "seen_at": datetime.now(timezone.utc)})
    body = tag_of(client, sign_up(client), str(lid))
    assert body["tag"] is None and body["low"] is None and body["median"] is None
    assert model.calls == []                                   # new clothes are never priced as friperie


def test_another_users_pending_listing_is_404(client):
    lid = sell(client, sign_up(client), 10)                    # pending: not approved yet
    other = sign_up(client, email="sami@example.com", name="Sami", gender="men")
    assert client.get("/price-estimate", params={"listing_id": lid}, headers=other).status_code == 404


def test_listing_without_the_model_is_503(client):
    buyer = sign_up(client)
    lid = listed(client, 10)
    client.app.state.price = None
    assert client.get("/price-estimate", params={"listing_id": lid}, headers=buyer).status_code == 503


def test_a_listing_is_only_priced_against_friperie(client):
    buyer = sign_up(client)
    r = client.get("/price-estimate", params={"listing_id": listed(client, 10), "channel": "classified"},
                   headers=buyer)
    assert r.status_code == 422
