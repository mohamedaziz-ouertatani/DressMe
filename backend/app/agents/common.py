"""
What the three DressMe agents share (see AGENTS.md): the item pictures shown
under an answer, the prompt rules every agent follows, the Agent record, and
the list_wardrobe tool every agent can call.
"""

from dataclasses import dataclass
from functools import wraps
from typing import Callable

from ..routers.outfits import wardrobe


def image_attachments(value, group=""):
    """Extract safe, displayable item images from a tool result."""
    if isinstance(value, dict):
        if isinstance(value.get("image_url"), str) and isinstance(value.get("id"), str):
            yield {
                "id": value["id"],
                "category": value.get("category", ""),
                "sub_category": value.get("sub_category", ""),
                "colour": value.get("colour", ""),
                "image_url": value["image_url"],
                "group": group,
            }
        for child in value.values():
            yield from image_attachments(child, group)
    elif isinstance(value, list):
        for index, child in enumerate(value, 1):
            child_group = group or f"outfit-{index}"
            yield from image_attachments(child, child_group)


def sell_actions(value):
    """The chat actions in a tool result: only links to the app's own Sell form
    (a model must not be able to put any other link in front of the user)."""
    if isinstance(value, dict):
        action = value.get("action")
        if (isinstance(action, dict) and action.get("kind") == "sell"
                and isinstance(action.get("url"), str) and action["url"].startswith("/sell?")):
            yield {"kind": "sell", "url": action["url"]}
        for child in value.values():
            yield from sell_actions(child)
    elif isinstance(value, list):
        for child in value:
            yield from sell_actions(child)


def with_attachments(functions, attachments, actions=None):
    """The tools as {name: function}. With an `attachments` list, every item picture a
    tool returns is also added to it (once), so the app can show it under the answer;
    with an `actions` list, every Sell-form link too (once)."""
    if attachments is None and actions is None:
        return dict(functions)

    def capture(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            if attachments is not None:
                seen = {item["id"] for item in attachments}
                for item in image_attachments(result):
                    if item["id"] not in seen:
                        attachments.append(item)
                        seen.add(item["id"])
            if actions is not None:
                for action in sell_actions(result):
                    if action not in actions:
                        actions.append(action)
            return result
        return wrapped

    return {name: capture(fn) for name, fn in functions.items()}


def list_wardrobe_tool(request, user):
    """The list_wardrobe tool, bound to this user (every agent has it)."""
    def list_wardrobe(category: str = "") -> list[dict]:
        """List the user's clothes. category: optional filter (top, bottom, dress, outerwear,
        shoes, bag, accessory, traditional, swimwear)."""
        docs, _ = wardrobe(request, user)
        return [{"id": str(d["_id"]), "category": d["category"], "sub_category": d["sub_category"],
                 "colour": d["colour"], "pattern": d["pattern"],
                 "image_url": f"/items/{d['_id']}/image"}
                for d in docs if not category or d["category"] == category]
    return list_wardrobe


# The rules every agent follows (the same as the original chat prompt, chat.SYSTEM)
BASE = """You are DressMe, a friendly personal fashion assistant for young people in Tunisia
who have a limited budget and buy mostly second-hand (friperie) clothes that can rarely be returned.
Rules:
- Answer in the language the user writes in (French, English, or Tunisian Arabic / Darija, also when
  they write Darija in Latin letters). Only when that is unclear, use their profile language
  ({language}: fr = French, ar = Tunisian Arabic, en = English).
- Use the tools to see the user's real wardrobe. Never invent items the user does not own;
  refer to items by their description (e.g. "your black jeans").
- Respect the user's modesty level (coverage {min_coverage}, 1 = very revealing ... 5 = fully covered;
  empty = no preference). Never push them to show more.
- Be short, concrete and kind. Budget matters: prefer re-using what they own."""

# What the agents do, so each one can point the user to the right one
TEAM = """DressMe has three assistants and each message goes to one of them:
- the Stylist: what to wear today or for an occasion, outfits from the wardrobe, the weather;
- the Shopping advisor: should I buy this, where to find a piece, prices in shops and friperie;
- the Wardrobe analyst: what the wardrobe lacks, its most and least useful pieces, near-duplicates.
If the question is for another assistant, say so in one sentence and invite the user to ask it."""


def system_prompt(user, job):
    """The shared rules, filled in for this user, + this agent's job + the team."""
    p = user["profile"]
    rules = BASE.format(language=p.get("language", "fr"), min_coverage=p.get("min_coverage") or "")
    return f"{rules}\n\nYour job: {job}\n\n{TEAM}"


@dataclass(frozen=True)
class Agent:
    name: str             # stylist, shopping or analyst (saved with each chat answer)
    title: str            # how the app names it (translated in the frontend)
    description: str      # one line, read by the router
    job: str              # this agent's part of the system prompt
    tools: Callable       # tools(request, user) -> {name: function}

    def prompt(self, user):
        return system_prompt(user, self.job)

    def bound_tools(self, request, user, attachments=None, actions=None):
        return with_attachments(self.tools(request, user), attachments, actions)
