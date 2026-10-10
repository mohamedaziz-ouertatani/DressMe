"""The three agents' tools and the router (see AGENTS.md). Tools are called
directly, like the chat engine would, on a wardrobe built through the API."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.agents import AGENTS, DEFAULT_AGENT, analyst, shopping, stylist
from app.agents.router import by_keywords, load_keywords, route, router_prompt
from app.chat_engine import ChatBusy, ChatQuota
from app.db import vector_to_bson
from app.listings import listing_query
from app.routers.insights import wardrobe_counts
from tests.conftest import BLACK, BLUE, RED, FakeChatEngine, fake_vector, photo, sign_up, upload


def as_request(client):
    """What a tool needs from the request: the app (database, models, settings)."""
    return SimpleNamespace(app=client.app)


def user_doc(client, email="amira@example.com"):
    return client.app.state.db.users.find_one({"email": email})


def stylist_tools(client, email="amira@example.com"):
    return stylist.AGENT.bound_tools(as_request(client), user_doc(client, email))


# ------------------------------------------------------------------ stylist
def test_stylist_has_its_tools():
    assert set(stylist.tools(None, None)) == {
        "list_wardrobe", "suggest_outfits", "score_outfit", "complete_outfit", "get_weather"}


def test_complete_outfit_adds_pieces_from_the_wardrobe(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    upload(client, headers, BLUE)
    upload(client, headers, BLACK)
    result = stylist_tools(client)["complete_outfit"]([top["id"]], k=2)
    assert 1 <= len(result["completions"]) <= 2
    first = result["completions"][0]
    assert 0 <= first["score"] <= 100
    assert first["added"]["id"] != top["id"]
    assert top["id"] in [i["id"] for i in first["items"]]


def test_complete_outfit_ignores_other_users_items(client):
    amira = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    top = upload(client, amira, RED)
    result = stylist_tools(client, "youssef@example.com")["complete_outfit"]([top["id"]])
    assert result == {"error": "none of these ids are in the wardrobe"}


def test_get_weather_uses_the_default_place(client):
    sign_up(client)
    weather = stylist_tools(client)["get_weather"]()
    assert weather["season"] in ("summer", "winter", "mid-season")
    assert weather["place"] == client.app.state.settings.weather_place


def test_get_weather_switched_off(client):
    sign_up(client)
    client.app.state.weather = None
    assert stylist_tools(client)["get_weather"]() == {"error": "weather unavailable"}


def test_stylist_prompt_keeps_the_user_rules(client):
    sign_up(client)
    prompt = stylist.AGENT.prompt(user_doc(client))
    assert "Never invent items" in prompt
    assert "Shopping advisor" in prompt          # it knows what the other agents do


# ------------------------------------------------------------------ shared helpers
def test_listing_query_only_active_in_stock_by_default():
    assert listing_query() == {"status": "active", "in_stock": True}
    assert listing_query(category="top", colour="black", max_price=50, in_stock=False) == {
        "status": "active", "category": "top", "colour": "black", "price_tnd": {"$lte": 50}}


def test_wardrobe_counts_matches_insights(client):
    headers = sign_up(client)
    for rgb in (RED, RED, BLUE):
        upload(client, headers, rgb)
    docs = list(client.app.state.db.items.find({}))
    counts = wardrobe_counts(docs)
    insights = client.get("/insights", headers=headers).json()
    for key in ("total", "categories", "colours", "patterns", "to_confirm"):
        assert counts[key] == insights[key]


# ------------------------------------------------------------------ shopping advisor
def add_listing(client, **fields):
    """A listing document like the collector or a seller would save."""
    db = client.app.state.db
    doc = {"source_id": "exist", "external_id": f"p{db.listings.count_documents({})}", "title": "Shirt", "brand": "Exist", "status": "active",
           "in_stock": True, "category": "top", "sub_category": "shirt", "pattern": "solid",
           "colour": "black", "price_tnd": 49.0, "created_at": datetime.now(timezone.utc),
           "gender": "unisex", "vector": vector_to_bson(fake_vector(1)), **fields}
    return str(db.listings.insert_one(doc).inserted_id)


def shopping_tools(client, email="amira@example.com"):
    return shopping.AGENT.bound_tools(as_request(client), user_doc(client, email))


def test_shopping_has_its_tools():
    assert set(shopping.tools(None, None)) == {
        "list_wardrobe", "buy_advice_last_scan", "search_listings", "find_similar"}


def test_search_listings_shows_only_what_people_can_buy(client):
    sign_up(client)
    ok = add_listing(client, title="Black shirt")
    add_listing(client, title="Pending", source_id="sellers", status="pending")
    add_listing(client, title="Gone", status="gone")
    add_listing(client, title="Sold out", in_stock=False)
    add_listing(client, title="Too dear", price_tnd=300.0)
    result = shopping_tools(client)["search_listings"](category="top", max_price=100)
    assert [x["id"] for x in result["listings"]] == [ok]
    assert result["total"] == 1
    assert result["listings"][0]["image_url"] == f"/listings/{ok}/image"
    assert "contact" not in result["listings"][0]       # a seller's contact never goes to the model


def test_find_similar_from_an_item_and_from_the_last_scan(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    add_listing(client)
    tools = shopping_tools(client)
    result = tools["find_similar"](item_id=top["id"], n=3)
    assert len(result["shop"]) == 3 and result["shop"][0]["image_url"].startswith("/catalog/hm_")
    assert len(result["listings"]) == 1
    assert "no such item" in tools["find_similar"]()["error"]      # no scan yet
    client.post("/analyze", files={"photo": photo(BLUE)}, headers=headers)
    assert "shop" in tools["find_similar"]()


def test_find_similar_ignores_other_users_items(client):
    amira = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    top = upload(client, amira, RED)
    result = shopping_tools(client, "youssef@example.com")["find_similar"](item_id=top["id"])
    assert "error" in result


# ------------------------------------------------------------------ wardrobe analyst
def analyst_tools(client, email="amira@example.com"):
    return analyst.AGENT.bound_tools(as_request(client), user_doc(client, email))


def test_analyst_has_its_tools():
    assert set(analyst.tools(None, None)) == {
        "list_wardrobe", "wardrobe_insights", "wardrobe_stats", "find_near_twins"}


def test_wardrobe_insights_says_what_is_missing(client):
    headers = sign_up(client)
    upload(client, headers, RED)
    upload(client, headers, BLUE)
    facts = analyst_tools(client)["wardrobe_insights"]()
    assert "shoes" in facts["missing"]
    assert facts["good_outfits"] >= 0
    assert set(facts) >= {"versatile", "unmatched", "unmatched_count", "new_pairs", "hidden_by_filters"}


def test_wardrobe_stats_and_twins(client):
    headers = sign_up(client)
    a = upload(client, headers, RED)
    b = upload(client, headers, RED)             # same photo: a near twin
    upload(client, headers, BLUE)
    tools = analyst_tools(client)
    assert tools["wardrobe_stats"]()["total"] == 3
    twins = tools["find_near_twins"]()["twins"]
    assert {i["id"] for i in twins[0]["items"]} == {a["id"], b["id"]}


def test_analyst_sees_only_its_user(client):
    amira = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    upload(client, amira, RED)
    assert analyst_tools(client, "youssef@example.com")["wardrobe_stats"]()["total"] == 0


# ------------------------------------------------------------------ registry and router
def test_every_agent_has_tools():
    assert list(AGENTS) == ["stylist", "shopping", "analyst", "seller", "explainer"]
    assert DEFAULT_AGENT == "stylist"
    for agent in AGENTS.values():
        assert len(agent.tools(None, None)) >= 3


def test_keyword_table_names_only_known_agents():
    rows = load_keywords()
    assert {agent for agent, _ in rows} == set(AGENTS)


def test_keyword_table_rejects_an_unknown_agent(tmp_path):
    bad = tmp_path / "agent_keywords.csv"
    bad.write_text("agent,language,keyword,note\ntailor,en,sew,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tailor"):
        load_keywords(bad)


@pytest.mark.parametrize("message, agent", [
    ("Should I buy this jacket?", "shopping"),
    ("Est-ce que je dois l'acheter ?", "shopping"),
    ("What should I wear today?", "stylist"),
    ("Qu'est-ce qui manque dans mes vêtements ?", "analyst"),
    ("hello", "stylist"),                                      # no keyword: the default
])
def test_keywords(message, agent):
    assert by_keywords(message, load_keywords()) == agent


def test_route_uses_the_llm_label():
    engine = FakeChatEngine(label=" Shopping.\n")
    assert route(engine, "anything") == ("shopping", "llm")


@pytest.mark.parametrize("error", [ChatBusy("down"), ChatQuota("quota")])
def test_route_falls_back_to_keywords_when_the_llm_fails(error):
    class Failing(FakeChatEngine):
        def classify(self, system, message):
            raise error
    assert route(Failing(), "should I buy it?") == ("shopping", "keywords")


def test_route_ignores_an_unknown_label():
    assert route(FakeChatEngine(label="tailor"), "what is missing?") == ("analyst", "keywords")


def test_keywords_mode_never_calls_the_llm():
    engine = FakeChatEngine(label="analyst")
    assert route(engine, "what should I wear?", mode="keywords") == ("stylist", "keywords")
    assert engine.classify_calls == 0


def test_router_prompt_lists_every_agent():
    prompt = router_prompt()
    assert all(name in prompt for name in AGENTS)


def test_listings_carry_the_shop_display_name():
    """The sources table's shop_name ("Hamadi Abid"), not the slug the connectors store
    as brand ("hamadiabid"): the chat showed the slug to users (2026-10-10)."""
    from app.listings import listing_out
    doc = {"_id": "x", "source_id": "hamadiabid_tn", "brand": "hamadiabid", "title": "Ceinture Homme"}
    assert listing_out(doc)["shop_name"] == "Hamadi Abid"
    assert listing_out({**doc, "source_id": "exist_tn", "brand": "exist"})["shop_name"] == "Exist"
    assert listing_out({**doc, "source_id": "unknown_src", "brand": "acme"})["shop_name"] == "acme"
    assert listing_out({**doc, "source_id": "sellers", "brand": ""})["shop_name"] == ""


def test_same_looking_listings_are_grouped_in_chat_answers(client):
    """Shops give many products one title ("Ceinture Homme"): three identical lines told the
    user nothing. The tool keeps one per shop + title + price + colour, with how many there are."""
    sign_up(client)
    for colour in ("black", "black", ""):        # our colour guess can be empty: the shop's name decides
        add_listing(client, source_id="hamadiabid_tn", brand="hamadiabid", title="Ceinture Homme",
                    category="accessory", sub_category="belt", colour=colour, shop_colour="BLACK",
                    price_tnd=49.99)
    add_listing(client, title="Shirt", colour="white")
    found = shopping_tools(client)["search_listings"]()
    belts = [x for x in found["listings"] if x["title"] == "Ceinture Homme"]
    assert len(belts) == 1 and belts[0]["same_kind"] == 3 and belts[0]["brand"] == "Hamadi Abid"
    assert [x for x in found["listings"] if x["title"] == "Shirt"][0].get("same_kind", 1) == 1
