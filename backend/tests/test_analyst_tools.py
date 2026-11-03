"""
The wardrobe analyst's tools (step 3e.2), called by a scripted fake model through POST /chat on the golden wardrobe:
they answer with refs and never a database id, their lists are short, and the numbers match the /insights route.
"""

import json
import re

import pytest
from pymongo import MongoClient

from app.assistant.model import FakeModel, ModelReply, ToolCall
from tests.conftest import TEST_DB, sign_up
from tests.test_golden import WARDROBE, stored

OWNED = {d["id"] for d in WARDROBE["items"]}
OBJECT_ID = re.compile(r"\b[0-9a-f]{24}\b")
MAX_CHARS = 2500                      # about 800 tokens: a tool result must stay small next to num_ctx 8192
ALL_REFS = " ".join(f"{{{n}}}" for n in range(1, 40))


@pytest.fixture
def analyst(make_client, settings):
    """ask(tool) = one turn of the wardrobe_analyst in which the fake model calls `tool`, then names every ref.
    Returns (what the model read, {ref: item id})."""
    model = FakeModel([])
    client = make_client(chat_model=model)
    user = WARDROBE["user"]
    headers = sign_up(client, user["email"], user["name"], user["gender"])
    db = MongoClient(settings.mongo_url)[TEST_DB]
    user_id = db.users.find_one({"email": user["email"]})["_id"]
    db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"]])

    def ask(tool):
        model.script += [ModelReply(tool_calls=[ToolCall(tool, {})]), ModelReply(text=ALL_REFS)]
        r = client.post("/chat", json={"message": "help", "agent": "wardrobe_analyst"}, headers=headers)
        assert r.status_code == 200, r.text
        read = model.received[-1]["messages"][-1]["content"]
        assert not OBJECT_ID.search(read), "a database id reached the model"
        assert len(read) <= MAX_CHARS, f"{len(read)} characters"
        refs = {int(n): p["id"] for n, p in r.json()["pieces"].items()}
        assert set(refs.values()) <= OWNED
        return json.loads(read), refs

    ask.client, ask.headers = client, headers
    return ask


def test_wardrobe_insights_is_short_and_matches_the_insights_route(analyst):
    seen, refs = analyst("wardrobe_insights")
    route = analyst.client.get("/insights", headers=analyst.headers).json()
    assert seen["total"] == route["total"] == len(WARDROBE["items"])
    assert seen["good_outfits"] == route["outfits"]["good"] and seen["missing"] == route["missing"][:5]
    assert seen["categories"] == route["categories"][:5] and seen["top_colours"] == route["colours"][:5]
    for name in ("categories", "top_colours", "patterns", "missing", "most_used", "never_used", "twins"):
        assert len(seen[name]) <= 5
    for p in seen["most_used"] + seen["never_used"]:                 # a piece is a ref and two words, no id
        assert set(p) <= {"ref", "type", "colour", "outfits"} and p["ref"] in refs
    assert [refs[r] for t in seen["twins"] for r in t["pieces"]] == \
        [i["id"] for t in route["twins"][:3] for i in t["items"]]


def test_near_twins_lists_pairs_of_refs(analyst):
    seen, refs = analyst("near_twins")
    assert seen["total"] >= len(seen["twins"]) and len(seen["twins"]) <= 5
    for pair in seen["twins"]:
        a, b = pair["pieces"]
        assert a != b and a in refs and b in refs and 0 < pair["similarity"] <= 1
    similarities = [t["similarity"] for t in seen["twins"]]
    assert similarities == sorted(similarities, reverse=True)       # most alike first


def test_an_empty_wardrobe_gives_zero_not_an_error(make_client):
    model = FakeModel([ModelReply(tool_calls=[ToolCall("wardrobe_insights", {})]), ModelReply(text="Nothing yet.")])
    client = make_client(chat_model=model)
    r = client.post("/chat", json={"message": "help", "agent": "wardrobe_analyst"}, headers=sign_up(client))
    assert r.status_code == 200, r.text
    seen = json.loads(model.received[-1]["messages"][-1]["content"])
    assert seen["total"] == 0 and seen["good_outfits"] == 0 and seen["twins"] == [] and seen["neutral_share"] is None


def test_the_stylist_cannot_use_the_analysts_tools(make_client):
    model = FakeModel([ModelReply(tool_calls=[ToolCall("near_twins", {})]), ModelReply(text="Sorry.")])
    client = make_client(chat_model=model)
    r = client.post("/chat", json={"message": "help", "agent": "stylist"}, headers=sign_up(client))
    assert r.status_code == 200
    assert json.loads(model.received[-1]["messages"][-1]["content"])["error"] == "unknown_tool"
