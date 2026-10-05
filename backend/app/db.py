"""
MongoDB access (pymongo). Collections:
    users       email, password_hash, profile
    items       one wardrobe item per document (always filtered by user_id)
    candidates  photos analysed with /analyze, not in the wardrobe (the cleaned
                JPEG is in `photo`); deleted automatically after 24 h (TTL index)
    chats       chat history per user
    events      usage log for the admin dashboard (see events.py)
    outfit_feedback  per-user like/dislike feedback with vector snapshots
    listings    shop products to buy, shared by all users (app/listings.py,
                filled by src/collect_listings.py)
    listing_runs  one line per collector run and source (admin page)
    listing_jobs  collector runs started from the admin page (app/jobs.py)
    source_checks the read-only shop checks run from Admin > Listings

FashionCLIP vectors are stored as raw float16 bytes (1 KB per item).
"""

import numpy as np
from bson import Binary, ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, MongoClient


def connect(settings):
    client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000, tz_aware=True)
    db = client[settings.mongo_db]
    db.users.create_index("email", unique=True)
    db.items.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    db.candidates.create_index("created_at", expireAfterSeconds=24 * 3600)
    db.chats.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    db.events.create_index([("at", ASCENDING), ("type", ASCENDING)])
    db.outfit_feedback.create_index(
        [("user_id", ASCENDING), ("outfit_key", ASCENDING)], unique=True)
    db.listings.create_index([("source_id", ASCENDING), ("external_id", ASCENDING)], unique=True)
    db.listings.create_index([("status", ASCENDING), ("in_stock", ASCENDING), ("category", ASCENDING)])
    db.listing_runs.create_index([("source_id", ASCENDING), ("finished_at", ASCENDING)])
    db.listing_jobs.create_index([("started_at", ASCENDING)])
    db.source_checks.create_index([("source_id", ASCENDING), ("checked_at", ASCENDING)])
    return db


def vector_to_bson(vector):
    return Binary(np.asarray(vector, np.float16).tobytes())


def vector_from_bson(data):
    return np.frombuffer(bytes(data), np.float16).astype(np.float32) if data else None


def object_id(value):
    """A string id from the URL as an ObjectId, or None if it is not valid."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None
