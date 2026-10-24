"""
Step 1, the routes: the price, the profile budget, the confidence and codes in /buy-advice, the
`last_advice` snapshot kept on the candidate, and the price a listing candidate copies.

(The golden tests, tests/test_golden.py, prove that the verdict, the counts and the outfits did not
change; the unit tests of the codes are in tests/test_verdict.py.)
"""

import pytest
from bson import ObjectId

import compatibility
from tests.conftest import BLUE, GREEN, RED, photo, sign_up, upload


def scan(client, headers, rgb=GREEN):
    r = client.post("/analyze", files={"photo": photo(rgb)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def ask(client, headers, candidate_id, **more):
    return client.post("/buy-advice", json={"candidate_id": candidate_id, **more}, headers=headers)


def stored(client, candidate_id):
    return client.app.state.db.candidates.find_one({"_id": ObjectId(candidate_id)})


# ---------------------------------------------------------------- the price
def test_price_is_stored_on_the_candidate(client):
    headers = sign_up(client)
    cand = scan(client, headers)
    assert ask(client, headers, cand["id"], price_tnd=45.5).status_code == 200
    assert stored(client, cand["id"])["price_tnd"] == 45.5
    # asking again without a price keeps the one we know
    assert ask(client, headers, cand["id"]).status_code == 200
    assert stored(client, cand["id"])["price_tnd"] == 45.5


def test_no_price_means_null_never_zero(client):
    headers = sign_up(client)
    cand = scan(client, headers)
    assert ask(client, headers, cand["id"]).status_code == 200
    doc = stored(client, cand["id"])
    assert doc.get("price_tnd") is None and doc["last_advice"]["price_tnd"] is None
    assert ask(client, headers, cand["id"], price_tnd=None).status_code == 200       # null = not given
    assert stored(client, cand["id"]).get("price_tnd") is None


@pytest.mark.parametrize("bad", [0, -5, 100001, "cheap"])
def test_a_price_must_be_a_positive_number(client, bad):
    headers = sign_up(client)
    cand = scan(client, headers)
    assert ask(client, headers, cand["id"], price_tnd=bad).status_code == 422
    assert stored(client, cand["id"]).get("price_tnd") is None


def test_the_price_does_not_change_the_verdict(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE):
        upload(client, headers, rgb)
    cand = scan(client, headers, RED)
    plain = ask(client, headers, cand["id"]).json()
    priced = ask(client, headers, cand["id"], price_tnd=999).json()
    for key in ("verdict", "good_outfits", "reasons", "best", "explanation"):
        assert plain[key] == priced[key], key


# ---------------------------------------------------------------- confidence and codes
def test_the_answer_gains_a_confidence_and_codes_and_keeps_everything_else(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE):
        upload(client, headers, rgb)
    body = ask(client, headers, scan(client, headers, RED)["id"]).json()
    assert {"verdict", "good_outfits", "reasons", "candidate", "best", "explanation"} <= set(body)
    assert body["confidence"] in ("high", "medium", "low")
    assert isinstance(body["codes"], list) and all({"code", "params"} == set(c) for c in body["codes"])


def test_a_small_wardrobe_is_reported_with_low_confidence(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE):
        upload(client, headers, rgb)
    body = ask(client, headers, scan(client, headers, RED)["id"]).json()
    small = [c for c in body["codes"] if c["code"] == "small_wardrobe"]
    assert small and small[0]["params"]["owned"] == 2 and body["confidence"] == "low"


def test_a_guess_the_model_flagged_is_reported_until_the_user_corrects_it(client):
    headers = sign_up(client)
    cand = scan(client, headers, RED)
    client.app.state.db.candidates.update_one(
        {"_id": ObjectId(cand["id"])}, {"$set": {"predicted.colour.unsure": True, "predicted.colour.conf": 0.55}})
    first = ask(client, headers, cand["id"]).json()
    assert {"code": "guessed_field", "params": {"field": "colour", "conf": 0.55}} in first["codes"]
    fixed = ask(client, headers, cand["id"], corrections={"colour": "red"}).json()
    assert "guessed_field" not in [c["code"] for c in fixed["codes"]]


# ---------------------------------------------------------------- the budget in the profile
def test_budget_is_part_of_the_profile(client):
    headers = sign_up(client)
    assert client.get("/me", headers=headers).json()["budget_tnd"] is None
    r = client.put("/me", json={"budget_tnd": 150}, headers=headers)
    assert r.status_code == 200 and r.json()["budget_tnd"] == 150
    assert client.put("/me", json={"language": "fr"}, headers=headers).json()["budget_tnd"] == 150     # kept
    assert client.put("/me", json={"budget_tnd": None}, headers=headers).json()["budget_tnd"] is None  # cleared


@pytest.mark.parametrize("bad", [0, -1, "lots"])
def test_a_budget_must_be_a_positive_number(client, bad):
    headers = sign_up(client)
    assert client.put("/me", json={"budget_tnd": bad}, headers=headers).status_code == 422


def test_over_budget_needs_both_the_price_and_the_budget(client):
    headers = sign_up(client)
    cand = scan(client, headers, RED)
    no_budget = ask(client, headers, cand["id"], price_tnd=80).json()
    assert "over_budget" not in [c["code"] for c in no_budget["codes"]]
    client.put("/me", json={"budget_tnd": 100}, headers=headers)
    over = ask(client, headers, cand["id"], price_tnd=80).json()
    assert {"code": "over_budget", "params": {"price": 80.0, "budget": 100.0, "share": 0.8}} in over["codes"]
    cheap = ask(client, headers, cand["id"], price_tnd=20).json()
    assert "over_budget" not in [c["code"] for c in cheap["codes"]]


# ---------------------------------------------------------------- what was shown is remembered
def test_last_advice_is_saved_on_the_candidate(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE):
        upload(client, headers, rgb)
    cand = scan(client, headers, RED)
    assert "last_advice" not in stored(client, cand["id"])                  # nothing shown yet
    body = ask(client, headers, cand["id"], price_tnd=30).json()
    snap = stored(client, cand["id"])["last_advice"]
    s = compatibility.rules_for("women").settings
    assert snap["verdict"] == body["verdict"] and snap["good_outfits"] == body["good_outfits"]
    assert snap["codes"] == body["codes"] and snap["confidence"] == body["confidence"]
    assert snap["thresholds"] == {"good_outfit": s["good_outfit"], "buy_min": int(s["buy_min_outfits"]),
                                  "think_min": int(s["think_min_outfits"])}
    assert snap["price_tnd"] == 30 and snap["computed_at"] is not None


# ---------------------------------------------------------------- listings
def sell_and_approve(client, db, seller_headers, **form):
    data = {"price_tnd": "25", "size": "M", "city": "Tunis", "contact": "@amira", **form}
    r = client.post("/listings/sell", files={"photo": photo(RED)}, data=data, headers=seller_headers)
    assert r.status_code == 201, r.text
    db.listings.update_one({"_id": ObjectId(r.json()["id"])}, {"$set": {"status": "active"}})
    return r.json()["id"]


def test_a_listing_candidate_copies_the_listing_price_in_tnd(client):
    db = client.app.state.db
    seller = sign_up(client)
    buyer = sign_up(client, "buyer@example.com", "Buyer")
    listing_id = sell_and_approve(client, db, seller, price_tnd="25.5")
    r = client.post(f"/listings/{listing_id}/candidate", headers=buyer)
    assert r.status_code == 201, r.text
    assert stored(client, r.json()["id"])["price_tnd"] == 25.5
    # and the verdict for it is saved with that price
    assert ask(client, buyer, r.json()["id"]).status_code == 200
    assert stored(client, r.json()["id"])["last_advice"]["price_tnd"] == 25.5


def test_a_listing_without_a_price_gives_a_candidate_without_one(client):
    db = client.app.state.db
    seller = sign_up(client)
    buyer = sign_up(client, "buyer@example.com", "Buyer")
    listing_id = sell_and_approve(client, db, seller)
    db.listings.update_one({"_id": ObjectId(listing_id)}, {"$set": {"price_tnd": None}})   # a shop with no price
    r = client.post(f"/listings/{listing_id}/candidate", headers=buyer)
    assert stored(client, r.json()["id"])["price_tnd"] is None
