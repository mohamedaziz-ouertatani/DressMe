"""
Virtual try-on: the user's photo + wardrobe items (and/or a friperie scan) ->
a picture of the user wearing them (see tryon.py for the engine).

The person photo is kept in memory only: never saved, never put on white (the
model needs the person and the background as they are). The result is
returned inline (base64) and not stored either.
"""

import base64
import io
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..events import log_event
from ..security import gendered_user
from ..tryon import KIND, TryOnBusy, TryOnUnavailable, describe, plan
from ..wardrobe import to_compat
from .items import open_photo, own_item

router = APIRouter(tags=["try-on"])
log = logging.getLogger("uvicorn.error")   # shown in the uvicorn terminal


def item_photo(request, user, doc):
    """The item's cleaned photo: a file for wardrobe items, inside the document for scans."""
    if doc.get("photo"):
        return Image.open(io.BytesIO(bytes(doc["photo"]))).convert("RGB")
    path = request.app.state.settings.storage_dir / str(user["_id"]) / f"{doc['_id']}.jpg"
    if not path.exists():
        raise HTTPException(404, "Image missing")
    return Image.open(path).convert("RGB")


def as_data_url(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


@router.post("/tryon")
async def try_on(request: Request, photo: UploadFile = File(...),
                 item_ids: list[str] = Form(default=[]), candidate_id: str | None = Form(default=None),
                 user=Depends(gendered_user)):
    """Dress the person in `photo` with the given wardrobe items and/or scanned
    candidate. Shoes, bags and accessories are skipped (the model can't draw
    them). A garment no Space could put on is listed in `failed` and the
    others are still dressed; 502 only when none could be put on."""
    engine = request.app.state.tryon
    settings = request.app.state.settings
    if engine is None:
        raise HTTPException(503, "Virtual try-on is switched off (TRYON_ENGINE=off)")
    docs = [own_item(request, user, i) for i in dict.fromkeys(item_ids)]   # 404 if not theirs
    if candidate_id:
        docs.append(own_item(request, user, candidate_id, collection="candidates"))
    if not docs:
        raise HTTPException(422, "Pick at least one piece to try on")
    from .outfits import rules_of
    why = compatibility.clashes([to_compat(d) for d in docs], rules_of(user))
    if why:
        raise HTTPException(422, "These pieces can't be worn together: " + "; ".join(why))
    garments, skipped = plan(docs)
    if not garments:
        raise HTTPException(422, "Try-on works for clothes only (not shoes, bags or accessories)")
    if len(garments) > settings.tryon_max_garments:
        raise HTTPException(422, f"Try on at most {settings.tryon_max_garments} garments at once")

    result = await open_photo(photo, settings)
    applied, failed, reasons = [], [], []
    for doc in garments:
        try:
            result = await run_in_threadpool(
                engine.dress, result, item_photo(request, user, doc), KIND[doc["category"]],
                describe(doc))
        except TryOnUnavailable as e:
            raise HTTPException(503, str(e))
        except TryOnBusy as e:
            # e.g. no working Space can dress trousers: skip this piece, keep
            # dressing the others; it is listed in `failed`
            log.warning("try-on failed (%s garment): %s", KIND[doc["category"]], e)
            failed.append(str(doc["_id"]))
            reasons.append(str(e))
            continue
        applied.append(str(doc["_id"]))
    if not applied:                          # nothing made: the app falls back to its overlay
        raise HTTPException(502, " / ".join(reasons))
    log_event(request.app.state.db, "tryon", user["_id"], garments=len(applied))
    return {"image": as_data_url(result), "applied": applied, "failed": failed, "skipped": skipped}
