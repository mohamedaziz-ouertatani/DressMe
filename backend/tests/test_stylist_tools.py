"""
The Stylist's real tools (step 3d), each called by a scripted fake model through POST /chat on the golden wardrobe.
Each tool reuses a screen's function, so its answer is compared with that screen's route; and what the model reads
never holds a database id (only refs) or free text.
"""

import json
import re

import pytest
from pymongo import MongoClient

from app.assistant.model import FakeModel, ModelReply, ToolCall
from tests.conftest import TEST_DB, sign_up
from tests.test_golden import WARDROBE, stored

OWNED = {d["id"] for d in WARDROBE["items"]}
ALL_REFS = " ".join(f"{{{n}}}" for n in range(1, 40))      # an answer naming every ref, so `pieces` maps them all
OBJECT_ID = re.compile(r"\b[0-9a-f]{24}\b")
BLACK_SKIRT = ("list_wardrobe", {"category": "bottom", "colour": "black"})       # the golden wardrobe has one: ref 1


@pytest.fixture
def golden_chat(make_client, settings):
    """ask(*calls) runs ONE turn in which the fake model makes each (tool, arguments) call in turn, then names every
    ref. Returns (what the model read from the LAST tool, {ref: item id})."""
    model = FakeModel([])
    client = make_client(chat_model=model)
    user = WARDROBE["user"]
    headers = sign_up(client, user["email"], user["name"], user["gender"])
    db = MongoClient(settings.mongo_url)[TEST_DB]
    user_id = db.users.find_one({"email": user["email"]})["_id"]
    db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"]])

    def ask(*calls):
        model.script += [ModelReply(tool_calls=[ToolCall(name, args)]) for name, args in calls]
        model.script.append(ModelReply(text=ALL_REFS))
        r = client.post("/chat", json={"message": "help"}, headers=headers)
        assert r.status_code == 200, r.text
        for message in model.received[-1]["messages"]:
            if message["role"] == "tool":
                assert not OBJECT_ID.search(message["content"]), "a database id reached the model"
        refs = {int(n): p["id"] for n, p in r.json()["pieces"].items()}
        assert set(refs.values()) <= OWNED                           # only the user's own pieces
        return json.loads(model.received[-1]["messages"][-1]["content"]), refs

    ask.client, ask.headers = client, headers
    return ask


def ids_of(outfit, refs):
    return [refs[n] for n in outfit["pieces"]]


def test_search_wardrobe_matches_the_search_route(golden_chat):
    seen, refs = golden_chat(("search_wardrobe", {"query": "black skirt"}))
    route = golden_chat.client.post("/search", data={"text": "black skirt"}, headers=golden_chat.headers).json()
    assert [refs[p["ref"]] for p in seen["pieces"]] == [r["item"]["id"] for r in route["results"]]
    assert seen["nothing_close"] == route["nothing_close"]
    assert set(seen["pieces"][0]) == {"ref", "category", "type", "colour", "close"}


def test_search_wardrobe_says_when_there_are_no_words(golden_chat):
    seen, _ = golden_chat(("search_wardrobe", {"query": ",,"}))
    assert seen["error"] == "no_words"


def test_get_weather_uses_the_default_city(golden_chat):
    seen, _ = golden_chat(("get_weather", {}))
    assert seen == {"location": "default city", "temp_c": 26, "condition": "cloudy", "rain": False, "season": "summer"}


def test_suggest_outfits_gives_the_same_outfits_as_the_dress_page(golden_chat):
    seen, refs = golden_chat(("suggest_outfits", {"occasion": "work"}))
    page = golden_chat.client.get("/outfits/today", params={"occasion": "work"}, headers=golden_chat.headers).json()
    assert [ids_of(o, refs) for o in seen["outfits"]] == [[i["id"] for i in o["items"]] for o in page["outfits"]]
    assert [o["score"] for o in seen["outfits"]] == [round(o["score"]) for o in page["outfits"]]
    first = seen["outfits"][0]
    assert set(first) == {"pieces", "label", "score", "complete", "missing", "reasons"}
    assert isinstance(first["score"], int) and all(r[0] in "+-" for r in first["reasons"])


def test_build_outfit_gives_the_same_outfits_as_the_build_page(golden_chat):
    seen, refs = golden_chat(BLACK_SKIRT, ("build_outfit", {"pieces": [1]}))
    page = golden_chat.client.post("/outfits/build", json={"item_ids": [refs[1]]}, headers=golden_chat.headers).json()
    assert [ids_of(o, refs) for o in seen["outfits"]] == [[i["id"] for i in o["items"]] for o in page["outfits"]]
    assert len(seen["outfits"]) == len(page["outfits"]) > 0


def test_score_outfit_gives_the_score_of_the_score_route(golden_chat):
    seen, refs = golden_chat(BLACK_SKIRT, ("list_wardrobe", {"category": "top"}), ("score_outfit", {"pieces": [1, 2]}))
    route = golden_chat.client.post("/outfits/score", json={"item_ids": [refs[1], refs[2]]},
                                    headers=golden_chat.headers).json()
    assert seen["score"] == round(route["score"])
    assert seen["parts"] == {k: (None if v is None else round(v * 100)) for k, v in route["parts"].items()}
    assert (seen["complete"], seen["missing"]) == (route["complete"], route["missing"])


def test_a_ref_lives_for_one_turn_only(golden_chat):
    golden_chat(BLACK_SKIRT)                                  # ref 1 existed in that turn...
    seen, _ = golden_chat(("build_outfit", {"pieces": [1]}))  # ...not in this one
    assert seen["error"] == "unknown_piece"


def test_pieces_that_clash_are_an_error_the_model_can_read(golden_chat):
    seen, _ = golden_chat(BLACK_SKIRT, ("score_outfit", {"pieces": [1, 1]}))
    assert seen["error"] == "pieces_clash"
