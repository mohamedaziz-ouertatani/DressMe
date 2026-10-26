"""
One turn of the assistant (step 3c): the user's message in, an answer out.

    messages = [system (the agent's instructions + the shared rules), user]
    repeat up to max_rounds times:
        reply = model.chat(messages, the agent's tool schemas, max_tokens)
        text and no tool call -> done ("answered")
        tool calls -> run each through the registry, add the results to the messages, ask again
    when the rounds run out, or the model asks for the SAME call again: one last chat() with no tools, so it must
    answer ("max_rounds" / "repeat"). Finally the {n} rule cleans the answer.

The loop never raises for a tool problem (the model reads the error and can correct itself). Only ModelUnavailable
goes up, to the route.
"""

import json
from dataclasses import dataclass

from .placeholders import resolve


@dataclass
class TurnResult:
    answer: str
    refs: list
    unknown_refs: list
    trace: list
    stop_reason: str
    rounds: int


def call_key(call):
    """The same tool with the same arguments, whatever the order of the arguments."""
    return (call.name, json.dumps(call.arguments, sort_keys=True, default=str))


def n_pieces(result):
    return len(result.data.get("pieces", [])) if result.ok and isinstance(result.data, dict) else 0


def run_turn(agent, user_text, model, registry, ctx, shared_rules=""):
    system = agent.instructions.strip() + ("\n\n" + shared_rules.strip() if shared_rules.strip() else "")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_text}]
    schemas = registry.schemas(agent.tools)
    seen, trace = set(), []
    stop_reason, rounds, reply = "max_rounds", 0, None

    while rounds < agent.max_rounds:
        rounds += 1
        reply = model.chat(messages, schemas, agent.max_tokens)
        if reply.thinking_stripped:                       # step 3d: only the loop sees every reply, so it notes it
            trace.append({"round": rounds, "note": "thinking_stripped"})
        if not reply.tool_calls:
            stop_reason = "answered"
            break
        messages.append({"role": "assistant", "content": reply.text or "",
                         "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}}
                                        for c in reply.tool_calls]})
        repeated = False
        for call in reply.tool_calls:
            key = call_key(call)
            if key in seen:                               # asked again with the same arguments: stop looping
                repeated = True
                content = {"error": "repeat", "message": "You already made this call. Answer with what you have."}
            else:
                seen.add(key)
                result = registry.run(call, ctx)
                content = result.for_model()
                trace.append({"round": rounds, "tool": call.name, "args": call.arguments, "ok": result.ok,
                              "error_code": result.error_code, "n_pieces": n_pieces(result), "ms": result.ms})
            messages.append({"role": "tool", "name": call.name, "content": json.dumps(content, ensure_ascii=False)})
        if repeated:
            stop_reason = "repeat"
            break

    if stop_reason != "answered":                         # the last chance: no tools, so it must answer
        reply = model.chat(messages, [], agent.max_tokens)
        if reply.thinking_stripped:
            trace.append({"round": rounds + 1, "note": "thinking_stripped"})
    answer, refs, unknown = resolve(reply.text or "", ctx.ledger)
    return TurnResult(answer, refs, unknown, trace, stop_reason, rounds)
