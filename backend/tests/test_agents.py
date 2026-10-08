"""The three agents' tools and the router (see AGENTS.md). Tools are called
directly, like the chat engine would, on a wardrobe built through the API."""

from types import SimpleNamespace

from app.agents import stylist
from tests.conftest import BLACK, BLUE, RED, sign_up, upload


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
