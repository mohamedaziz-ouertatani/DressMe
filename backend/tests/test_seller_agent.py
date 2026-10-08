"""The Seller assistant (AGENTS.md): its tools, chat actions, and the plumbing they use."""

from urllib.parse import parse_qs, urlparse

from app.agents import AGENTS, seller
from app.agents.common import with_attachments
from app.agents.router import by_keywords, load_keywords
from tests.conftest import BLUE, RED, fake_vector, photo, sign_up, upload
from tests.test_agents import add_listing, as_request, user_doc


def test_actions_keep_only_sell_form_links():
    def tool():
        return {"a": {"action": {"kind": "sell", "url": "/sell?item=1&price=12"}},
                "b": {"action": {"kind": "sell", "url": "https://example.com/phish"}},
                "c": {"action": {"kind": "pay", "url": "/sell?item=2"}},
                "d": [{"action": {"kind": "sell", "url": "/sell?item=1&price=12"}}]}   # duplicate
    attachments, actions = [], []
    with_attachments({"tool": tool}, attachments, actions)["tool"]()
    assert actions == [{"kind": "sell", "url": "/sell?item=1&price=12"}]


def test_listing_search_can_leave_out_one_seller(client):
    sign_up(client)
    me = user_doc(client)["_id"]
    mine = add_listing(client, source_id="sellers", seller_id=me, price_tnd=10.0)
    other = add_listing(client, price_tnd=40.0)
    index, db = client.app.state.listing_index, client.app.state.db
    ids = [h["id"] for h in index.search(db, fake_vector(1), k=5, category="top")]
    assert set(ids) == {mine, other}
    ids = [h["id"] for h in index.search(db, fake_vector(1), k=5, category="top", exclude_seller=me)]
    assert ids == [other]


# ------------------------------------------------------------------ the agent
def seller_tools(client, email="amira@example.com"):
    return seller.AGENT.bound_tools(as_request(client), user_doc(client, email))


def test_seller_has_its_tools_and_is_registered():
    assert set(seller.tools(None, None)) == {
        "list_wardrobe", "pieces_to_sell", "price_hint", "my_listings", "prepare_sell"}
    assert list(AGENTS) == ["stylist", "shopping", "analyst", "seller"]


def test_pieces_to_sell_unmatched_and_twins(client):
    headers = sign_up(client)
    a = upload(client, headers, RED)
    b = upload(client, headers, RED)          # same photo: b is the twin to sell
    result = seller_tools(client)["pieces_to_sell"]()
    assert {p["id"] for p in result["unmatched"]} == {a["id"], b["id"]}    # tops with no bottom
    assert result["twins"][0]["keep"]["id"] == a["id"]
    assert result["twins"][0]["sell"]["id"] == b["id"]


def test_price_hint_from_an_item_and_from_the_last_scan(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    add_listing(client, price_tnd=50.0)                       # a shop shirt: 50 x 0.3 = 15
    tools = seller_tools(client)
    hint = tools["price_hint"](item_id=top["id"])
    assert hint["based_on"] == "shops" and hint["median"] == 15
    assert "contact" not in hint["examples"][0] and "city" not in hint["examples"][0]
    assert "error" in tools["price_hint"]()                   # no scan yet
    client.post("/analyze", files={"photo": photo(RED)}, headers=headers)
    assert tools["price_hint"]()["median"] == 15


def test_price_hint_skips_own_listings_and_other_users_items(client):
    amira = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    top = upload(client, amira, RED)
    add_listing(client, source_id="sellers", seller_id=user_doc(client)["_id"], price_tnd=10.0)
    assert seller_tools(client)["price_hint"](item_id=top["id"]) == {
        "error": "no similar listings with a price yet"}
    assert "error" in seller_tools(client, "youssef@example.com")["price_hint"](item_id=top["id"])


def test_my_listings_are_private_and_never_show_contact(client):
    headers = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    r = client.post("/listings/sell", files={"photo": photo(BLUE)}, headers=headers,
                    data={"price_tnd": "20", "city": "Sousse", "contact": "+216 00 000 000", "title": "Jeans"})
    assert r.status_code == 201, r.text
    mine = seller_tools(client)["my_listings"]()["listings"]
    assert [(m["title"], m["status"]) for m in mine] == [("Jeans", "pending")]
    assert "contact" not in mine[0] and "city" not in mine[0]
    assert seller_tools(client, "youssef@example.com")["my_listings"]()["listings"] == []


def test_prepare_sell_builds_a_sell_form_link(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    tools = seller_tools(client)
    result = tools["prepare_sell"](price_tnd=15, item_id=top["id"], title="Red T-shirt & co", size="M")
    url = urlparse(result["action"]["url"])
    assert result["action"]["kind"] == "sell" and url.path == "/sell"
    assert parse_qs(url.query) == {"item": [top["id"]], "price": ["15"], "title": ["Red T-shirt & co"],
                                   "size": ["M"]}
    assert "error" in tools["prepare_sell"](price_tnd=15)               # no scan yet
    assert "error" in tools["prepare_sell"](price_tnd=0, item_id=top["id"])
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    url = tools["prepare_sell"](price_tnd=12.5)["action"]["url"]
    assert parse_qs(urlparse(url).query) == {"candidate": [cand["id"]], "price": ["12.5"]}


def test_prepare_sell_ignores_other_users_items(client):
    amira = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    top = upload(client, amira, RED)
    assert "error" in seller_tools(client, "youssef@example.com")["prepare_sell"](
        price_tnd=10, item_id=top["id"])


def test_sell_keywords_route_to_the_seller():
    keywords = load_keywords()
    assert by_keywords("I want to sell my jacket", keywords) == "seller"
    assert by_keywords("je veux vendre ce jean", keywords) == "seller"
