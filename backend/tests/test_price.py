"""GET /price-estimate: the trained price model's band (a fake here, never the real file)."""

from tests.conftest import BLUE, RED, FakePriceModel, photo, sign_up, upload

FIELDS = {"low", "median", "high", "channel", "based_on", "count", "typical_error_factor", "note"}


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
