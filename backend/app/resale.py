"""
A friperie price for something the user wants to sell (the Seller assistant, AGENTS.md).

Look-alike listings (FashionCLIP, same category) give the prices:
  - friperie sellers' listings count as they are;
  - shop listings are new clothes, so their price is multiplied by the team's
    second-hand factor for that category (mappings/resale_pricing.csv, REVIEW);
  - once there are enough friperie look-alikes (min_friperie), shop prices are left out.
The answer is a range (25th-75th percentile) and the median, rounded to 1 TND, with
the listings it came from so the user can see why.
"""

import csv

import numpy as np

from .config import ROOT
from .listings import SELLERS
from .vocab import CATEGORIES

RULES_CSV = ROOT / "mappings" / "resale_pricing.csv"
SETTINGS = ("neighbours", "min_friperie")
EXAMPLES = 5           # listings shown with a price hint


def load_rules(path=RULES_CSV):
    """The team's factors and settings. Anything unknown or missing stops with an error."""
    factor, settings = {}, {}
    with open(path, encoding="utf-8", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            kind, name, value = row["kind"].strip(), row["name"].strip(), row["value"].strip()
            if kind == "factor":
                if name != "*" and name not in CATEGORIES:
                    raise ValueError(f"{path.name} line {line}: unknown category {name!r}")
                factor[name] = float(value)
            elif kind == "setting":
                if name not in SETTINGS:
                    raise ValueError(f"{path.name} line {line}: unknown setting {name!r}")
                settings[name] = int(value)
            else:
                raise ValueError(f"{path.name} line {line}: unknown kind {kind!r}")
    if "*" not in factor:
        raise ValueError(f"{path.name}: needs a default factor row (name = *)")
    for name in SETTINGS:
        if name not in settings:
            raise ValueError(f"{path.name}: missing setting {name}")
    return {"factor": factor, **settings}


def price_range(hits, rules):
    """The price range from look-alike listings (rows of ListingIndex.search), or None."""
    priced = [h for h in hits if h.get("price_tnd") and h["price_tnd"] > 0]
    friperie = [h for h in priced if h["source_id"] == SELLERS]
    shops = [h for h in priced if h["source_id"] != SELLERS]
    used = friperie if len(friperie) >= rules["min_friperie"] else friperie + shops
    if not used:
        return None
    factor = rules["factor"]

    def resale(h):
        if h["source_id"] == SELLERS:
            return float(h["price_tnd"])
        return h["price_tnd"] * factor.get(h["category"], factor["*"])

    prices = np.array([resale(h) for h in used])
    low, median, high = (int(round(float(np.percentile(prices, q)))) for q in (25, 50, 75))
    shop_used = any(h["source_id"] != SELLERS for h in used)
    based_on = "both" if friperie and shop_used else "shops" if shop_used else "friperie"
    return {"low": low, "high": high, "median": median, "based_on": based_on, "count": len(used),
            "examples": [{"title": h.get("title", ""), "source_id": h["source_id"],
                          "price_tnd": h["price_tnd"], "resale_price": int(round(resale(h))),
                          "similarity": h.get("score"), "snapshot": bool(h.get("snapshot"))}
                         for h in used[:EXAMPLES]]}
