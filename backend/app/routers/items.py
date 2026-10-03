"""
Wardrobe items: upload a photo (analysed by the models), list, correct, delete.
Also /analyze: a friperie photo analysed WITHOUT adding it to the wardrobe
(a "candidate", kept 24 h for /buy-advice and /similar).
"""

import io
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError

from ..db import object_id, vector_to_bson
from ..events import log_event
from ..schemas import ItemUpdate
from ..security import current_user
from ..vocab import SUB_PARENT
from ..wardrobe import fields_from_analysis, item_out

router = APIRouter(tags=["wardrobe"])


async def read_photo(upload, settings):
    """The uploaded file as a PIL image; 400 if it is not a picture or too big."""
    data = await upload.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Photo larger than {settings.max_upload_mb} MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "This file is not a readable picture")
    # phones store portrait photos as landscape pixels + an EXIF "rotate" tag:
    # apply it, or the models (and the saved photo) would see the item lying on its side
    return ImageOps.exif_transpose(img).convert("RGB")


def analyse(img, user, request):
    analysis = request.app.state.analyzer.analyze(img)
    fields, predicted = fields_from_analysis(analysis)
    return {"user_id": user["_id"], **fields, "predicted": predicted,
            "vector": vector_to_bson(analysis["vector"]),
            "coverage": None, "season": [], "usage": [], "corrected": [],
            "created_at": datetime.now(timezone.utc)}


def own_item(request, user, item_id, collection="items"):
    """The user's item, or 404 (also for other users' items: never reveal they exist)."""
    oid = object_id(item_id)
    doc = oid and request.app.state.db[collection].find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(404, "Item not found")
    return doc


def apply_update(doc, body: ItemUpdate):
    """Validated corrections -> a $set dict; the sub_category must fit the category."""
    changes = body.model_dump(exclude_unset=True)
    category = changes.get("category", doc["category"])
    sub = changes.get("sub_category", doc["sub_category"])
    if "category" in changes and "sub_category" not in changes and SUB_PARENT.get(sub) != category:
        changes["sub_category"] = ""          # the old sub_category no longer fits
        sub = ""
    if sub and SUB_PARENT.get(sub) != category:
        raise HTTPException(422, f"sub_category '{sub}' is not a kind of '{category}'")
    corrected = sorted(set(doc.get("corrected", [])) | set(changes))
    return {**changes, "corrected": corrected}


@router.post("/items", status_code=201)
async def add_item(request: Request, photo: UploadFile = File(...), user=Depends(current_user)):
    settings = request.app.state.settings
    img = await read_photo(photo, settings)
    doc = analyse(img, user, request)
    doc["_id"] = ObjectId()
    folder = settings.storage_dir / str(user["_id"])
    folder.mkdir(parents=True, exist_ok=True)
    img.thumbnail((settings.max_image_side, settings.max_image_side))
    img.save(folder / f"{doc['_id']}.jpg", quality=85)
    request.app.state.db.items.insert_one(doc)
    log_event(request.app.state.db, "upload", user["_id"], category=doc["category"])
    return item_out(doc)


@router.get("/items")
def list_items(request: Request, category: str | None = None, user=Depends(current_user)):
    query = {"user_id": user["_id"]}
    if category:
        query["category"] = category
    return [item_out(d) for d in request.app.state.db.items.find(query).sort("created_at", 1)]


@router.get("/items/{item_id}")
def get_item(item_id: str, request: Request, user=Depends(current_user)):
    return item_out(own_item(request, user, item_id))


@router.patch("/items/{item_id}")
def update_item(item_id: str, body: ItemUpdate, request: Request, user=Depends(current_user)):
    doc = own_item(request, user, item_id)
    changes = apply_update(doc, body)
    request.app.state.db.items.update_one({"_id": doc["_id"]}, {"$set": changes})
    log_event(request.app.state.db, "correction", user["_id"],
              fields=sorted(set(changes) - {"corrected"}))
    return item_out(own_item(request, user, item_id))


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, request: Request, user=Depends(current_user)):
    doc = own_item(request, user, item_id)
    request.app.state.db.items.delete_one({"_id": doc["_id"]})
    path = request.app.state.settings.storage_dir / str(user["_id"]) / f"{doc['_id']}.jpg"
    path.unlink(missing_ok=True)


@router.get("/items/{item_id}/image")
def item_image(item_id: str, request: Request, user=Depends(current_user)):
    doc = own_item(request, user, item_id)
    path = request.app.state.settings.storage_dir / str(user["_id"]) / f"{doc['_id']}.jpg"
    if not path.exists():
        raise HTTPException(404, "Image missing")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/analyze", status_code=201)
async def analyze(request: Request, photo: UploadFile = File(...), user=Depends(current_user)):
    """Analyse a photo without adding it to the wardrobe (e.g. in a friperie)."""
    img = await read_photo(photo, request.app.state.settings)
    doc = analyse(img, user, request)
    doc["_id"] = request.app.state.db.candidates.insert_one(doc).inserted_id
    log_event(request.app.state.db, "scan", user["_id"], category=doc["category"])
    return item_out(doc, kind="candidates")

