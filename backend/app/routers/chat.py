"""
The DressMe chat assistant (Gemini). It answers from the user's REAL wardrobe
by calling our functions (tools) instead of inventing clothes.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..chat_engine import ChatUnavailable
from ..events import log_event
from ..schemas import ChatMessage
from ..security import current_user
from ..wardrobe import outfit_out, to_compat
from .outfits import profile, wardrobe

router = APIRouter(tags=["chat"])
HISTORY = 20     # messages sent back to the model as context

SYSTEM = """You are DressMe, a friendly personal fashion assistant for young people in Tunisia
who have a limited budget and buy mostly second-hand (friperie) clothes that can rarely be returned.
Rules:
- Answer in the user's language ({language}: fr = French, ar = Tunisian Arabic / Arabic, en = English),
  or in the language the user writes in.
- Use the tools to see the user's real wardrobe and to build or score outfits. Never invent items
  the user does not own; refer to items by their description (e.g. "your black jeans").
- Respect the user's modesty level (coverage {min_coverage}, 1 = very revealing ... 5 = fully covered;
  empty = no preference). Never push them to show more.
- For "should I buy this?", use buy_advice_last_scan (the last photo they analysed in the app).
- Be short, concrete and kind. Budget matters: prefer re-using what they own."""


def tools_for(request, user):
    """The functions Gemini may call, already bound to this user."""
    def list_wardrobe(category: str = "") -> list[dict]:
        """List the user's clothes. category: optional filter (top, bottom, dress, outerwear,
        shoes, bag, accessory, traditional, swimwear)."""
        docs, _ = wardrobe(request, user)
        return [{"id": str(d["_id"]), "category": d["category"], "sub_category": d["sub_category"],
                 "colour": d["colour"], "pattern": d["pattern"]}
                for d in docs if not category or d["category"] == category]

    def suggest_outfits(season: str = "", occasion: str = "", n: int = 3) -> list[dict]:
        """Best outfits from the user's wardrobe. season: summer, winter or mid-season.
        occasion: casual, formal, sport, wedding, eid or work. n: how many (1-10)."""
        docs, by_id = wardrobe(request, user)
        outfits = compatibility.suggest_outfits(
            [to_compat(d) for d in docs], profile(user, season or None, occasion or None),
            n=max(1, min(int(n), 10)))
        return [outfit_out(o, by_id) for o in outfits]

    def score_outfit(item_ids: list[str]) -> dict:
        """Score (0-100) and reasons for an outfit made of the user's items (ids from list_wardrobe)."""
        docs, by_id = wardrobe(request, user)
        chosen = [by_id[i] for i in item_ids if i in by_id]
        if not chosen:
            return {"error": "none of these ids are in the wardrobe"}
        items = [to_compat(d) for d in chosen]
        clash = compatibility.clashes(items)
        if clash:          # same hard rule as /outfits/score
            return {"error": "these pieces can't be worn together: " + "; ".join(clash)}
        return outfit_out({**compatibility.score_outfit(items), "items": items}, by_id)

    def buy_advice_last_scan() -> dict:
        """'Should I buy this?' for the last photo the user analysed in the app (buy / think / skip)."""
        cand = request.app.state.db.candidates.find_one({"user_id": user["_id"]},
                                                        sort=[("created_at", -1)])
        if not cand:
            return {"error": "no analysed photo in the last 24 hours"}
        docs, by_id = wardrobe(request, user)
        by_id[str(cand["_id"])] = cand
        advice = compatibility.buy_advice(to_compat(cand), [to_compat(d) for d in docs], profile(user))
        return {"item": {"category": cand["category"], "sub_category": cand["sub_category"],
                         "colour": cand["colour"]},
                "verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
                "reasons": advice["reasons"], "best": [outfit_out(o, by_id) for o in advice["best"]]}

    return {f.__name__: f for f in (list_wardrobe, suggest_outfits, score_outfit, buy_advice_last_scan)}


@router.post("/chat")
def chat(body: ChatMessage, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    history = list(db.chats.find({"user_id": user["_id"]}).sort("created_at", -1).limit(HISTORY))[::-1]
    p = user["profile"]
    system = SYSTEM.format(language=p.get("language", "fr"), min_coverage=p.get("min_coverage") or "")
    try:
        answer, used = request.app.state.chat_engine.reply(
            system, [{"role": h["role"], "text": h["text"]} for h in history],
            body.message, tools_for(request, user))
    except ChatUnavailable as e:
        raise HTTPException(503, str(e))
    now = datetime.now(timezone.utc)
    db.chats.insert_many([
        {"user_id": user["_id"], "role": "user", "text": body.message, "created_at": now},
        # 1 ms later: MongoDB keeps milliseconds, and the answer must sort after the question
        {"user_id": user["_id"], "role": "model", "text": answer, "tools": used,
         "created_at": now + timedelta(milliseconds=1)},
    ])
    log_event(db, "chat", user["_id"], tools=used)
    return {"reply": answer, "tools_used": used}


@router.get("/chat/history")
def chat_history(request: Request, user=Depends(current_user)):
    docs = request.app.state.db.chats.find({"user_id": user["_id"]}).sort("created_at", 1)
    return [{"role": d["role"], "text": d["text"], "tools_used": d.get("tools", [])} for d in docs]


@router.delete("/chat/history", status_code=204)
def clear_history(request: Request, user=Depends(current_user)):
    request.app.state.db.chats.delete_many({"user_id": user["_id"]})
