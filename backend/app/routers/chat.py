"""
The DressMe chat (Gemini or a local model, see app/chat_engine.py): each message goes to one of
five agents (Stylist, Shopping advisor, Wardrobe analyst, Seller assistant, Explainer; see
AGENTS.md and app/agents/), which
answers from the user's REAL data by calling our functions (tools) instead of inventing clothes.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from ..agents import AGENTS
from ..agents.router import route
from ..chat_engine import ChatBusy, ChatQuota, ChatUnavailable
from ..events import log_event
from ..schemas import ChatMessage
from ..security import current_user

router = APIRouter(tags=["chat"])
HISTORY = 20     # messages sent back to the model as context

# When the model returns no text at all (a small local model sometimes does): never
# pretend something was found, ask again in the user's profile language
NO_ANSWER = {
    "en": "Sorry, I couldn't finish that answer. Could you ask again in other words?",
    "fr": "Désolé, je n'ai pas pu terminer cette réponse. Tu peux reformuler ta question ?",
    "ar": "سامحني، ما كمّلتش الجواب. تنجم تعاود تسأل بكلام آخر؟",
}


@router.post("/chat")
def chat(body: ChatMessage, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    history = list(db.chats.find({"user_id": user["_id"]}).sort("created_at", -1).limit(HISTORY))[::-1]
    engine = request.app.state.chat_engine
    name, routed_by = route(engine, body.message, request.app.state.settings.router)
    agent = AGENTS[name]
    attachments, actions, trace = [], [], []      # trace: "How I answered" (XAI)
    try:
        answer, used = engine.reply(
            agent.prompt(user), [{"role": h["role"], "text": h["text"]} for h in history],
            body.message, agent.bound_tools(request, user, attachments, actions, trace))
    except ChatUnavailable as e:       # no key: the assistant is switched off
        raise HTTPException(503, str(e))
    except ChatQuota as e:             # the key's (daily) quota is used up
        raise HTTPException(429, str(e))
    except ChatBusy as e:              # the model is down or overloaded: try again later
        raise HTTPException(502, str(e))
    if not answer.strip():
        answer = NO_ANSWER.get(user["profile"].get("language"), NO_ANSWER["en"])
    now = datetime.now(timezone.utc)
    db.chats.insert_many([
        {"user_id": user["_id"], "role": "user", "text": body.message, "created_at": now},
        # 1 ms later: MongoDB keeps milliseconds, and the answer must sort after the question
        {"user_id": user["_id"], "role": "model", "text": answer, "tools": used,
         "attachments": attachments, "actions": actions, "agent": name, "routed_by": routed_by,
         "trace": trace,
         "created_at": now + timedelta(milliseconds=1)},
    ])
    log_event(db, "chat", user["_id"], tools=used, agent=name)
    result = {"reply": answer, "tools_used": used, "agent": name, "agent_title": agent.title,
              "routed_by": routed_by, "trace": trace}
    if attachments:
        result["attachments"] = attachments
    if actions:                        # e.g. the Seller assistant's ready-filled Sell form
        result["actions"] = actions
    return result


@router.get("/chat/history")
def chat_history(request: Request, user=Depends(current_user)):
    docs = request.app.state.db.chats.find({"user_id": user["_id"]}).sort("created_at", 1)
    return [{"role": d["role"], "text": d["text"], "tools_used": d.get("tools", []),
             "attachments": d.get("attachments", []), "agent": d.get("agent", ""), "actions": d.get("actions", []),
             "routed_by": d.get("routed_by", ""), "trace": d.get("trace", [])} for d in docs]


@router.delete("/chat/history", status_code=204)
def clear_history(request: Request, user=Depends(current_user)):
    request.app.state.db.chats.delete_many({"user_id": user["_id"]})
