"""
Men / women: which items a user is shown, and the gendered rows of the team's rules.

    item_gender(item)            the item's own label (men / women / unisex), else the team
                                 table mappings/gender_sub_categories.csv, else unisex
    shown(user_gender)           the item genders this user sees: {gender, "unisex"}
    for_gender(table, g, key)    a rule CSV for this gender: neutral rows + this gender's
                                 rows; a gendered row replaces the neutral row with the same key

The user's own wardrobe is never filtered: gender only changes what the app suggests from
outside it (catalogue, shops, listings), the order of the pickers and the team's rules.
"""

from functools import lru_cache

import pandas as pd

from item_images import ROOT

MAP_DIR = ROOT / "mappings"
TABLE = "gender_sub_categories.csv"
GENDERS = ("men", "women")              # a user is one of these
VALUES = ("men", "women", "unisex")     # an item is one of these
# every spelling the sources use (Fashion Product, local labels, shops); kids' labels are
# not our users, so they fall back to the table
SPELLINGS = {"men": "men", "man": "men", "male": "men", "homme": "men", "hommes": "men",
             "women": "women", "woman": "women", "female": "women", "femme": "women",
             "femmes": "women", "unisex": "unisex"}


def normalise(value):
    """men / women / unisex, or "" when the label is missing or unusable."""
    return SPELLINGS.get(str(value or "").strip().lower(), "")


@lru_cache(maxsize=4)
def load_table(map_dir=MAP_DIR):
    """{sub_category: men / women / unisex} from the team's table."""
    df = pd.read_csv(map_dir / TABLE, dtype=str, keep_default_na=False)
    return dict(zip(df["sub_category"], df["gender"]))


def item_gender(item, table=None):
    """The item's own label first, then the team table for its sub_category, else unisex."""
    table = table if table is not None else load_table()
    return normalise(item.get("gender")) or table.get(item.get("sub_category") or "", "unisex")


def item_genders(labels, subs, table=None):
    """item_gender for whole columns (the 300k-row catalogue)."""
    table = table if table is not None else load_table()
    own = labels.fillna("").map(normalise)
    from_table = subs.fillna("").map(table).fillna("unisex")
    return own.where(own != "", from_table)


def shown(user_gender):
    """The item genders a user sees, or None (no gender yet = no filter)."""
    return {user_gender, "unisex"} if user_gender in GENDERS else None


def for_gender(table, gender, key):
    """Neutral rows + this gender's rows of a rule table. When both exist for the same
    key (key(row) on itertuples rows), the gendered row wins. A table without a
    `gender` column is returned as it is (every row is neutral)."""
    if "gender" not in table.columns:
        return table
    table = table[table["gender"].isin({"", gender or ""})]
    keys = [key(r) for r in table.itertuples()]
    table = table.assign(_gendered=table["gender"] != "", _key=keys)
    table = table.sort_values("_gendered", kind="stable").drop_duplicates("_key", keep="last")
    return table.drop(columns=["_gendered", "_key"]).sort_index()
