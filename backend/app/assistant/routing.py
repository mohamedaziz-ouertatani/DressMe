"""
The router (step 3e): which agent answers a message.

    1. the app named an agent (a button)        -> that one, no model call              how = "button"
    2. one model call, no tools, temperature 0, -> the agent it names                   how = "model"
       a few tokens: each agent's name and description in, ONE WORD out
    3. the model failed or answered something   -> the agent whose keywords (agents.yaml) appear most  how = "keywords"
       that is not an agent's name
    4. no keyword either                        -> the first agent of the file (stylist) how = "default"

It never raises: a router that is down must not stop the chat (the agent's own call then decides if the model is up).
"""

from .model import ModelUnavailable


def routing_prompt(agents):
    lines = [f"- {name}: {agent.description}" for name, agent in agents.agents.items()]
    return ("You route a message from a user of a fashion app to the agent that should answer it.\n"
            "Agents:\n" + "\n".join(lines) + "\n"
            "Answer with ONE word: the name of the agent. Nothing else.")


def agent_named(text, names):
    """The agent name a model reply is, or None. The whole reply must be the name (case and punctuation aside)."""
    cleaned = (text or "").strip().strip("\"'`.,:;!*() ").lower()
    return cleaned if cleaned in names else None


def by_keywords(message, agents):
    """The agent with the most keywords found in the message (the first of the file wins a tie), or None."""
    lowered = message.lower()
    best, best_hits = None, 0
    for name, agent in agents.agents.items():
        hits = sum(1 for words in agent.keywords.values() for w in words if w.lower() in lowered)
        if hits > best_hits:
            best, best_hits = name, hits
    return best


def choose_agent(message, agents, model, button=None):
    """(agent name, how). `button` = the agent the app asked for, already checked to exist."""
    if button:
        return button, "button"
    try:
        reply = model.chat([{"role": "system", "content": routing_prompt(agents)},
                            {"role": "user", "content": message}],
                           [], agents.router.max_tokens, temperature=agents.router.temperature)
        named = agent_named(reply.text, agents.agents)
        if named:
            return named, "model"
    except ModelUnavailable:
        pass
    found = by_keywords(message, agents)
    if found:
        return found, "keywords"
    return next(iter(agents.agents)), "default"
