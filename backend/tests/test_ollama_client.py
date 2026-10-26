"""
The Ollama client (step 3d), with a fake HTTP transport: no Ollama needed. Also GET /assistant/status and /chat
when Ollama cannot be reached.
"""

import json

import httpx
import pytest

from app.assistant import default_registry
from app.assistant.agents import load_agents
from app.assistant.model import ModelUnavailable, ToolCall
from app.assistant.ollama import OllamaClient
from app.config import ROOT
from tests.conftest import sign_up

SETTINGS = load_agents(ROOT / "mappings" / "agents.yaml", default_registry().names()).model
NOWHERE = "http://127.0.0.1:9"          # nothing listens there: connection refused
TOOLS = [{"type": "function", "function": {"name": "list_wardrobe", "description": "List.", "parameters": {}}}]


def client_answering(answer, sent=None, status=200):
    """An OllamaClient whose HTTP calls get `answer` (a dict, or an exception to raise); `sent` collects the requests."""
    def handle(request):
        if sent is not None:
            sent.append((request.url.path, json.loads(request.content)))
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(status, json=answer)
    return OllamaClient("http://ollama.test", "qwen3.5:4b", SETTINGS, transport=httpx.MockTransport(handle))


def reply(content="", tool_calls=None):
    return {"model": "qwen3.5:4b", "message": {"role": "assistant", "content": content,
                                               **({"tool_calls": tool_calls} if tool_calls else {})}, "done": True}


def test_the_request_has_the_tools_think_off_and_the_options():
    sent = []
    messages = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "list_wardrobe", "arguments": {}}}]},
                {"role": "tool", "name": "list_wardrobe", "content": "{\"pieces\": []}"}]
    client_answering(reply("Hello"), sent).chat(messages, TOOLS, max_tokens=300)
    path, body = sent[0]
    assert path == "/api/chat"
    assert (body["model"], body["stream"], body["think"], body["keep_alive"]) == ("qwen3.5:4b", False, False, "10m")
    assert body["tools"] == TOOLS
    assert body["options"] == {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5,
                               "num_ctx": 8192, "num_predict": 300}
    assert body["messages"][3] == {"role": "tool", "tool_name": "list_wardrobe", "content": "{\"pieces\": []}"}
    assert body["messages"][:3] == messages[:3]


def test_no_tools_means_no_tools_field():
    sent = []
    client_answering(reply("Hello"), sent).chat([{"role": "user", "content": "Hi"}], [], max_tokens=50)
    assert "tools" not in sent[0][1]


def test_tool_calls_become_tool_calls():
    calls = [{"id": "call_1", "function": {"index": 0, "name": "list_wardrobe", "arguments": {"category": "bottom"}}},
             {"function": {"name": "get_weather", "arguments": "{}"}}]        # arguments as text are read too
    answer = client_answering(reply("", calls)).chat([{"role": "user", "content": "Hi"}], TOOLS, 100)
    assert answer.tool_calls == [ToolCall("list_wardrobe", {"category": "bottom"}), ToolCall("get_weather", {})]
    assert answer.text is None and answer.thinking_stripped is False


def test_a_think_block_is_stripped_and_flagged():
    answer = client_answering(reply("<think>The user wants...</think>\n\nTry {1}.")).chat(
        [{"role": "user", "content": "Hi"}], [], 100)
    assert answer.text == "Try {1}." and answer.thinking_stripped is True


@pytest.mark.parametrize("client", [
    OllamaClient(NOWHERE, "qwen3.5:4b", SETTINGS),                                    # connection refused
    client_answering(httpx.ReadTimeout("too slow")),                                 # timeout
    client_answering({"error": "model 'qwen3.5:4b' not found"}, status=404),        # model not pulled
    client_answering({"error": "boom"}, status=500),
], ids=["refused", "timeout", "not-found", "server-error"])
def test_every_failure_is_model_unavailable(client):
    with pytest.raises(ModelUnavailable):
        client.chat([{"role": "user", "content": "Hi"}], [], 50)


def test_available_asks_api_show_once_a_minute():
    sent = []
    client = client_answering({"capabilities": ["completion", "tools"]}, sent)
    assert client.available() is True and client.available() is True
    assert [path for path, _ in sent] == ["/api/show"]                 # the second answer came from the cache
    assert OllamaClient(NOWHERE, "qwen3.5:4b", SETTINGS).available() is False


def test_status_and_chat_when_ollama_cannot_be_reached(make_client):
    client = make_client(chat_model=OllamaClient(NOWHERE, "qwen3.5:4b", SETTINGS))
    headers = sign_up(client)
    assert client.get("/assistant/status").status_code in (401, 403)          # a login is needed
    r = client.get("/assistant/status", headers=headers)
    assert r.status_code == 200 and r.json() == {"available": False, "model": "qwen3.5:4b"}
    chat = client.post("/chat", json={"message": "What should I wear today?"}, headers=headers)
    assert chat.status_code == 503 and chat.json()["detail"] == "assistant_unavailable"
    assert client.get("/health").status_code == 200                          # the app keeps running
