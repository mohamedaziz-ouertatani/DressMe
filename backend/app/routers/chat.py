"""
POST /chat: one turn with the assistant (step 3c, the walking skeleton; the real model comes in step 3d).

    body    {message: 1-1000 characters, chat_id?: text, agent?: a name from mappings/agents.yaml}
    answer  {chat_id, agent, answer, pieces: {"<n>": item}, trace, stop_reason, model}

The answer names pieces as {n}; `pieces` holds the user's OWN items behind the numbers the answer uses, so the app
can show their photos. Each turn is saved as one document in `chats` (the message and the answer live only there).
The event log keeps counts and times, never the message text. No model set up: 503 `assistant_unavailable`.
"""

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..assistant.ledger import PieceLedger
from ..assistant.loop import run_turn
from ..assistant.model import ModelUnavailable
from ..assistant.tools import ToolContext
from ..db import object_id
from ..events import log_event
from ..security import current_user
from ..wardrobe import item_out

router = APIRouter(tags=["assistant"])


class ChatBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=1000)
    chat_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    agent: str | None = None


@router.post("/chat")
def chat(body: ChatBody, request: Request, user=Depends(current_user)):
    state = request.app.state
    agents = state.agents
    # TODO(step 3e): with no agent given, the router picks one from the keywords; for now the first of the file
    name = body.agent or next(iter(agents.agents))
    if name not in agents.agents:
        raise HTTPException(422, "unknown_agent")

    started = time.perf_counter()
    ctx = ToolContext(user_id=user["_id"], db=state.db, ledger=PieceLedger())
    try:
        turn = run_turn(agents.agents[name], body.message, state.chat_model, state.registry, ctx,
                        shared_rules=agents.shared_rules)
    except ModelUnavailable:
        raise HTTPException(503, "assistant_unavailable")

    # the pieces behind the {n} in the answer: only the user's own items, through the ledger
    item_ids = [ctx.ledger.item_id(ref) for ref in turn.refs]
    docs = {str(d["_id"]): d for d in state.db.items.find(
        {"_id": {"$in": [object_id(i) for i in item_ids]}, "user_id": user["_id"]})}
    pieces = {str(ref): item_out(docs[i]) for ref, i in zip(turn.refs, item_ids) if i in docs}

    chat_id = body.chat_id or uuid.uuid4().hex
    state.db.chats.insert_one({
        "user_id": user["_id"], "chat_id": chat_id, "created_at": datetime.now(timezone.utc), "agent": name,
        "message": body.message, "answer": turn.answer, "item_ids": item_ids, "unknown_refs": turn.unknown_refs,
        "trace": turn.trace, "stop_reason": turn.stop_reason, "model": state.chat_model.name})
    log_event(state.db, "assistant", user["_id"], agent=name, rounds=turn.rounds, stop_reason=turn.stop_reason,
              n_tool_calls=len(turn.trace), n_unknown_refs=len(turn.unknown_refs),
              ms=round((time.perf_counter() - started) * 1000))      # never the message text
    return {"chat_id": chat_id, "agent": name, "answer": turn.answer, "pieces": pieces, "trace": turn.trace,
            "stop_reason": turn.stop_reason, "model": state.chat_model.name}
