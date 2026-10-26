"""
POST /search: find pieces of the user's OWN wardrobe by words or by a photo (step 3b).

The pure logic is src/phase4/search.py (normalise the words, cosine similarity, the cut); this route only
loads the user's items, asks FashionCLIP for the query vector and answers. The assistant's search_wardrobe tool
(step 3d) calls the same `find_owned` (one function, two callers).

    multipart form: exactly one of `text` (1 to 120 characters) or `photo`; optional `limit` (1 to 20)
    answer: {mode, results: [{item, similarity, close}], nothing_close, skipped_no_vector}

A photo is cleaned and encoded like "add item", but NOTHING is saved: no file, no item, no candidate.
The log keeps only the mode, the number of results, nothing_close and the time: never the words or the photo.
"""

import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from .. import ml  # noqa: F401  (puts src/ on the import path)
import search

from ..db import vector_from_bson
from ..events import log_event
from ..security import current_user
from ..wardrobe import item_out
from .items import read_photo

router = APIRouter(tags=["search"])
MAX_TEXT = 120


def find_owned(db, user_id, vector, cut, limit, rules, category=None):
    """The user's own pieces nearest to `vector` (search.rank_owned). When none is close, only the nearest
    `closest_anyway` are kept. Only this user's pieces are ever loaded: the user filter is in the query itself."""
    query = {"user_id": user_id, **({"category": category} if category else {})}
    pieces = [{**d, "vector": vector_from_bson(d.get("vector"))} for d in db.items.find(query)]
    ranked = search.rank_owned(vector, pieces, cut, limit)
    if ranked["nothing_close"]:                          # say so, and still show the nearest few
        ranked["results"] = ranked["results"][:int(rules["closest_anyway"])]
    return ranked


@router.post("/search")
async def search_own_pieces(request: Request, text: str | None = Form(None), photo: UploadFile | None = File(None),
                            limit: int | None = Form(None, ge=1, le=20), user=Depends(current_user)):
    started = time.perf_counter()
    text = (text or "").strip()
    # the codes are what the app translates; no sentence from the server is ever shown
    if photo is not None and text:
        raise HTTPException(400, "search_text_and_photo")
    if photo is None and not text:
        raise HTTPException(400, "search_need_text_or_photo")
    if len(text) > MAX_TEXT:
        raise HTTPException(400, "search_text_too_long")

    rules = search.load_rules()
    analyzer = request.app.state.analyzer
    if photo is None:
        mode, cut = "text", rules["text_cut"]
        query = search.normalise_query(text, search.load_terms())
        if not query:
            raise HTTPException(400, "search_text_no_words")
        vector = analyzer.embed_text(query)
    else:
        mode, cut = "photo", rules["photo_cut"]
        vector = analyzer.embed_image(await read_photo(photo, request))      # cleaned, never saved

    ranked = find_owned(request.app.state.db, user["_id"], vector, cut, limit or int(rules["default_limit"]), rules)
    results = ranked["results"]

    log_event(request.app.state.db, "search", user["_id"], mode=mode, results=len(results),
              nothing_close=ranked["nothing_close"], ms=round((time.perf_counter() - started) * 1000))
    return {"mode": mode,
            "results": [{"item": item_out(r["item"]), "similarity": round(r["similarity"], 4), "close": r["close"]}
                        for r in results],
            "nothing_close": ranked["nothing_close"], "skipped_no_vector": ranked["skipped_no_vector"]}
