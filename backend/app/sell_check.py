"""
The seller's check before Send (POST /listings/sell/check, routers/listings.py).

Two engines from src/phase4, both reading the FashionCLIP vector of the photo:
  - label_check.py: when the title names a brand, does the photo look like that
    brand AND is the asked price near the usual one? If BOTH disagree, the app asks
    for a photo that shows the label or logo. It is a request to the seller, never a
    verdict, and it is never shown to buyers.
  - condition_hint.py: a "looks new" score. Kept in the API answer only: sellers
    have no condition selector, so the app does not show it.

Nothing here is stored. The price band is computed the way GET /price-estimate
computes it for a seller's listing (friperie channel, the analysed category),
and only its median is used.

PhotoCache keeps the cleaned photo and its analysis in memory for a few minutes,
by (user, file hash), so the /listings/sell that follows a /check with the same
file does not clean and analyse it a second time (~3-5 s each).
"""

import copy
import hashlib
import time

from . import ml  # noqa: F401  (puts src/ on the import path)
import price as price_model

from .db import vector_from_bson
from .routers.items import analyse, read_photo

CACHE_SECONDS = 600        # a seller usually sends within a few minutes of the check
CACHE_SIZE = 32            # photos kept at most (each ~1 MB in memory)


class PhotoCache:
    """{(user id, sha256 of the file): (time, cleaned photo, analysis)}, in memory only."""

    def __init__(self, seconds=CACHE_SECONDS, size=CACHE_SIZE):
        self.seconds, self.size, self.entries = seconds, size, {}

    def get(self, key):
        hit = self.entries.get(key)
        if hit is None or time.monotonic() - hit[0] >= self.seconds:
            self.entries.pop(key, None)
            return None
        return hit[1].copy(), copy.deepcopy(hit[2])     # copies: the caller may change them

    def put(self, key, img, analysed):
        now = time.monotonic()
        self.entries = {k: v for k, v in self.entries.items() if now - v[0] < self.seconds}
        while len(self.entries) >= self.size:            # the oldest goes first
            self.entries.pop(next(iter(self.entries)))
        self.entries[key] = (now, img.copy(), copy.deepcopy(analysed))


def photo_cache(request):
    cache = getattr(request.app.state, "seller_photos", None)
    if cache is None:
        cache = request.app.state.seller_photos = PhotoCache()
    return cache


async def cleaned_and_analysed(photo, user, request):
    """(cleaned photo, analysis) of an uploaded file, from the cache when the same
    user sent the same file a few minutes ago. Same errors as read_photo (400 / 413)."""
    limit = request.app.state.settings.max_upload_mb * 1024 * 1024
    data = await photo.read(limit + 1)
    await photo.seek(0)                                  # read_photo reads it again
    key = (str(user["_id"]), hashlib.sha256(data).hexdigest())
    cache = photo_cache(request)
    hit = cache.get(key)
    if hit is not None:
        return hit
    img = await read_photo(photo, request)
    analysed = analyse(img, user, request)
    cache.put(key, img, analysed)
    return img, analysed


def friperie_median(request, vector, category):
    """The median of the friperie band, as GET /price-estimate gives it for a seller's
    listing; None when there is no price model or it cannot price this piece."""
    model = request.app.state.price
    if model is None or vector is None:
        return None
    band = model.estimate(vector, category=category, channel="friperie", rules=price_model.load_rules())
    return band.get("median") if band else None


def check(request, analysed, title, asking_price):
    """{"label_check": ..., "condition_hint": ...}; null for an engine that is not loaded."""
    vector = vector_from_bson(analysed.get("vector"))
    label_check = request.app.state.label_check
    condition_hint = request.app.state.condition_hint
    if vector is None:
        return {"label_check": None, "condition_hint": None}
    median = friperie_median(request, vector, analysed.get("category")) if label_check else None
    return {
        # listings have no description: the brand is read from the title only
        "label_check": label_check.check(vector, title, "", asking_price=asking_price,
                                         estimate_median=median) if label_check else None,
        "condition_hint": condition_hint.hint(vector) if condition_hint else None,
    }
