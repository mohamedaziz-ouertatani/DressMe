from types import SimpleNamespace

import pytest

from app import chat_engine
from app.chat_engine import ChatBusy, ChatQuota, GeminiEngine
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


class GeminiError(Exception):
    """Like google.genai.errors.APIError: carries the HTTP code."""

    def __init__(self, code):
        super().__init__(f"{code} error")
        self.code = code


class FlakyClient:
    """A Gemini client that fails with the given codes, then answers."""

    def __init__(self, *codes):
        self.codes, self.calls = list(codes), 0
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls += 1
        if self.codes:
            raise GeminiError(self.codes.pop(0))
        return SimpleNamespace(text=" Wear the jeans. ")


def engine_with(client, settings):
    engine = GeminiEngine(settings)
    engine._client = client
    engine._get_client = lambda: client
    return engine


def test_gemini_overload_is_retried(settings, monkeypatch):
    monkeypatch.setattr(chat_engine, "RETRY_WAITS", [0, 0])
    client = FlakyClient(503, 500)
    answer, used = engine_with(client, settings).reply("system", [], "hi", {})
    assert answer == "Wear the jeans." and client.calls == 3


def test_gemini_still_down_after_retries(settings, monkeypatch):
    monkeypatch.setattr(chat_engine, "RETRY_WAITS", [0, 0])
    client = FlakyClient(503, 503, 503)
    with pytest.raises(ChatBusy):
        engine_with(client, settings).reply("system", [], "hi", {})
    assert client.calls == 3


def test_gemini_wrong_model_is_not_retried(settings, monkeypatch):
    monkeypatch.setattr(chat_engine, "RETRY_WAITS", [0, 0])
    client = FlakyClient(404)
    with pytest.raises(ChatBusy):
        engine_with(client, settings).reply("system", [], "hi", {})
    assert client.calls == 1


def test_chat_busy_answers_502(make_client, settings, monkeypatch):
    monkeypatch.setattr(chat_engine, "RETRY_WAITS", [0, 0])
    client = make_client(chat_engine=engine_with(FlakyClient(503, 503, 503), settings))
    r = client.post("/chat", json={"message": "hello"}, headers=sign_up(client))
    assert r.status_code == 502 and "503" in r.json()["detail"]


def test_used_up_quota_is_not_retried(make_client, settings, monkeypatch):
    monkeypatch.setattr(chat_engine, "RETRY_WAITS", [0, 0])
    flaky = FlakyClient(429)
    with pytest.raises(ChatQuota):
        engine_with(flaky, settings).reply("system", [], "hi", {})
    assert flaky.calls == 1
    client = make_client(chat_engine=engine_with(FlakyClient(429), settings))
    r = client.post("/chat", json={"message": "hello"}, headers=sign_up(client))
    assert r.status_code == 429


# ------------------------------------------------------------------ local model (Ollama)
import copy  # noqa: E402

from app.chat_engine import ChatUnavailable, OllamaEngine, make_engine, tool_schema  # noqa: E402


def test_tool_schema_reads_signature_and_docstring():
    def score_outfit(item_ids: list[str], n: int = 3) -> dict:
        """Score an
        outfit."""
    s = tool_schema(score_outfit)["function"]
    assert s["name"] == "score_outfit" and s["description"] == "Score an outfit."
    assert s["parameters"]["properties"] == {"item_ids": {"type": "array", "items": {"type": "string"}},
                                             "n": {"type": "integer"}}
    assert s["parameters"]["required"] == ["item_ids"]


class FakeOllama:
    """Answers /api/chat like Ollama: first a tool call, then text. Keeps the requests."""

    def __init__(self, *answers, status=200):
        self.answers, self.status, self.requests = list(answers), status, []

    def post(self, url, json, timeout):
        self.requests.append(copy.deepcopy(json))   # httpx sends a copy too
        return SimpleNamespace(status_code=self.status, text="error",
                               json=lambda: {"message": self.answers.pop(0)})


def ollama_engine(settings, monkeypatch, fake):
    import httpx
    monkeypatch.setattr(httpx, "post", fake.post)
    settings.chat_engine = "ollama"
    return make_engine(settings)


def test_ollama_runs_the_tools_it_asks_for(settings, monkeypatch):
    fake = FakeOllama(
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "list_wardrobe", "arguments": {"category": "shoes"}}}]},
        {"role": "assistant", "content": " You have black sneakers. "})
    engine = ollama_engine(settings, monkeypatch, fake)
    assert isinstance(engine, OllamaEngine)
    seen = []

    def list_wardrobe(category: str = "") -> list[dict]:
        """List the clothes."""
        seen.append(category)
        return [{"id": "1", "category": "shoes", "colour": "black"}]

    answer, used = engine.reply("system", [{"role": "model", "text": "hello"}], "my shoes?",
                                {"list_wardrobe": list_wardrobe})
    assert answer == "You have black sneakers." and used == ["list_wardrobe"] and seen == ["shoes"]
    first, second = fake.requests
    assert [m["role"] for m in first["messages"]] == ["system", "assistant", "user"]
    assert first["tools"][0]["function"]["name"] == "list_wardrobe"
    assert second["messages"][-1]["role"] == "tool" and "black" in second["messages"][-1]["content"]


def test_ollama_tool_errors_go_back_to_the_model(settings, monkeypatch):
    fake = FakeOllama(
        {"content": "", "tool_calls": [{"function": {"name": "score_outfit", "arguments": "{\"wrong\": 1}"}}]},
        {"content": "", "tool_calls": [{"function": {"name": "no_such_tool", "arguments": {}}}]},
        {"content": "Sorry, try again."})

    def score_outfit(item_ids: list[str]) -> dict:
        """Score."""
        return {}

    answer, used = ollama_engine(settings, monkeypatch, fake).reply(
        "system", [], "score", {"score_outfit": score_outfit})
    assert answer == "Sorry, try again." and used == ["score_outfit", "no_such_tool"]
    assert "TypeError" in fake.requests[1]["messages"][-1]["content"]
    assert "unknown tool" in fake.requests[2]["messages"][-1]["content"]


def test_ollama_missing_model_or_server(settings, monkeypatch):
    with pytest.raises(ChatUnavailable):
        ollama_engine(settings, monkeypatch, FakeOllama(status=404)).reply("s", [], "hi", {})
    with pytest.raises(ChatBusy):
        ollama_engine(settings, monkeypatch, FakeOllama(status=500)).reply("s", [], "hi", {})
    import httpx

    def refuse(*args, **kwargs):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx, "post", refuse)
    with pytest.raises(ChatUnavailable):
        OllamaEngine(settings).reply("s", [], "hi", {})
