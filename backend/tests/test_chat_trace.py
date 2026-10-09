"""'How I answered': the trace of an agent's tool calls (agents/common.py), saved with
each chat answer and returned by /chat and the history (XAI sub-project 3)."""

from app.agents.common import one_line, with_attachments
from tests.conftest import BLUE, RED, sign_up, upload


def test_trace_records_short_arguments_and_one_line_results():
    def explain_outfit(item_ids: list[str], note: str = "") -> dict:
        return {"score": 71.9, "points": {}}

    def broken(item_id: str) -> dict:
        raise ValueError("boom")

    trace = []
    tools = with_attachments({"explain_outfit": explain_outfit, "broken": broken}, None, trace=trace)
    tools["explain_outfit"]([f"id{i}" for i in range(9)], note="x" * 200)
    try:
        tools["broken"]("abc")
    except ValueError:
        pass
    first, second = trace
    assert first["tool"] == "explain_outfit" and first["result"] == "score 71.9"
    assert len(first["args"]["item_ids"]) == 7 and first["args"]["item_ids"][-1] == "… 3 more"
    assert len(first["args"]["note"]) <= 61
    assert second == {"tool": "broken", "args": {"item_id": "abc"}, "result": "failed: ValueError"}


def test_one_line_results():
    assert one_line({"error": "unknown item ids"}) == "error: unknown item ids"
    assert one_line({"verdict": "buy", "good_outfits": 9}) == "verdict buy"
    assert one_line({"before": {}, "after": {}, "change": -4.2}) == "change -4.2"
    assert one_line([1, 2, 3]) == "3 items"
    assert one_line({"a": 1, "b": 2}) == "a, b"


def test_chat_answer_carries_its_trace(client):
    headers = sign_up(client)
    upload(client, headers, RED)
    upload(client, headers, BLUE)
    r = client.post("/chat", json={"message": "what is in my wardrobe?"}, headers=headers).json()
    assert r["routed_by"] in ("llm", "keywords")
    assert r["trace"] == [{"tool": "list_wardrobe", "args": {}, "result": "2 items"}]
    model_turn = client.get("/chat/history", headers=headers).json()[-1]
    assert model_turn["trace"] == r["trace"] and model_turn["routed_by"] == r["routed_by"]
