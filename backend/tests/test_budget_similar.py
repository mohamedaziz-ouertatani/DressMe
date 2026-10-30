"""GET /similar respects the budget: the shop listings row keeps only listings with a known price up to
budget x budget_share (mappings/verdict_rules.csv), and ListingIndex.search(max_price=...) does the filtering."""

import verdict
from tests.conftest import RED, fake_vector, photo, sign_up
from tests.test_listings import raw, sync

# five red tops (the fake labeller reads them as tops): no price, 0, and three real prices
PRICES = {"none": None, "zero": 0, "p20": 20, "p30": 30, "p80": 80}


def seed(client):
    sync(client, [raw(ext, RED, price=p) for ext, p in PRICES.items()])


def titles(hits):
    return sorted(h["title"].removeprefix("Product ") for h in hits)


def search(client, **kw):
    return client.app.state.listing_index.search(client.app.state.db, fake_vector(sum(RED)), k=10,
                                                 category="top", **kw)


# ------------------------------------------------------------------ ListingIndex.search
def test_search_without_max_price_is_unchanged(client):
    seed(client)
    assert titles(search(client)) == sorted(PRICES)                       # every price, none and 0 too
    assert titles(search(client, max_price=None)) == sorted(PRICES)


def test_search_max_price_drops_no_price_zero_and_too_dear(client):
    seed(client)
    assert titles(search(client, max_price=30)) == ["p20", "p30"]         # 30 itself is kept (<=)
    assert titles(search(client, max_price=1000)) == ["p20", "p30", "p80"]   # null and 0 never pass


def test_search_still_returns_k_when_enough_are_cheap(client):
    sync(client, [raw(f"dear{i}", RED, price=500) for i in range(6)] +
         [raw(f"cheap{i}", RED, price=10 + i) for i in range(4)])
    hits = client.app.state.listing_index.search(client.app.state.db, fake_vector(sum(RED)), k=4,
                                                 category="top", max_price=50)
    assert len(hits) == 4 and all(0 < h["price_tnd"] <= 50 for h in hits)


# ------------------------------------------------------------------ GET /similar
def scan(client, headers):
    r = client.post("/analyze", files={"photo": photo(RED)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_similar_without_a_budget_is_unchanged(client):
    seed(client)
    headers = sign_up(client)
    body = client.get(f"/similar?candidate_id={scan(client, headers)}&k=10", headers=headers).json()
    assert body["budget_cap"] is None
    assert titles(body["listings"]) == sorted(PRICES)


def test_similar_with_a_budget_caps_the_listings(client):
    seed(client)
    headers = sign_up(client)
    client.put("/me", json={"budget_tnd": 100}, headers=headers)
    cap = round(100 * verdict.load_rules()["budget_share"], 2)               # the team's share, not a literal
    body = client.get(f"/similar?candidate_id={scan(client, headers)}&k=10", headers=headers).json()
    assert body["budget_cap"] == cap
    assert body["listings"] and all(0 < x["price_tnd"] <= cap for x in body["listings"])
    assert titles(body["listings"]) == sorted(n for n, p in PRICES.items() if p and p <= cap)
    # the other rows have no prices: untouched by the budget
    assert len(body["catalog"]) == 10 and len(body["shop"]) == 10


def test_similar_all_prices_turns_the_cap_off(client):
    seed(client)
    headers = sign_up(client)
    client.put("/me", json={"budget_tnd": 100}, headers=headers)
    body = client.get(f"/similar?candidate_id={scan(client, headers)}&k=10&all_prices=true", headers=headers).json()
    assert body["budget_cap"] is None
    assert titles(body["listings"]) == sorted(PRICES)
