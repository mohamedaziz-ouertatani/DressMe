"""
POST /chat (step 3c): the whole path with a scripted fake model and the real list_wardrobe tool on the golden wardrobe.
"""

import json

from pymongo import MongoClient

from app.assistant.model import FakeModel, ModelReply, ToolCall
from tests.conftest import RED, TEST_DB, photo, sign_up
from tests.test_golden import WARDROBE, stored


def wardrobe_then(answer):
    return FakeModel([ModelReply(tool_calls=[ToolCall("list_wardrobe", {"limit": 5})]), ModelReply(text=answer)])


def test_a_turn_with_the_golden_wardrobe(make_client, settings):
    model = wardrobe_then("Try {2} with {1}. {99}")
    # the golden fixture builds its own client, so the golden user is seeded here, on a client with the fake model
    client = make_client(chat_model=model)
    user = WARDROBE["user"]
    headers = sign_up(client, user["email"], user["name"], user["gender"])
    db = MongoClient(settings.mongo_url)[TEST_DB]
    user_id = db.users.find_one({"email": user["email"]})["_id"]
    db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"]])
    owned = {d["id"] for d in WARDROBE["items"]}

    r = client.post("/chat", json={"message": "What can I wear with my black jeans?"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "Try {2} with {1}."                     # {99} was invented: removed
    assert body["stop_reason"] == "answered" and body["agent"] == "stylist" and body["model"] == "fake"
    assert sorted(body["pieces"]) == ["1", "2"]
    assert {p["id"] for p in body["pieces"].values()} <= owned       # the user's own items
    assert [(t["tool"], t["ok"], t["n_pieces"]) for t in body["trace"]] == [("list_wardrobe", True, 5)]

    # the model saw coded pieces only: refs, never an id or a photo
    tool_message = json.loads(model.received[1]["messages"][-1]["content"])
    assert tool_message["total"] == len(WARDROBE["items"]) and len(tool_message["pieces"]) == 5
    assert set(tool_message["pieces"][0]) == {"ref", "category", "type", "colour", "pattern", "season"}
    assert not any(item_id in json.dumps(tool_message) for item_id in owned)      # no database id reached the model

    saved = db.chats.find_one({"user_id": user_id})
    assert saved["message"] == "What can I wear with my black jeans?" and saved["answer"] == "Try {2} with {1}."
    assert saved["chat_id"] == body["chat_id"] and saved["unknown_refs"] == [99] and len(saved["item_ids"]) == 2
    event = db.events.find_one({"type": "assistant"})
    assert (event["agent"], event["n_tool_calls"], event["n_unknown_refs"]) == ("stylist", 1, 1)
    assert "message" not in event and "What can I wear" not in json.dumps(event, default=str)


def test_another_user_never_sees_the_first_users_items(make_client):
    model = FakeModel([ModelReply(tool_calls=[ToolCall("list_wardrobe", {})]), ModelReply(text="Nothing to wear: {1}.")])
    client = make_client(chat_model=model)
    first = sign_up(client, "first@example.com", "First")
    client.post("/items", files={"photo": photo(RED)}, headers=first)
    second = sign_up(client, "second@example.com", "Second")

    r = client.post("/chat", json={"message": "What do I own?"}, headers=second)
    assert r.status_code == 200
    tool_message = json.loads(model.received[1]["messages"][-1]["content"])
    assert tool_message == {"pieces": [], "total": 0}                # the first user's red top is not there
    assert r.json()["pieces"] == {} and r.json()["answer"] == "Nothing to wear:."   # {1} was never shown: removed


def test_no_model_answers_503_assistant_unavailable(client):
    headers = sign_up(client)
    r = client.post("/chat", json={"message": "Hello"}, headers=headers)
    assert r.status_code == 503 and r.json()["detail"] == "assistant_unavailable"
    assert client.app.state.db.chats.count_documents({}) == 0       # a failed turn saves nothing


def test_the_request_is_checked(make_client):
    client = make_client(chat_model=FakeModel([ModelReply(text="Hi")]))
    headers = sign_up(client)
    assert client.post("/chat", json={"message": ""}, headers=headers).status_code == 422
    assert client.post("/chat", json={"message": "x" * 1001}, headers=headers).status_code == 422
    unknown = client.post("/chat", json={"message": "Hi", "agent": "wizard"}, headers=headers)
    assert unknown.status_code == 422 and unknown.json()["detail"] == "unknown_agent"
    assert client.post("/chat", json={"message": "Hi"}).status_code in (401, 403)       # a login is needed
    ok = client.post("/chat", json={"message": "Hi", "chat_id": "abc-1"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["chat_id"] == "abc-1"
