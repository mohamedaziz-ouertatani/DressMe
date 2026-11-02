"""
The shopping agent's tools (step 3e.5), called by a scripted fake model through POST /chat on the golden wardrobe and
the evaluation's five fixed fake listings (app.eval_traps.seed_listings): a listing has its own numbers, the model
never reads a seller's name, city or contact, and the buy flow gives the same verdict as /buy-advice.
(`golden_chat` is in test_explainer_tools.py.)
"""

import copy
import json

import pytest
from bson import ObjectId

from app.eval_traps import FAKE_CONTACT, seed_listings
from tests.test_explainer_tools import OWNED, golden_chat, ref  # noqa: F401  (golden_chat is a fixture)

LISTING_KEYS = {"listing", "title", "price_tnd", "shop", "category", "colour"}
BAG_UNDER_50 = {"category": "bag", "colour": "black", "max_price": 50}
FAKE_HANDBAG = ObjectId("5f0c02" + f"{1:018x}")


@pytest.fixture
def shop(golden_chat):
    """The golden user with five fake listings. The shopping agent also gets list_wardrobe here (test only), so the
    fake model can first read the piece numbers it needs."""
    golden_chat.client.app.state.agents.agents["shopping"].tools.append("list_wardrobe")
    assert seed_listings(golden_chat.db) == 5
    return golden_chat


def number_of(shop, words):
    """The listing number the model was given (by the search of step 1) for the listing whose title has these words."""
    return next(x["listing"] for x in shop.reads[1]["listings"] if words in x["title"].lower())


def assert_no_contact(reads):
    text = json.dumps(reads)
    assert FAKE_CONTACT not in text and "Sfax" not in text and "city" not in text and "contact" not in text


def test_the_fake_listings_are_flagged_so_the_evaluation_can_delete_them(shop):
    assert shop.db.listings.count_documents({"eval_fake": True}) == shop.db.listings.count_documents({}) == 5
    shop.db.listings.delete_many({"eval_fake": True})
    assert shop.db.listings.count_documents({}) == 0


# ---------------------------------------------------------------- search_listings
def test_search_listings_shows_numbers_and_nothing_about_the_seller(shop):
    _, reads = shop("shopping", ("search_listings", {}))
    seen = reads[1]
    assert seen["total"] == 5 and len(seen["listings"]) == 5
    assert sorted(x["listing"] for x in seen["listings"]) == [1, 2, 3, 4, 5]
    assert all(set(x) == LISTING_KEYS and x["shop"] for x in seen["listings"])
    assert_no_contact(reads)
    jacket = next(x for x in seen["listings"] if x["category"] == "outerwear")      # the friperie seller's listing
    assert jacket["title"] == "black jacket" and "denim" not in json.dumps(seen).lower()   # their free text is not shown


def test_the_filters_are_the_listing_routes(shop):
    _, reads = shop("shopping", ("search_listings", BAG_UNDER_50))
    assert [(x["title"], x["price_tnd"]) for x in reads[1]["listings"]] == [("Black leather handbag", 45)]
    route = shop.client.get("/listings", params={"category": "bag", "colour": "black", "max_price": 50},
                            headers=shop.headers).json()
    assert reads[1]["total"] == route["total"] == 1


def test_the_other_genders_listings_stay_hidden_as_in_the_route(shop):
    men = copy.deepcopy(shop.db.listings.find_one({"_id": FAKE_HANDBAG}))
    men.update(_id=ObjectId(), external_id="fake-men", gender="men", title="Men's bag")
    shop.db.listings.insert_one(men)
    _, reads = shop("shopping", ("search_listings", {}))
    assert reads[1]["total"] == 5 and "Men's bag" not in json.dumps(reads[1])


# ---------------------------------------------------------------- similar_pieces
def test_similar_pieces_gives_listings_and_the_closest_own_piece(shop):
    answer, reads = shop("shopping", lambda p: ("similar_pieces", {"piece": ref(p, "casual-shoes", "brown")}))
    seen = reads[1]
    assert seen["piece"] == ref(reads[0]["pieces"], "casual-shoes", "brown")
    assert 1 <= len(seen["listings"]) <= 5 and seen["listings"][0]["title"] == "Brown leather loafers"
    assert all(set(x) == LISTING_KEYS | {"similarity"} for x in seen["listings"])
    own = seen["closest_own_piece"]
    assert own["ref"] != seen["piece"] and own["ref"] in {int(n) for n in answer["pieces"]}
    assert_no_contact(reads)


