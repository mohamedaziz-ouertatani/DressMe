"""
The agent router: which agent answers a chat message (see AGENTS.md).

    1. The language model reads a short list of the agents and answers one word
       (engine.classify), unless ROUTER=keywords.
    2. If that call fails (no key, busy, quota) or answers something else, the
       team's keyword table decides (mappings/agent_keywords.csv).
    3. No keyword either: the Stylist.

Only the latest message is routed; the chosen agent still sees the whole history.
"""

import csv
import re
import unicodedata

from ..chat_engine import ChatBusy, ChatUnavailable
from ..config import ROOT
from . import AGENTS, DEFAULT_AGENT

KEYWORDS_CSV = ROOT / "mappings" / "agent_keywords.csv"


def normalise(text):
    """Lower case, without accents (é -> e), so 'Météo' matches 'meteo'."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def load_keywords(path=KEYWORDS_CSV):
    """[(agent, keyword)] from the team's table. An unknown agent stops with an error."""
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            if row["agent"] not in AGENTS:
                raise ValueError(f"{path.name} line {line}: unknown agent {row['agent']!r}")
            if row["keyword"].strip():
                rows.append((row["agent"], normalise(row["keyword"].strip())))
    return rows


def by_keywords(message, keywords):
    """The agent with the most keywords found at the start of a word in the message
    (ties and no match: the Stylist)."""
    text = normalise(message)
    hits = {name: 0 for name in AGENTS}
    for agent, keyword in keywords:
        if re.search(r"(?<!\w)" + re.escape(keyword), text):
            hits[agent] += 1
    best = max(hits.values())
    winners = [name for name, n in hits.items() if n == best]
    return winners[0] if best and len(winners) == 1 else DEFAULT_AGENT


def router_prompt():
    lines = [f"- {a.name}: {a.description}" for a in AGENTS.values()]
    return ("You route messages of a fashion app to one assistant. The assistants:\n"
            + "\n".join(lines)
            + "\nAnswer with the assistant's name only, one word: " + ", ".join(AGENTS) + ".")


_KEYWORDS = None     # read once, on first use


def route(engine, message, mode="llm", keywords=None):
    """(agent name, how it was chosen: 'llm' or 'keywords')."""
    global _KEYWORDS
    if mode == "llm":
        try:
            label = normalise(engine.classify(router_prompt(), message))
        except (ChatUnavailable, ChatBusy):        # ChatQuota is a ChatBusy
            label = ""
        found = [name for name in AGENTS if name in label]
        if len(found) == 1:
            return found[0], "llm"
    if keywords is None:
        _KEYWORDS = _KEYWORDS or load_keywords()
        keywords = _KEYWORDS
    return by_keywords(message, keywords), "keywords"
