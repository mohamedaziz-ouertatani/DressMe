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
from ..tryon import BASIC_KINDS, TryOnBusy, TryOnUnavailable, describe, kind_of, plan
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


@router.get("/tryon/info")
def try_on_info(request: Request, user=Depends(gendered_user)):
    """What the try-on page needs before it starts: is the AI on, does the photo leave
    this computer (privacy note), and about how long one garment takes (its progress bar)."""
    engine = request.app.state.tryon
    return {"enabled": engine is not None,
            "private": bool(getattr(engine, "private", False)),
            "seconds_per_garment": getattr(engine, "seconds_per_garment", 60),
            "max_garments": request.app.state.settings.tryon_max_garments,
            "looks": bool(getattr(engine, "can_copy_looks", False)),     # "Try this look"
            # what it can put on: upper / lower / overall, + shoes / glasses for the local engine
            "kinds": sorted(getattr(engine, "kinds", BASIC_KINDS)) if engine else []}


async def try_on_look(request, engine, settings, user, photo, look):
    """Dress the person in `photo` with the whole outfit someone wears in `look`, shoes
    included (the service does the shoes, then the clothes). Only engines that can (the
    local IDM-VTON service). Neither photo is kept."""
    if not getattr(engine, "can_copy_looks", False):
        raise HTTPException(422, "Trying on a look from a photo needs the local try-on engine")
    person = await open_photo(photo, settings)
    reference = await open_photo(look, settings)
    try:
        result = await run_in_threadpool(engine.dress, person, reference, "full", "full outfit")
    except TryOnUnavailable as e:
        raise HTTPException(503, str(e))
    except TryOnBusy as e:
        raise HTTPException(502, str(e))
    log_event(request.app.state.db, "tryon", user["_id"], look=True)
    return {"image": as_data_url(result), "applied": ["look"], "failed": [], "skipped": []}


@router.post("/tryon")
async def try_on(request: Request, photo: UploadFile = File(...),
                 item_ids: list[str] = Form(default=[]), candidate_id: str | None = Form(default=None),
                 look: UploadFile | None = File(default=None),
                 user=Depends(gendered_user)):
    """Dress the person in `photo` with the given wardrobe items and/or scanned
    candidate. What the engine can't put on is skipped (bags, belts, jewellery always;
    shoes and glasses unless the engine lists them in its `kinds`). A garment the
    engine failed on is listed in `failed` and the others are still dressed; 502
    only when none could be put on."""
    engine = request.app.state.tryon
    settings = request.app.state.settings
    if engine is None:
        raise HTTPException(503, "Virtual try-on is switched off (TRYON_ENGINE=off)")
    if look is not None:                     # "Try this look": the whole outfit from a photo
        return await try_on_look(request, engine, settings, user, photo, look)
    docs = [own_item(request, user, i) for i in dict.fromkeys(item_ids)]   # 404 if not theirs
    if candidate_id:
        docs.append(own_item(request, user, candidate_id, collection="candidates"))
    if not docs:
        raise HTTPException(422, "Pick at least one piece to try on")
    from .outfits import rules_of
    why = compatibility.clashes([to_compat(d) for d in docs], rules_of(user))
    if why:
        raise HTTPException(422, "These pieces can't be worn together: " + "; ".join(why))
    garments, skipped = plan(docs, getattr(engine, "kinds", BASIC_KINDS))
    if not garments:
        raise HTTPException(422, "None of these pieces can be tried on (bags and most accessories can't)")
    if len(garments) > settings.tryon_max_garments:
        raise HTTPException(422, f"Try on at most {settings.tryon_max_garments} garments at once")

    result = await open_photo(photo, settings)
    applied, failed, reasons = [], [], []
    for doc in garments:
        try:
            result = await run_in_threadpool(
                engine.dress, result, item_photo(request, user, doc), kind_of(doc),
                describe(doc))
        except TryOnUnavailable as e:
            raise HTTPException(503, str(e))
        except TryOnBusy as e:
            # e.g. no working Space can dress trousers: skip this piece, keep
            # dressing the others; it is listed in `failed`
            log.warning("try-on failed (%s garment): %s", kind_of(doc), e)
            failed.append(str(doc["_id"]))
            reasons.append(str(e))
            continue
        applied.append(str(doc["_id"]))
    if not applied:                          # nothing made: the app falls back to its overlay
        raise HTTPException(502, " / ".join(reasons))
    log_event(request.app.state.db, "tryon", user["_id"], garments=len(applied))
    return {"image": as_data_url(result), "applied": applied, "failed": failed, "skipped": skipped}
