"""
The router (step 3e.1): who answers a message. A button choice skips it; otherwise one model call (no tools,
temperature 0, a few tokens) names the agent; a bad answer or a model that fails falls back to the keywords, then to
the first agent. And the general agent, which has no tools, runs a whole turn.
"""

from app.assistant import default_registry
from app.assistant.agents import load_agents
from app.assistant.model import FakeModel, ModelReply, ModelUnavailable
from app.assistant.routing import agent_named, by_keywords, choose_agent
from app.config import ROOT
from tests.conftest import sign_up

AGENTS = load_agents(ROOT / "mappings" / "agents.yaml", default_registry().names())


def say(text):
    return ModelReply(text=text)


class FailsOnce(FakeModel):
    """The first call (the router's) says the model is down; the next ones are scripted."""

    def chat(self, messages, tools, max_tokens, temperature=None):
        if not self.received:
            self.received.append({"messages": messages, "tools": tools, "max_tokens": max_tokens,
                                  "temperature": temperature})
            raise ModelUnavailable("down for one call")
        return super().chat(messages, tools, max_tokens, temperature)


def chat(model, message, make_client, **body):
    client = make_client(chat_model=model)
    r = client.post("/chat", json={"message": message, **body}, headers=sign_up(client))
    assert r.status_code == 200, r.text
    return r.json()


def route_of(body):
    return [line for line in body["trace"] if "router" in line][0]


# ---------------------------------------------------------------- the pieces
def test_the_real_file_has_a_general_agent_without_tools():
    general = AGENTS.agents["general"]
    assert general.tools == [] and general.description and list(AGENTS.agents)[0] == "stylist"
    assert (AGENTS.router.temperature, AGENTS.router.max_tokens) == (0, 10)


def test_a_reply_counts_only_when_it_is_exactly_an_agent_name():
    names = AGENTS.agents
    assert agent_named("general", names) == "general"
    assert agent_named(" Stylist.\n", names) == "stylist"
    assert agent_named('"general"', names) == "general"
    assert agent_named("I think stylist", names) is None
    assert agent_named("stylist or general", names) is None
    assert agent_named("", names) is None and agent_named(None, names) is None


def test_keywords_pick_the_agent_with_most_hits():
    assert by_keywords("What should I wear? Which outfit goes with it?", AGENTS) == "stylist"
    assert by_keywords("Quelle tenue je peux porter ?", AGENTS) == "stylist"
    assert by_keywords("What is the capital of Japan?", AGENTS) is None


def test_the_router_prompt_lists_every_agent_with_its_description():
    model = FakeModel([say("general")])
    choose_agent("Hi!", AGENTS, model)
    system = model.received[0]["messages"][0]["content"]
    assert all(f"- {name}: {agent.description}" in system for name, agent in AGENTS.agents.items())
    assert model.received[0]["messages"][1] == {"role": "user", "content": "Hi!"}


# ---------------------------------------------------------------- POST /chat
def test_a_button_choice_skips_the_router(make_client):
    model = FakeModel([say("Wear {1}.")])
    body = chat(model, "Hi", make_client, agent="stylist")
    assert len(model.received) == 1                                  # the agent's call only, no routing call
    assert route_of(body) == {"router": "stylist", "how": "button"} and body["agent"] == "stylist"


def test_a_valid_one_word_answer_is_used(make_client):
    model = FakeModel([say("general"), say("Hello! Ask me what to wear.")])
    body = chat(model, "Hi!", make_client)
    routing, answering = model.received
    assert routing["tools"] == [] and routing["temperature"] == 0 and routing["max_tokens"] == 10
    assert answering["temperature"] is None                          # the agent's own call keeps the team's value
    assert route_of(body) == {"router": "general", "how": "model"} and body["agent"] == "general"
    assert body["answer"] == "Hello! Ask me what to wear."


def test_an_invalid_answer_falls_back_to_the_keywords(make_client):
    model = FakeModel([say("Probably the stylist, I think."), say("Wear {1}.")])
    body = chat(model, "What should I wear today?", make_client)
    assert route_of(body) == {"router": "stylist", "how": "keywords"}


def test_an_invalid_answer_without_keywords_falls_back_to_the_stylist(make_client):
    model = FakeModel([say("banana"), say("Fine.")])
    body = chat(model, "What is the capital of Japan?", make_client)
    assert route_of(body) == {"router": "stylist", "how": "default"} and body["agent"] == "stylist"


def test_the_model_failing_during_routing_falls_back_too(make_client):
    model = FailsOnce([say("Wear something warm.")])
    body = chat(model, "Which outfit goes with my skirt?", make_client)
    assert route_of(body) == {"router": "stylist", "how": "keywords"} and body["answer"] == "Wear something warm."


def test_the_model_failing_everywhere_is_still_a_503(client):
    headers = sign_up(client)
    r = client.post("/chat", json={"message": "Hi"}, headers=headers)        # NoModel: the router falls back, then
    assert r.status_code == 503 and r.json()["detail"] == "assistant_unavailable"   # the agent's own call fails


def test_the_general_agent_runs_a_turn_with_no_tools(make_client):
    model = FakeModel([say("general"), say("I am your fashion assistant. {7}")])
    body = chat(model, "Hi!", make_client)
    answering = model.received[1]
    assert answering["tools"] == []                                  # no tool schema was offered
    assert "no tools" in answering["messages"][0]["content"]        # the general agent's instructions
    assert body["stop_reason"] == "answered" and body["pieces"] == {}
    assert body["answer"] == "I am your fashion assistant."          # {7} was never shown by a tool: removed
    assert [line for line in body["trace"] if "tool" in line] == []
