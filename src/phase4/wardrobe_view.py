"""
The Wardrobe view (step 5 of the upgrade): what the wear log says about the pieces. Pure functions: data in,
data out, no MongoDB, no files except the rules CSV.

    worn_summary(items, wear_entries, today, window_days, grace_days) ->
        {"worn_lately": [{"item_id", "last_worn_on"}, ...],   worn within the last `window_days` days, most recent first
         "never_worn":  [item id, ...],                       no wear entry at all, owned for more than `grace_days`
         "window_days": ..., "grace_days": ...}

`items` = dicts with "id" and "created_at" (a datetime; a date also works). `wear_entries` = dicts with "item_ids"
and "worn_on" ("YYYY-MM-DD", the date in Africa/Tunis, as the wear log stores it). `today` = a date, the Tunis
date. The two numbers are the team's, in mappings/wardrobe_view.csv (REVIEW), never in this file.
"""

import csv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from item_images import ROOT

RULES_CSV = ROOT / "mappings" / "wardrobe_view.csv"
REQUIRED = ("window_days", "grace_days")
TUNIS = ZoneInfo("Africa/Tunis")


def load_rules(path=RULES_CSV):
    """{name: whole number of days} from the team's file (read at each call: an edit applies at once)."""
    with open(path, encoding="utf-8", newline="") as f:
        rules = {row["name"]: int(float(row["value"])) for row in csv.DictReader(f)}
    missing = [name for name in REQUIRED if name not in rules]
    if missing:
        raise ValueError(f"{path}: missing rows {missing}")
    return rules


def owned_since(item):
    """The Tunis date the piece was added."""
    created = item["created_at"]
    if isinstance(created, datetime):
        created = created.astimezone(TUNIS) if created.tzinfo else created
        return created.date()
    return created


# TODO(step 5): the first version counts a piece as worn when it is in a wear entry, nothing more. The full
# version: how often each piece is worn (a frequency, not only the last day), the cost per wear (the price paid
# is in the decisions log), a "sell suggestions" list from the never-worn pieces (the Seller assistant already
# has pieces_to_sell), and a rule for seasonal pieces that rest on purpose.
def worn_summary(items, wear_entries, today, window_days, grace_days):
    last_worn = {}
    for entry in wear_entries:
        for item_id in entry["item_ids"]:
            if entry["worn_on"] > last_worn.get(item_id, ""):          # ISO dates compare as text
                last_worn[item_id] = entry["worn_on"]
    since = (today - timedelta(days=window_days)).isoformat()
    lately = [{"item_id": i["id"], "last_worn_on": last_worn[i["id"]]}
              for i in items if i["id"] in last_worn and last_worn[i["id"]] >= since]
    lately.sort(key=lambda w: w["last_worn_on"], reverse=True)          # stable: ties keep the wardrobe order
    never = sorted((i for i in items if i["id"] not in last_worn and (today - owned_since(i)).days > grace_days),
                   key=owned_since)                                      # the longest-waiting first
    return {"worn_lately": lately, "never_worn": [i["id"] for i in never],
            "window_days": window_days, "grace_days": grace_days}