# ---------------------------------------------------------------- buy_advice
def test_the_buy_flow_gives_the_buy_advice_routes_verdict_and_reuses_the_candidate(shop):
    answer, reads = shop("shopping", ("search_listings", BAG_UNDER_50),
                         lambda p: ("buy_advice", {"listing": number_of(shop, "handbag")}))
    seen = reads[2]
    assert seen["listing"] == 1 and seen["verdict"] in ("buy", "think", "skip")
    assert seen["confidence"] in ("high", "medium", "low") and isinstance(seen["good_outfits"], int)
    assert len(seen["best_outfits_with_it"]) <= 3 and all(isinstance(c, dict) and "code" in c for c in seen["codes"])
    named = {int(n) for n in answer["pieces"]}
    for outfit in seen["best_outfits_with_it"]:                     # the user's own pieces: never the candidate
        assert outfit["pieces"] and set(outfit["pieces"]) <= named and 0 <= outfit["score"] <= 100
    assert set(answer["pieces"][n]["id"] for n in answer["pieces"]) <= OWNED
    assert_no_contact(reads)

    candidates = list(shop.db.candidates.find({"listing_id": FAKE_HANDBAG}))
    assert len(candidates) == 1                                      # made from the listing
    route = shop.client.post("/buy-advice", json={"candidate_id": str(candidates[0]["_id"])}, headers=shop.headers).json()
    assert (seen["verdict"], seen["good_outfits"], seen["confidence"]) == \
        (route["verdict"], route["good_outfits"], route["confidence"])

    shop("shopping", ("search_listings", BAG_UNDER_50), lambda p: ("buy_advice", {"listing": 1}))
    assert shop.db.candidates.count_documents({"listing_id": FAKE_HANDBAG}) == 1       # asked again: not a second one


# ---------------------------------------------------------------- numbers
def test_a_listing_number_from_another_turn_is_refused(shop):
    shop("shopping", ("search_listings", {}))                       # turn 1 shows listings 1 to 5 ...
    _, reads = shop("shopping", ("buy_advice", {"listing": 1}))     # ... turn 2 has shown pieces only
    assert reads[1]["error"] == "unknown_listing"
    assert shop.db.candidates.count_documents({}) == 0              # nothing was made from it


def test_pieces_and_listings_are_numbered_apart(shop):
    _, reads = shop("shopping", ("similar_pieces", {"piece": 99}), ("price_estimate_listing", {"listing": 12}))
    assert [r["error"] for r in reads[1:]] == ["unknown_piece", "unknown_listing"]
    # 17 pieces were shown (numbers 1 to 17), but no listing: piece numbers never open a listing
    _, reads = shop("shopping", ("buy_advice", {"listing": 3}))
    assert reads[1]["error"] == "unknown_listing"


# ---------------------------------------------------------------- price_estimate_listing
def test_a_friperie_listing_gets_a_band_and_a_shop_listing_does_not(shop):
    _, reads = shop("shopping", ("search_listings", {}),
                    lambda p: ("price_estimate_listing", {"listing": number_of(shop, "black jacket")}),
                    lambda p: ("price_estimate_listing", {"listing": number_of(shop, "handbag")}))
    seller, shopfront = reads[2], reads[3]
    assert (seller["low"], seller["median"], seller["high"]) == (20, 25, 32) and "tag" in seller
    assert (shopfront["low"], shopfront["median"], shopfront["high"]) == (None, None, None)
    assert_no_contact(reads)


def test_without_a_price_model_the_listing_tool_says_so(shop):
    shop.client.app.state.price = None
    _, reads = shop("shopping", ("search_listings", {}),
                    lambda p: ("price_estimate_listing", {"listing": number_of(shop, "black jacket")}))
    assert reads[2]["error"] == "no_price_model"


# ---------------------------------------------------------------- who may use what
def test_the_stylist_cannot_use_the_shopping_tools_and_the_tools_stay_apart(golden_chat):
    _, reads = golden_chat("stylist", ("search_listings", {}), ("buy_advice", {"listing": 1}),
                           ("similar_pieces", {"piece": 1}), ("price_estimate_listing", {"listing": 1}))
    assert [r["error"] for r in reads[1:]] == ["unknown_tool"] * 4


def test_the_shopping_agent_was_not_given_the_stylists_tools(shop):
    _, reads = shop("shopping", ("build_outfit", {"pieces": [1]}), ("score_outfit", {"pieces": [1, 2]}))
    assert [r["error"] for r in reads[1:]] == ["unknown_tool", "unknown_tool"]
