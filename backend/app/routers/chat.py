"""
The DressMe chat assistant (Gemini or a local model, see app/chat_engine.py). It answers from the user's REAL wardrobe
by calling our functions (tools) instead of inventing clothes.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..chat_engine import ChatBusy, ChatQuota, ChatUnavailable
from ..events import log_event
from ..schemas import ChatMessage
from ..security import current_user
from ..wardrobe import outfit_out, to_compat
from .outfits import profile, user_profile, wardrobe

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


def _image_attachments(value, group=""):
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
            yield from _image_attachments(child, group)
    elif isinstance(value, list):
        for index, child in enumerate(value, 1):
            child_group = group or f"outfit-{index}"
            yield from _image_attachments(child, child_group)


def tools_for(request, user, attachments=None):
    """The functions the model may call, already bound to this user."""
    def list_wardrobe(category: str = "") -> list[dict]:
        """List the user's clothes. category: optional filter (top, bottom, dress, outerwear,
        shoes, bag, accessory, traditional, swimwear)."""
        docs, _ = wardrobe(request, user)
        return [{"id": str(d["_id"]), "category": d["category"], "sub_category": d["sub_category"],
                 "colour": d["colour"], "pattern": d["pattern"],
                 "image_url": f"/items/{d['_id']}/image"}
                for d in docs if not category or d["category"] == category]

    def suggest_outfits(season: str = "", occasion: str = "", n: int = 1) -> list[dict]:
        """Recommend one best outfit from the user's wardrobe. season: summer, winter or
        mid-season. occasion: casual, formal, sport, wedding, eid or work. n: how many
        when the user explicitly asks for more (1-10)."""
        docs, by_id = wardrobe(request, user)
        outfits = compatibility.suggest_outfits(
            [to_compat(d) for d in docs], user_profile(
                user, docs, request, season or None, occasion or None),
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
        return outfit_out({**compatibility.score_outfit(
            items, style_profile=user_profile(user, docs, request)["style_vector"]),
            "items": items}, by_id)

    def buy_advice_last_scan() -> dict:
        """'Should I buy this?' for the last photo the user analysed in the app (buy / think / skip)."""
        cand = request.app.state.db.candidates.find_one({"user_id": user["_id"]},
                                                        sort=[("created_at", -1)])
        if not cand:
            return {"error": "no analysed photo in the last 24 hours"}
        docs, by_id = wardrobe(request, user)
        by_id[str(cand["_id"])] = cand
        advice = compatibility.buy_advice(
            to_compat(cand), [to_compat(d) for d in docs],
            user_profile(user, docs, request))
        return {"item": {"id": str(cand["_id"]), "category": cand["category"],
                         "sub_category": cand["sub_category"], "colour": cand["colour"],
                         "image_url": f"/candidates/{cand['_id']}/image"},
                "verdict": advice["verdict"], "good_outfits": advice["good_outfits"],
                "reasons": advice["reasons"], "best": [outfit_out(o, by_id) for o in advice["best"]]}

    functions = (list_wardrobe, suggest_outfits, score_outfit, buy_advice_last_scan)
    if attachments is None:
        return {f.__name__: f for f in functions}

    def capture(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            seen = {item["id"] for item in attachments}
            for item in _image_attachments(result):
                if item["id"] not in seen:
                    attachments.append(item)
                    seen.add(item["id"])
            return result
        return wrapped

    return {f.__name__: capture(f) for f in functions}


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
