"""Deleting an account: the one place that does it. The admin route (DELETE /admin/users/{id}) and the
user's own (DELETE /me) both call `delete_account`, so they can never forget a different set of data."""

import shutil

from .db import USER_COLLECTIONS
from .routers.listings import delete_seller_listings


def delete_account(request, user):
    """Everything the user owns, then the user: every per-user collection (db.USER_COLLECTIONS), the seller
    listings and their pictures, the user's photo folder."""
    db = request.app.state.db
    for coll in USER_COLLECTIONS:
        db[coll].delete_many({"user_id": user["_id"]})
    delete_seller_listings(db, request.app.state.settings.storage_dir, user["_id"])
    request.app.state.listing_index.invalidate()
    db.users.delete_one({"_id": user["_id"]})
    shutil.rmtree(request.app.state.settings.storage_dir / str(user["_id"]), ignore_errors=True)
