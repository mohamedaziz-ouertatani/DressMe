from app.chat_engine import GeminiEngine
from tests.conftest import BLACK, BLUE, RED, photo, sign_up, upload


def test_chat_uses_the_real_wardrobe(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE, BLACK):
        upload(client, headers, rgb)
    r = client.post("/chat", json={"message": "what is in my wardrobe?"}, headers=headers)
    assert r.status_code == 200
    assert r.json() == {"reply": "You have 3 items.", "tools_used": ["list_wardrobe"]}
    r = client.post("/chat", json={"message": "suggest an outfit"}, headers=headers)
    assert r.json()["tools_used"] == ["suggest_outfits"]


def test_chat_buy_advice_uses_last_scan(client):
    headers = sign_up(client)
    r = client.post("/chat", json={"message": "should I buy it?"}, headers=headers)
    assert "no analysed photo" in r.json()["reply"]
    upload(client, headers, BLUE)
    client.post("/analyze", files={"photo": photo(RED)}, headers=headers)
    r = client.post("/chat", json={"message": "should I buy it?"}, headers=headers)
    assert r.json()["reply"].split()[-1] in ("buy", "think", "skip")


def test_history_is_kept_in_order_and_private(client):
    amira = sign_up(client)
    youssef = sign_up(client, "youssef@example.com", "Youssef")
    client.post("/chat", json={"message": "hi"}, headers=amira)
    r = client.post("/chat", json={"message": "hi again"}, headers=amira)
    assert r.json()["reply"].startswith("(history 2)")    # the model saw the first exchange
    history = client.get("/chat/history", headers=amira).json()
    assert [h["role"] for h in history] == ["user", "model", "user", "model"]
    assert history[0]["text"] == "hi"
    assert client.get("/chat/history", headers=youssef).json() == []
    assert client.delete("/chat/history", headers=amira).status_code == 204
    assert client.get("/chat/history", headers=amira).json() == []


def test_chat_without_api_key(make_client, settings):
    client = make_client(chat_engine=GeminiEngine(settings))     # settings has no key
    headers = sign_up(client)
    r = client.post("/chat", json={"message": "hello"}, headers=headers)
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]
