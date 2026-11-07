"""POST /listings/sell/check: the seller's label check + condition hint before Send.

The engines are the real src/phase4 classes with fixed weights (conftest
fake_label_check / fake_condition_hint): adidas is never 'seen in the photo',
nike always is. FakePriceModel's friperie median is 25 TND.
"""

from tests.conftest import RED, fake_condition_hint, photo, sign_up

FORBIDDEN = ("fake", "counterfeit", "not authentic")


def check(client, headers, rgb=RED, **data):
    return client.post("/listings/sell/check", files={"photo": photo(rgb)}, data=data, headers=headers)


def sell(client, headers, rgb=RED, **data):
    data = {"price_tnd": "10", "city": "Tunis", "contact": "@me", **data}
    return client.post("/listings/sell", files={"photo": photo(rgb)}, data=data, headers=headers)


def test_cheap_claim_the_photo_does_not_support_asks_for_the_label(client):
    headers = sign_up(client)
    r = check(client, headers, title="Basket Adidas original", price_tnd="10")
    assert r.status_code == 200, r.text
    lc = r.json()["label_check"]
    assert lc["claimed_brand"] == "adidas" and lc["photo_supports_claim"] is False
    assert lc["price_ratio"] == 0.4 and lc["unusually_cheap"] is True       # 10 / 25
    assert lc["action"] == "ask_label_photo"
    assert lc["message"] == ("This ad names Adidas. A photo that shows the label or logo "
                             "clearly helps buyers trust it.")
    assert not any(w in r.text.lower() for w in FORBIDDEN)
    # the friperie band, read like GET /price-estimate reads it for a listing
    assert client.app.state.price.calls[-1][1:] == ("top", "friperie")


def test_saves_nothing(client):
    headers = sign_up(client)
    check(client, headers, title="Adidas", price_tnd="10")
    db = client.app.state.db
    assert db.listings.count_documents({}) == 0 and db.candidates.count_documents({}) == 0
    assert db.items.count_documents({}) == 0


def test_one_signal_alone_does_not_ask(client):
    headers = sign_up(client)
    fair = check(client, headers, title="Adidas original", price_tnd="25").json()["label_check"]
    assert fair["photo_supports_claim"] is False and fair["action"] is None   # the photo alone
    seen = check(client, headers, title="Nike Air Max", price_tnd="5").json()["label_check"]
    assert seen["unusually_cheap"] is True and seen["action"] is None         # the price alone


def test_missing_title_or_price_still_answers(client):
    headers = sign_up(client)
    r = check(client, headers).json()
    assert r["label_check"]["claimed_brand"] is None and r["label_check"]["action"] is None
    no_price = check(client, headers, title="Adidas").json()["label_check"]
    assert no_price["price_ratio"] is None and no_price["action"] is None
    assert r["condition_hint"]["action"] is None and 0 <= r["condition_hint"]["looks_new_score"] <= 1


def test_no_price_band_means_no_price_signal(client):
    headers = sign_up(client)
    client.app.state.price = None                 # no price model: estimate_median=None
    lc = check(client, headers, title="Adidas original", price_tnd="1").json()["label_check"]
    assert lc["price_ratio"] is None and lc["action"] is None


def test_condition_hint_low_score_asks_to_check(make_client):
    client = make_client(condition_hint=fake_condition_hint(intercept=-5.0))
    headers = sign_up(client)
    h = check(client, headers).json()["condition_hint"]
    assert h["action"] == "confirm_condition" and h["percentile"] == 0.0
    assert "worn" in h["message"]


def test_engines_missing_answer_null(client):
    headers = sign_up(client)
    client.app.state.label_check = client.app.state.condition_hint = None
    r = check(client, headers, title="Adidas", price_tnd="10")
    assert r.status_code == 200 and r.json() == {"label_check": None, "condition_hint": None}


def test_needs_a_login_and_a_picture(client):
    assert client.post("/listings/sell/check", files={"photo": photo(RED)}).status_code == 401
    headers = sign_up(client)
    bad = client.post("/listings/sell/check", files={"photo": ("x.png", b"not a picture", "image/png")},
                      headers=headers)
    assert bad.status_code == 400
    assert check(client, headers, price_tnd="0").status_code == 422


def test_sell_after_check_reuses_the_analysis(client):
    headers = sign_up(client)
    analyzer = client.app.state.analyzer
    calls = []
    real = analyzer.analyze
    analyzer.analyze = lambda img: calls.append(1) or real(img)
    check(client, headers, title="Adidas", price_tnd="10")
    r = sell(client, headers, title="Adidas")
    assert r.status_code == 201, r.text
    assert len(calls) == 1                         # the same file: analysed once
    other = sign_up(client, email="sami@example.com", name="Sami", gender="men")
    assert sell(client, other).status_code == 201
    assert len(calls) == 2                         # never shared between users


def test_not_on_the_sell_answer_nor_buyer_routes(client):
    headers = sign_up(client)
    sold = sell(client, headers, title="Adidas").json()
    assert "label_check" not in sold and "condition_hint" not in sold
    for path in ("/listings/mine", f"/listings/{sold['id']}"):
        body = client.get(path, headers=headers).text
        assert "label_check" not in body and "condition_hint" not in body
