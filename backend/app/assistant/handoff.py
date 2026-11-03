"""
Handoff (step 3e.6): one message with two parts, two agents.

    agent A is answering; the message has a part that belongs to agent B
    A calls handoff(agent="B", note="...")  -> the tool only records {"to", "note"} in the turn's context
    the loop stops with stop_reason "handoff" (A writes its own part from the tool results it already has)
    the route (chat.py) runs B ONCE: the original message + A's note, the SAME context (same piece and listing
    ledgers, so {n} means the same piece in both answers). B has no handoff tool, so it cannot hand over again.

Everything the code guarantees lives here: the target must be another agent of agents.yaml, one handoff per turn.
Nothing else about the second run is new: it is `run_turn` again.
"""

from pydantic import Field

from .loop import TurnResult
from .tools import Tool, ToolError
from .tools_stylist import Strict

# This sentence starts a line in the instructions of every agent that has the tool (mappings/agents.yaml); an agent may
# add an example after it on the same line. The second run removes the whole line, because that agent cannot hand over.
INSTRUCTION_LINE = ("If the user also asks something that belongs to another agent, call handoff with that agent's "
                    "name and a short note, and do not answer that part yourself.")


class HandoffArgs(Strict):
    agent: str = Field(min_length=1, max_length=40)
    note: str = Field(min_length=1, max_length=100)


def handoff(ctx, args):
    if args.agent == ctx.agent:
        raise ToolError("invalid_target", "That is you: hand over to ANOTHER agent.")
    if args.agent not in ctx.known_agents:
        raise ToolError("unknown_agent", f"There is no agent {args.agent!r}. The agents are: "
                                         f"{', '.join(a for a in ctx.known_agents if a != ctx.agent)}.")
    if ctx.handoff is not None:
        raise ToolError("already_handed_over", "You already handed this message over. Answer your own part.")
    ctx.handoff = {"to": args.agent, "note": args.note}
    return {"handed_over_to": args.agent, "now": "Write only your own part of the answer."}


HANDOFF = Tool("handoff", (
    "Only when the message has a separate part that another agent should answer. "
    "Do not use it for the part you can answer. "
    "agent: the other agent's name; note: what that part is, in a few words. Example: handoff(agent='stylist', "
    "note='what to wear instead')."),
    HandoffArgs, handoff)


def menu(agents, current):
    """The other agents and what they handle, for the system prompt of an agent that has the handoff tool."""
    lines = [f"- {name}: {agent.description}" for name, agent in agents.agents.items() if name != current]
    return "Agents you can hand over to with the handoff tool:\n" + "\n".join(lines)


def second_run_agent(agent):
    """The agent as it runs the second part: no handoff tool and no instruction about it."""
    kept = [line for line in agent.instructions.splitlines() if not line.strip().startswith(INSTRUCTION_LINE)]
    return agent.model_copy(update={"tools": [t for t in agent.tools if t != "handoff"],
                                    "instructions": "\n".join(kept).rstrip() + "\n"})


def merge_turns(first, second, handed):
    """One TurnResult for the user: the first agent's part (if it wrote one) then the second's. Refs are shared (one
    ledger), so the union is exact. The trace keeps both agents' lines with a {"handoff": ...} line between them."""
    def union(a, b):
        return a + [x for x in b if x not in a]
    answer = f"{first.answer}\n\n{second.answer}" if first.answer else second.answer
    return TurnResult(answer, union(first.refs, second.refs), union(first.unknown_refs, second.unknown_refs),
                      first.trace + [{"handoff": handed}] + second.trace, second.stop_reason,
                      first.rounds + second.rounds, union(first.echoed_refs, second.echoed_refs))


def second_message(message, first, note):
    """What the second agent reads: the original message and which part is its own."""
    return f"{message}\n\n[The {first} agent handed this to you. Answer only this part: {note}]"
