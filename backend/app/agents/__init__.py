"""
The DressMe AI agents (see AGENTS.md). Each agent is a system prompt plus a set of
tools (Python functions bound to the current user); the router (router.py) picks
one agent per chat message.
"""

from . import analyst, explainer, seller, shopping, stylist

# name -> agent, in the order the router prompt and AGENTS.md list them
AGENTS = {a.name: a for a in (stylist.AGENT, shopping.AGENT, analyst.AGENT, seller.AGENT,
                              explainer.AGENT)}
DEFAULT_AGENT = "stylist"      # when the router can't tell
