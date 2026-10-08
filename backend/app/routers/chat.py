"""
The DressMe chat assistant (Gemini or a local model, see app/chat_engine.py). It answers from the user's REAL wardrobe
by calling our functions (tools) instead of inventing clothes.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from ..agents import shopping, stylist
from ..agents.common import with_attachments
from ..chat_engine import ChatBusy, ChatQuota, ChatUnavailable
from ..events import log_event
from ..schemas import ChatMessage
from ..security import current_user

router = APIRouter(tags=["chat"])
HISTORY = 20     # messages sent back to the model as context

SYSTEM = """You are DressMe, a friendly personal fashion assistant for young people in Tunisia
who have a limited budget and buy mostly second-hand (friperie) clothes that can rarely be returned.
Rules:
- Answer in the language the user writes in (French, English, or Tunisian Arabic / Darija, also when
  they write Darija in Latin letters). Only when that is unclear, use their profile language
  ({language}: fr = French, ar = Tunisian Arabic, en = English).
- Use the tools to see the user's real wardrobe and to build or score outfits. Never invent items
  the user does not own; refer to items by their description (e.g. "your black jeans").
- Respect the user's modesty level (coverage {min_coverage}, 1 = very revealing ... 5 = fully covered;
  empty = no preference). Never push them to show more.
- For "should I buy this?", use buy_advice_last_scan (the last photo they analysed in the app).
- Be short, concrete and kind. Budget matters: prefer re-using what they own."""


def tools_for(request, user, attachments=None):
    """The original four chat tools. Kept for src/phase4/build_chat_dataset.py: the
    fine-tuned local model (LLM.md) was trained on exactly these."""
    s, b = stylist.tools(request, user), shopping.tools(request, user)
    functions = {name: s[name] for name in ("list_wardrobe", "suggest_outfits", "score_outfit")}
    functions["buy_advice_last_scan"] = b["buy_advice_last_scan"]
    return with_attachments(functions, attachments)


@router.post("/chat")
def chat(body: ChatMessage, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    history = list(db.chats.find({"user_id": user["_id"]}).sort("created_at", -1).limit(HISTORY))[::-1]
    p = user["profile"]
    system = SYSTEM.format(language=p.get("language", "fr"), min_coverage=p.get("min_coverage") or "")
    attachments = []
    try:
        answer, used = request.app.state.chat_engine.reply(
            system, [{"role": h["role"], "text": h["text"]} for h in history],
            body.message, tools_for(request, user, attachments))
    except ChatUnavailable as e:       # no key: the assistant is switched off
        raise HTTPException(503, str(e))
    except ChatQuota as e:             # the key's (daily) quota is used up
        raise HTTPException(429, str(e))
    except ChatBusy as e:              # the model is down or overloaded: try again later
        raise HTTPException(502, str(e))
    now = datetime.now(timezone.utc)
    db.chats.insert_many([
        {"user_id": user["_id"], "role": "user", "text": body.message, "created_at": now},
        # 1 ms later: MongoDB keeps milliseconds, and the answer must sort after the question
        {"user_id": user["_id"], "role": "model", "text": answer, "tools": used,
         "attachments": attachments,
         "created_at": now + timedelta(milliseconds=1)},
    ])
    log_event(db, "chat", user["_id"], tools=used)
    result = {"reply": answer, "tools_used": used}
    if attachments:
        result["attachments"] = attachments
    return result


@router.get("/chat/history")
def chat_history(request: Request, user=Depends(current_user)):
    docs = request.app.state.db.chats.find({"user_id": user["_id"]}).sort("created_at", 1)
    return [{"role": d["role"], "text": d["text"], "tools_used": d.get("tools", []),
             "attachments": d.get("attachments", [])} for d in docs]


@router.delete("/chat/history", status_code=204)
def clear_history(request: Request, user=Depends(current_user)):
    request.app.state.db.chats.delete_many({"user_id": user["_id"]})
