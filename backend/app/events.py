"""
Usage log for the admin dashboard. Candidates disappear after 24 h, so every
action worth counting is written here once:
    upload      an item added to a wardrobe
    scan        a photo analysed with /analyze
    verdict     a buy-advice answer        (extra: verdict = buy / think / skip)
    correction  a user corrected an item   (extra: fields = [...])
    chat        a chat message answered
"""

from datetime import datetime, timezone

EVENT_TYPES = ["upload", "scan", "verdict", "correction", "chat"]


def log_event(db, kind, user_id, **extra):
    db.events.insert_one({"type": kind, "user_id": user_id, "at": datetime.now(timezone.utc), **extra})
