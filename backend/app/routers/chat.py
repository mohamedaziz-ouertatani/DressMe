"""
POST /chat: one turn with the assistant (step 3c; the real model, Ollama, since step 3d).
A message with a part for another agent: the first agent calls the handoff tool, the other agent answers that part
ONCE with the same ledgers (step 3e.6, assistant/handoff.py); `agent` in the answer is then the second agent.

    body    {message: 1-1000 characters, chat_id?: text, agent?: a name from mappings/agents.yaml}
    answer  {chat_id, agent, answer, pieces: {"<n>": item}, trace, stop_reason, model}

GET /assistant/status: {available, model}, so the app can say early that the assistant is off (step 3d).

The answer names pieces as {n}; `pieces` holds the user's OWN items behind the numbers the answer uses, so the app
can show their photos. Each turn is saved as one document in `chats` (the message and the answer live only there).
The event log keeps counts and times, never the message text. No model set up: 503 `assistant_unavailable`.
"""

import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..assistant.handoff import menu as handoff_menu, merge_turns, second_message, second_run_agent
from ..assistant.ledger import PieceLedger
from ..assistant.loop import run_turn
from ..assistant.model import ModelUnavailable
from ..assistant.routing import choose_agent
from ..assistant.tools import ToolContext
from ..db import object_id
from ..events import log_event
from ..security import current_user
from ..wardrobe import item_out

router = APIRouter(tags=["assistant"])
USER_REF = re.compile(r"\{(\d+)\}")      # a {number} typed by the user


class ChatBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=1000)
    chat_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    agent: str | None = None


@router.post("/chat")
def chat(body: ChatBody, request: Request, user=Depends(current_user)):
    state = request.app.state
    agents = state.agents
    if body.agent and body.agent not in agents.agents:
        raise HTTPException(422, "unknown_agent")

    started = time.perf_counter()
    # the model must never see a {n} it did not get from a tool, or it may copy it as a piece number;
    # only this copy changes, the saved message stays as the user wrote it
    for_model = USER_REF.sub(r"\1", body.message)
    # step 3e: which agent answers (the app's button, else the router's one-word model call, else the keywords)
    name, how = choose_agent(for_model, agents, state.chat_model, button=body.agent)
    route_line = {"router": name, "how": how}
    # the tools reuse the screens' functions, which read the request (app state) and the user document (step 3d)
    ctx = ToolContext(user_id=user["_id"], db=state.db, ledger=PieceLedger(), user=user, request=request,
                      agent=name, known_agents=tuple(agents.agents))
    answering, handed = name, None
    try:
        turn = run_turn(agents.agents[name], for_model, state.chat_model, state.registry, ctx,
                        shared_rules=shared_rules_for(agents, name))
        if turn.handoff:                          # step 3e.6: the other agent answers the rest, ONCE, same ledgers
            handed = {"from": name, "to": turn.handoff["to"], "note": turn.handoff["note"]}
            answering, ctx.agent, ctx.handoff = handed["to"], handed["to"], None
            second = run_turn(second_run_agent(agents.agents[answering]),
                              second_message(for_model, name, handed["note"]),
                              state.chat_model, state.registry, ctx, shared_rules=agents.shared_rules)
            turn = merge_turns(turn, second, handed)
    except ModelUnavailable:
        raise HTTPException(503, "assistant_unavailable")
    turn.trace.insert(0, route_line)

    # the pieces behind the {n} in the answer: only the user's own items, through the ledger
    item_ids = [ctx.ledger.item_id(ref) for ref in turn.refs]
    docs = {str(d["_id"]): d for d in state.db.items.find(
        {"_id": {"$in": [object_id(i) for i in item_ids]}, "user_id": user["_id"]})}
    pieces = {str(ref): item_out(docs[i]) for ref, i in zip(turn.refs, item_ids) if i in docs}

    chat_id = body.chat_id or uuid.uuid4().hex
    state.db.chats.insert_one({
        "user_id": user["_id"], "chat_id": chat_id, "created_at": datetime.now(timezone.utc), "agent": answering,
        "agents": [name, answering] if handed else [name], "handoff": handed,       # both agents are kept
        "message": body.message, "answer": turn.answer, "item_ids": item_ids, "unknown_refs": turn.unknown_refs,
        "echoed_refs": turn.echoed_refs, "trace": turn.trace, "stop_reason": turn.stop_reason, "model": state.chat_model.name})
    log_event(state.db, "assistant", user["_id"], agent=answering, routed=how, rounds=turn.rounds, stop_reason=turn.stop_reason,
              n_tool_calls=sum(1 for line in turn.trace if "tool" in line), n_unknown_refs=len(turn.unknown_refs),
              handed_from=name if handed else None,
              ms=round((time.perf_counter() - started) * 1000))      # never the message text
    return {"chat_id": chat_id, "agent": answering, "answer": turn.answer, "pieces": pieces, "trace": turn.trace,
            "stop_reason": turn.stop_reason, "model": state.chat_model.name}


def shared_rules_for(agents, name):
    """The shared rules; an agent that has the handoff tool also reads who it can hand over to (from agents.yaml)."""
    if "handoff" not in agents.agents[name].tools:
        return agents.shared_rules
    return agents.shared_rules.rstrip() + "\n\n" + handoff_menu(agents, name)


@router.get("/assistant/status")
def status(request: Request, user=Depends(current_user)):
    """Is the model there? (Ollama's /api/show, 3 s at most, remembered for a minute.)"""
    model = request.app.state.chat_model
    return {"available": bool(model.available()), "model": model.name}
