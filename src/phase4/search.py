"""
Search the user's own pieces by words or by a photo (step 3b).

This file is plain Python and numbers: no MongoDB and no model inside. The route (backend/app/routers/search.py)
loads the user's items, asks FashionCLIP for the vector of the words or of the photo, and calls the two
functions below; the chat tool of step 3d will call the same ones.

    words or photo -> a vector of 512 numbers -> cosine similarity with each owned piece -> the cut -> results

Every piece in the wardrobe already has its picture vector (made when it was added). Words are turned into a
vector by FashionCLIP's text side, which lives in the same 512-number space as the picture side, so a text vector
can be compared with a picture vector. Cosine similarity is 1 for the same direction and 0 for unrelated.
Words and photos land in different ranges (a photo is compared with pictures, words with pictures through
a bridge), so each has its own cut in mappings/search_rules.csv, set by src/phase4/calibrate_search.py.
"""

import csv
import re
import unicodedata

import numpy as np

from item_images import ROOT

RULES_CSV = ROOT / "mappings" / "search_rules.csv"
TERMS_CSV = ROOT / "mappings" / "search_terms.csv"

RULE_NAMES = ("text_cut", "photo_cut", "target_precision", "wardrobe_size", "default_limit", "closest_anyway")
ARTICLES = {"a", "an", "the", "le", "la", "les", "un", "une", "des"}      # words that say nothing about the piece
ARABIC_THE = "ال"                                                          # "the" is a prefix in Arabic
LONGEST_PHRASE = 4                                                         # "sac a main" is 3 words: try up to 4
SPELLING = str.maketrans({"ى": "ي", "ة": "ه"})                             # two Arabic letters people mix up


def fold(text):
    """Lowercase, without accents or Arabic marks, with one spelling for the Arabic letters people mix up.
    (NFKD splits a letter from its mark: e-acute -> e + accent, and the Arabic alef with a hamza -> alef + hamza;
    dropping the marks leaves the plain letters.)"""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ـ", "")                  # tatweel, the line that stretches Arabic letters
    return text.translate(SPELLING).replace("’", "'")


def words(text):
    """The folded words of a text. A French elision is dropped: l'ete -> ete, d'oreilles -> oreilles."""
    found = re.findall(r"[^\W_]+(?:['\-][^\W_]+)*", fold(text))
    return [re.sub(r"^(?:l|d)'", "", w) for w in found]


def load_rules(path=RULES_CSV):
    """{name: number} from the team's file (read at each call, so an edit applies at once)."""
    with open(path, encoding="utf-8", newline="") as f:
        rules = {row["name"]: float(row["value"]) for row in csv.DictReader(f)}
    missing = [name for name in RULE_NAMES if name not in rules]
    if missing:
        raise ValueError(f"{path}: missing rows {missing}")
    return rules


def load_terms(path=TERMS_CSV):
    """{folded French or Arabic phrase: English phrase} from the team's table. Stops on a bad row."""
    terms = {}
    with open(path, encoding="utf-8", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            key, english = " ".join(words(row["term"])), row["en"].strip().lower()
            if row["lang"] not in ("fr", "ar"):
                raise ValueError(f"{path}: line {line}: lang must be fr or ar, not {row['lang']!r}")
            if not key or not english:
                raise ValueError(f"{path}: line {line}: the term and its English word are both needed")
            if terms.get(key, english) != english:
                raise ValueError(f"{path}: line {line}: {row['term']!r} already means {terms[key]!r}")
            terms[key] = english
    return terms


def normalise_query(text, terms):
    """What FashionCLIP's text side is asked for: "a photo of <the words>", in English where we know the word.
    French and Arabic fashion words become English through the team's table (longest phrase first, so "sac a
    main" is one handbag, not a bag and a hand); articles go; any other word is kept as typed."""
    tokens = words(text)
    kept, i = [], 0
    while i < len(tokens):
        for n in range(min(LONGEST_PHRASE, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i:i + n])
            # Arabic "the" is glued to the word: also try the phrase without it
            bare = " ".join([tokens[i].removeprefix(ARABIC_THE)] + tokens[i + 1:i + n]) if tokens[i].startswith(ARABIC_THE) else None
            found = terms.get(phrase) or (terms.get(bare) if bare else None)
            if found:
                kept.append(found)
                i += n
                break
        else:
            if tokens[i] not in ARTICLES and tokens[i] != ARABIC_THE:
                kept.append(tokens[i])
            i += 1
    if not kept:                           # nothing but articles ("the"): search for what was typed
        kept = tokens
    return "a photo of " + " ".join(kept) if kept else ""


def unit(vector):
    """The vector scaled to length 1, so a dot product is a cosine similarity."""
    vector = np.asarray(vector, np.float32)
    length = np.linalg.norm(vector)
    if not length:
        raise ValueError("a vector of zeros has no direction")
    return vector / length


def rank_owned(query_vec, items, cut, limit):
    """The user's pieces, best match first.

    items: dicts with a "vector" (512 numbers, or None for a piece that has none; the route never gives
    this function another user's piece). Returns {results, nothing_close, skipped_no_vector}: the best `limit`
    pieces, each {item, similarity, close}, where close = similarity >= cut; nothing_close = none of them is close."""
    usable = [item for item in items if item.get("vector") is not None and np.linalg.norm(item["vector"])]
    skipped = len(items) - len(usable)
    if not usable:
        return {"results": [], "nothing_close": True, "skipped_no_vector": skipped}
    pieces = np.stack([unit(item["vector"]) for item in usable])       # one row per piece
    similarity = pieces @ unit(query_vec)                              # the cosine of each row with the query
    order = np.argsort(-similarity, kind="stable")[:limit]             # best first; ties keep the wardrobe order
    results = [{"item": usable[i], "similarity": float(similarity[i]), "close": bool(similarity[i] >= cut)}
               for i in order]
    return {"results": results, "nothing_close": not any(r["close"] for r in results),
            "skipped_no_vector": skipped}
