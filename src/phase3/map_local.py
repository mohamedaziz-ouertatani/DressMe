"""
Map our own photos (wardrobe / friperie) to the unified schema: data/processed/local.csv

These are the only pictures from the real DressMe setting, so they are kept for
the TEST set only (merge_and_split.py enforces it). Guide for taking and
labelling them: LOCAL_PHOTOS.md.

Folder (inside data/, never committed):
    data/raw/Local/photos/<contributor>/<any name>.jpg   one item per photo
    data/raw/Local/labels.csv                            one row per photo, filled by hand

Steps:
    python src/phase3/map_local.py --init   # adds a row to labels.csv for every new photo
    (fill in labels.csv: category, colour, ...; a row with no category is skipped)
    python src/phase3/map_local.py          # checks every label, then writes local.csv

Labels are checked against the same vocabularies as the other datasets
(mappings/*.csv). Any error stops the script with the line number in
labels.csv, so a wrong label never reaches the merged file. Multi-value
fields (season, usage, style) use "|", e.g. summer|mid-season.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
LOCAL = DATA / "raw" / "Local"
PHOTOS = LOCAL / "photos"
LABELS = LOCAL / "labels.csv"
OUT_PATH = DATA / "processed" / "local.csv"
MAPPINGS = ROOT / "mappings"

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}
MIN_SIDE = 224   # smaller photos are refused: the models work at 224 px

# columns of labels.csv, in the order the team fills them in
LABEL_COLUMNS = ["file", "contributor", "source", "category", "sub_category",
                 "primary_colour", "secondary_colour", "pattern", "season", "usage", "style",
                 "coverage", "gender", "outfit_id", "labelled_by", "checked_by", "note"]

# allowed values (the same as the unified schema in CLAUDE.md)
SOURCES = {"wardrobe", "friperie"}
CATEGORIES = {"top", "bottom", "dress", "outerwear", "shoes", "bag", "accessory",
              "traditional", "swimwear"}
PATTERNS = {"solid", "striped", "checked", "floral", "printed"}
SEASONS = {"summer", "winter", "mid-season"}
USAGES = {"casual", "formal", "sport", "wedding", "eid", "work"}
STYLES = {"classic", "streetwear", "modest", "sporty", "trendy"}
GENDERS = {"men": "Men", "women": "Women", "unisex": "Unisex"}  # written like Fashion Product
SUB_PARENT = pd.read_csv(MAPPINGS / "sub_category_vocabulary.csv").set_index(
    "sub_category")["category"].to_dict()
COLOURS = set(pd.read_csv(MAPPINGS / "colour_palette.csv")["colour"])
ANONYMOUS_ID = re.compile(r"^[a-z0-9_-]{1,12}$")   # e.g. c01: never a name or an e-mail


def photo_files():
    """Every picture under photos/, as a path relative to photos/ (with / separators)."""
    return sorted(p.relative_to(PHOTOS).as_posix() for p in PHOTOS.rglob("*")
                  if p.is_file() and p.suffix.lower() in IMAGE_TYPES)


def read_labels():
    if not LABELS.exists():
        return pd.DataFrame(columns=LABEL_COLUMNS)
    df = pd.read_csv(LABELS, dtype=str, keep_default_na=False)
    if missing := [c for c in LABEL_COLUMNS if c not in df]:
        sys.exit(f"ERROR: {LABELS} has no column(s) {missing}. Run --init to add them.")
    return df[LABEL_COLUMNS].apply(lambda col: col.str.strip())


def init():
    """Add a row for every photo that labels.csv does not list yet."""
    if not PHOTOS.exists():
        PHOTOS.mkdir(parents=True)
        print(f"Created {PHOTOS}: put the photos there, one folder per contributor (e.g. c01/)")
    df = read_labels()
    new = [f for f in photo_files() if f not in set(df["file"])]
    rows = pd.DataFrame({"file": new}, columns=LABEL_COLUMNS).fillna("")
    # the first folder is the contributor's anonymous id
    rows["contributor"] = [f.split("/")[0].lower() if "/" in f else "" for f in new]
    heic = [p.name for p in PHOTOS.rglob("*") if p.suffix.lower() in {".heic", ".heif"}]
    if heic:
        print(f"WARNING: {len(heic)} HEIC photos skipped (e.g. {heic[0]}): export them as JPEG")
    out = pd.concat([df, rows], ignore_index=True)
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(LABELS, index=False, encoding="utf-8")
    print(f"{LABELS}: {len(out)} rows ({len(new)} new photos added, labels still to fill in)")


def check_row(r):
    """All the problems of one labelled row, as a list of messages."""
    errors = []

    def one_of(field, allowed, required=False):
        value = r[field]
        if value == "":
            if required:
                errors.append(f"{field} is empty")
        elif value not in allowed:
            errors.append(f"{field} '{value}' is not allowed (choose from: {', '.join(sorted(allowed))})")

    def many_of(field, allowed):
        for value in filter(None, r[field].split("|")):
            if value not in allowed:
                errors.append(f"{field} '{value}' is not allowed (choose from: {', '.join(sorted(allowed))})")

    if not ANONYMOUS_ID.match(r["contributor"]):
        errors.append(f"contributor '{r['contributor']}' must be an anonymous id like c01 "
                      "(lowercase letters, digits, - or _; never a name or e-mail)")
    one_of("source", SOURCES, required=True)
    one_of("category", CATEGORIES, required=True)
    one_of("sub_category", SUB_PARENT)
    if r["sub_category"] in SUB_PARENT and SUB_PARENT[r["sub_category"]] != r["category"]:
        errors.append(f"sub_category '{r['sub_category']}' is a kind of "
                      f"'{SUB_PARENT[r['sub_category']]}', not '{r['category']}'")
    one_of("primary_colour", COLOURS)
    one_of("secondary_colour", COLOURS)
    if r["secondary_colour"] and r["secondary_colour"] == r["primary_colour"]:
        errors.append("secondary_colour is the same as primary_colour (leave it empty)")
    if r["secondary_colour"] and not r["primary_colour"]:
        errors.append("secondary_colour is set but primary_colour is empty")
    one_of("pattern", PATTERNS)
    many_of("season", SEASONS)
    many_of("usage", USAGES)
    many_of("style", STYLES)
    one_of("coverage", {"1", "2", "3", "4", "5"})
    one_of("gender", GENDERS)
    return errors


def check_photo(path):
    """Problems with the picture file itself, and its MD5."""
    if not path.exists():
        return ["photo not found in photos/ (renamed or moved?)"], None
    try:
        with Image.open(path) as img:
            img.load()
            side = min(img.size)
    except (UnidentifiedImageError, OSError):
        return ["photo cannot be opened (export it as JPEG)"], None
    errors = [f"photo too small ({side} px, at least {MIN_SIDE} px)"] if side < MIN_SIDE else []
    return errors, hashlib.md5(path.read_bytes()).hexdigest()


def to_schema(df):
    """labels.csv rows -> the columns used by the other processed files."""
    prefix = lambda s: s.map(lambda v: f"lc_{v}" if v else "")
    return pd.DataFrame({
        "id": "lc_" + df["md5"].str[:12],
        "dataset": "local",
        "image_path": "raw/Local/photos/" + df["file"],
        "category": df["category"],
        "sub_category": df["sub_category"],
        "primary_colour": df["primary_colour"],
        "secondary_colour": df["secondary_colour"],
        "pattern": df["pattern"],
        "season": df["season"],
        "usage": df["usage"],
        "style": df["style"],
        "coverage": df["coverage"],
        "coverage_from": df["coverage"].map(lambda v: "label" if v else ""),
        "source": df["source"],
        "gender": df["gender"].map(lambda v: GENDERS.get(v, "")),
        # outfit ids are per contributor, so c01's "1" and c02's "1" stay apart
        "outfit_id": prefix(df["outfit_id"].where(df["outfit_id"] == "",
                                                  df["contributor"] + "_" + df["outfit_id"])),
        "image_group": "lc_" + df["md5"],
    })


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", action="store_true", help="add rows for new photos to labels.csv")
    args = ap.parse_args()
    if args.init:
        return init()
    if not LABELS.exists():
        sys.exit(f"ERROR: {LABELS} not found. Run: python src/phase3/map_local.py --init")

    df = read_labels()
    # values are compared in lowercase; the file names keep their case
    for col in LABEL_COLUMNS[1:13]:
        df[col] = df[col].str.lower()
    line = df.index + 2                     # line number in labels.csv (1 = header)

    problems = []
    for n, f in zip(line[df["file"].duplicated(keep=False)], df.loc[df["file"].duplicated(keep=False), "file"]):
        problems.append(f"line {n} ({f}): listed twice in labels.csv")
    todo = df["category"] == ""
    labelled = df[~todo].copy()
    labelled["md5"] = None
    for i, r in labelled.iterrows():
        photo_errors, md5 = check_photo(PHOTOS / r["file"])
        labelled.at[i, "md5"] = md5
        problems += [f"line {i + 2} ({r['file']}): {e}" for e in photo_errors + check_row(r)]
    copies = labelled[labelled["md5"].notna() & labelled["md5"].duplicated(keep=False)]
    for _, group in copies.groupby("md5"):
        problems.append(f"lines {', '.join(str(i + 2) for i in group.index)}: the same photo "
                        f"saved twice ({', '.join(group['file'])}): keep one")
    if problems:
        print(f"{len(problems)} problem(s) in {LABELS}:")
        print("\n".join("  " + p for p in problems))
        sys.exit(1)

    out = to_schema(labelled)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    # --- summary ----------------------------------------------------------
    print(f"Saved {len(out)} labelled photos to {OUT_PATH}")
    if todo.any():
        print(f"{todo.sum()} rows still have no category (not labelled yet): skipped")
    unlisted = sorted(set(photo_files()) - set(df["file"]))
    if unlisted:
        print(f"{len(unlisted)} photos are not in labels.csv yet (run --init), e.g. {unlisted[:3]}")
    unchecked = labelled[(labelled["checked_by"] == "") |
                         (labelled["checked_by"].str.lower() == labelled["labelled_by"].str.lower())]
    if len(unchecked):
        print(f"{len(unchecked)} labelled rows are not double-checked by a second person yet")
    if len(out):
        print("\nPhotos per category and source:")
        print(pd.crosstab(out["category"], out["source"], margins=True).to_string())
        print(f"\nContributors: {labelled['contributor'].nunique()} · "
              f"with colour: {(out['primary_colour'] != '').mean():.0%} · "
              f"with pattern: {(out['pattern'] != '').mean():.0%} · "
              f"with coverage: {(out['coverage'] != '').mean():.0%}")


if __name__ == "__main__":
    main()
