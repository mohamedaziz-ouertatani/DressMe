"""
Golden cases for the confidence and the reason codes of "should I buy this?" (step 1).

The four answers recorded in test_golden.py all come out `high` with no code: the frozen wardrobe is
large and complete, and its scans are well labelled. These cases seed parts of the SAME frozen data
(tests/golden/wardrobe.json) so that each code shows up in a recorded answer:

    small_wardrobe          5 pieces: too few to pair the new piece with       -> low
    no_pairing_piece        tops and shoes only, and the new piece is a top    -> medium
    fills_gap               the same wardrobe has no bottom, the listing is a skirt (informs only; the skirt is also
                            far from a taste made only of tops and shoes)
    guessed_and_over_budget a model guess that was flagged and not corrected, and a price above 30 % of the budget
    far_from_style          a t-shirt far from this wardrobe's taste (informs only)

Same rules as test_golden.py: expected answers in tests/golden/expected/buy_advice_codes_*.json,
GOLDEN_RECORD=1 rewrites them, only in a pull request that explains each difference.
"""

import pytest
from bson import ObjectId
from pymongo import MongoClient

import compatibility
from tests.conftest import TEST_DB, sign_up
from tests.test_golden import WARDROBE, check, scrub, stored, when

TOPS_AND_SHOES = ["top_1", "top_2", "top_3", "top_4", "top_5", "shoes_1", "shoes_2", "shoes_3"]
FULL = None                                                    # None = the whole frozen wardrobe

# name: (pieces of the wardrobe to seed, which frozen scan (or the shop listing) to ask about, request extras)
CASES = {
    "small_wardrobe": (["top_1", "top_2", "bottom_1", "shoes_2", "bag_2"], "buy", {}),    # the coat: buy with the full wardrobe, think with these 5
    "no_pairing_piece": (TOPS_AND_SHOES, "think", {}),
    "fills_gap": (TOPS_AND_SHOES, "listing", {}),
    "guessed_and_over_budget": (FULL, "buy", {"price_tnd": 400}),
    "far_from_style": (FULL, "far_style", {}),
}
# the codes each case must show (the recorded answer holds the rest)
EXPECTED_CODES = {
    "small_wardrobe": ["small_wardrobe"],
    "no_pairing_piece": ["no_pairing_piece"],
    "fills_gap": ["fills_gap", "far_from_style"],      # the skirt is also far from a taste made of tops and shoes
    "guessed_and_over_budget": ["guessed_field", "over_budget"],
    "far_from_style": ["far_from_style"],
}
CONFIDENCE = {"small_wardrobe": "low", "no_pairing_piece": "medium", "fills_gap": "high",
              "guessed_and_over_budget": "medium", "far_from_style": "high"}


@pytest.fixture(autouse=True)
def real_rules():
    compatibility.reload_rules()
    yield


def seeded(make_client, settings, keys, budget=None):
    """The golden user with only the given pieces of the frozen wardrobe, and all the scans."""
    client = make_client()
    user = WARDROBE["user"]
    headers = sign_up(client, user["email"], user["name"], user["gender"])
    client.put("/me", json={"min_coverage": user["min_coverage"], **({"budget_tnd": budget} if budget else {})},
               headers=headers)
    db = MongoClient(settings.mongo_url)[TEST_DB]
    user_id = db.users.find_one({"email": user["email"]})["_id"]
    db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"] if keys is None or d["key"] in keys])
    db.candidates.insert_many([stored(d, user_id) for d in WARDROBE["candidates"]])
    listing = WARDROBE["listing"]
    db.listings.insert_one({
        **{k: v for k, v in stored(listing, user_id).items() if k not in ("user_id", "coverage", "season", "usage")},
        "source_id": listing["shop_id"], "external_id": listing["dataset_id"], "title": listing["title"],
        "brand": listing["brand"], "shop_colour": listing["shop_colour"], "gender": listing["gender"], "url": "",
        "price_tnd": listing["price_tnd"], "sizes": listing["sizes"], "sizes_in_stock": listing["sizes"],
        "in_stock": True, "availability_level": "colour", "image_url": "", "checked_at": None, "snapshot": False,
        "price_original": None, "seen_at": when(listing["created_at"]), "status": "active"})
    ids = {d["key"]: d["id"] for d in WARDROBE["candidates"]}
    return client, headers, db, ids, listing["id"]


@pytest.mark.parametrize("name", list(CASES))
def test_codes_and_confidence(make_client, settings, name):
    keys, which, extra = CASES[name]
    client, headers, db, ids, listing_id = seeded(make_client, settings, keys,
                                                  budget=500 if name == "guessed_and_over_budget" else None)
    replace = {}
    if which == "listing":                                        # the Shops path
        candidate = client.post(f"/listings/{listing_id}/candidate", headers=headers).json()
        candidate_id = candidate["id"]
        replace = {candidate_id: "<candidate>"}
    else:
        candidate_id = ids[which]
    if name == "guessed_and_over_budget":                         # a guess the model flagged, never corrected
        db.candidates.update_one({"_id": ObjectId(candidate_id)},
                                 {"$set": {"predicted.colour.unsure": True, "predicted.colour.conf": 0.55}})

    r = client.post("/buy-advice", json={"candidate_id": candidate_id, **extra}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [c["code"] for c in body["codes"]] == EXPECTED_CODES[name]
    assert body["confidence"] == CONFIDENCE[name]
    check(f"buy_advice_codes_{name}", scrub(body, replace))
