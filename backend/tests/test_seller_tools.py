"""
The seller's tool (step 3e.3), called by a scripted fake model through POST /chat on the golden wardrobe: the price
band is the one GET /price-estimate gives, a piece is a ref and never an id, and a missing price model is an error
the model can read, not a made-up price. (`golden_chat` is in test_explainer_tools.py.)
"""

import pytest

from tests.test_explainer_tools import golden_chat, ref  # noqa: F401  (golden_chat is a fixture)

jacket = lambda p: ref(p, "jacket", "pink")


def route_band(golden_chat, item_id, **query):
    r = golden_chat.client.get("/price-estimate", params={"item_id": item_id, **query}, headers=golden_chat.headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_price_estimate_gives_the_band_the_price_route_gives(golden_chat):
    answer, reads = golden_chat("seller", lambda p: ("price_estimate", {"piece": jacket(p)}))
    seen = reads[1]
    item_id = {int(n): p["id"] for n, p in answer["pieces"].items()}[seen["piece"]]
    route = route_band(golden_chat, item_id)
    assert seen["piece"] == jacket(reads[0]["pieces"])
    assert (seen["low"], seen["median"], seen["high"]) == (route["low"], route["median"], route["high"]) == (20, 25, 32)
    assert seen["channel"] == "friperie" and seen["condition"] == "good" and seen["note"] == route["note"]
    assert set(seen) == {"piece", "channel", "condition", "low", "median", "high", "typical_error_factor", "note"}


def test_the_condition_and_the_channel_are_passed_on(golden_chat):
    answer, reads = golden_chat("seller", lambda p: ("price_estimate", {"piece": jacket(p), "condition": "stained",
                                                                          "channel": "classified"}))
    seen = reads[1]
    item_id = {int(n): p["id"] for n, p in answer["pieces"].items()}[seen["piece"]]
    route = route_band(golden_chat, item_id, condition="stained", channel="classified")
    assert seen["condition"] == "stained" and seen["channel"] == "classified"
    assert (seen["low"], seen["median"], seen["high"]) == (route["low"], route["median"], route["high"])
    assert seen["median"] < 25                                      # a stained piece is worth less than a good one


def test_friperie_shoes_are_rough_for_the_seller_too(golden_chat):
    """mappings/price_low_confidence.csv: friperie shoes. The jacket is relabelled shoes; the type stays jacket."""
    golden_chat.db.items.update_many({"sub_category": "jacket"},
                                     {"$set": {"category": "shoes"}})
    _, reads = golden_chat("seller", lambda p: ("price_estimate", {"piece": jacket(p)}))
    seen = reads[1]
    assert seen["reliable"] is False and "rough" in seen["reliability_note"]
    assert (seen["low"], seen["median"], seen["high"]) == (20, 25, 32)        # the band is still given
    _, reads = golden_chat("seller", lambda p: ("price_estimate", {"piece": jacket(p), "channel": "classified"}))
    assert "reliable" not in reads[1]                                          # classified shoes are fine


def test_without_a_price_model_the_tool_says_so_and_gives_no_price(golden_chat):
    golden_chat.client.app.state.price = None
    _, reads = golden_chat("seller", lambda p: ("price_estimate", {"piece": jacket(p)}))
    assert reads[1]["error"] == "no_price_model" and "low" not in reads[1]


def test_a_number_never_shown_and_a_wrong_channel_are_refused(golden_chat):
    _, reads = golden_chat("seller", ("price_estimate", {"piece": 99}),
                           lambda p: ("price_estimate", {"piece": jacket(p), "channel": "shop"}))
    assert [r["error"] for r in reads[1:]] == ["unknown_piece", "invalid_arguments"]


def test_the_seller_can_find_twins_but_not_use_other_agents_tools(golden_chat):
    _, reads = golden_chat("seller", ("near_twins", {}), ("wardrobe_insights", {}), ("explain_outfit", {"pieces": [1, 2]}))
    assert "twins" in reads[1] and len(reads[1]["twins"]) <= 5
    assert [r["error"] for r in reads[2:]] == ["unknown_tool", "unknown_tool"]


@pytest.mark.parametrize("agent", ["stylist", "explainer", "wardrobe_analyst"])
def test_no_other_agent_can_price_a_piece(golden_chat, agent):
    _, reads = golden_chat(agent, ("price_estimate", {"piece": 1}))
    assert reads[1]["error"] == "unknown_tool"
