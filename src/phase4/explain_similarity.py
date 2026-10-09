"""
Why two pieces look alike (XAI sub-project 3). DressMe finds look-alikes with
FashionCLIP picture vectors only; this explains a pair in two ways:

    shared_attributes(a, b)      what the stored labels have in common or not
    concept_overlap(va, vb, cv)  what the picture model associates with each piece,
                                 from the team's list of short texts
                                 (mappings/style_concepts.csv, REVIEW)
    explain_pair(...)            both, for one look-alike

Concepts are the picture model's associations, not facts about the piece
(src/phase4/evaluate_concepts.py checks how well they match known labels).
"""

import numpy as np
import pandas as pd

from item_images import ROOT

CONCEPTS_PATH = ROOT / "mappings" / "style_concepts.csv"
FIELDS = ["category", "sub_category", "colour", "pattern"]


def load_concepts(path=CONCEPTS_PATH):
    """The team's concepts: [{"concept", "prompt", "group", "check"}]."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return df[["concept", "prompt", "group", "check"]].to_dict("records")


def shared_attributes(a, b):
    """Labels both pieces have: equal ones in `shared`, different ones in `differs`.
    A label missing on either side is skipped (unknown is never guessed)."""
    shared, differs = [], []
    for f in FIELDS:
        va, vb = a.get(f) or "", b.get(f) or ""
        if not va or not vb:
            continue
        if va == vb:
            shared.append({"field": f, "value": va})
        else:
            differs.append({"field": f, "a": va, "b": vb})
    return {"shared": shared, "differs": differs}


def _ranking(vector, concept_vectors):
    """Concept names, most associated first."""
    names = list(concept_vectors)
    scores = np.array([float(np.asarray(vector, np.float32) @ concept_vectors[n]) for n in names])
    return [names[i] for i in np.argsort(-scores, kind="stable")]


def top_concepts(vector, concept_vectors, k=3):
    """The k concepts the picture vector is closest to."""
    return _ranking(vector, concept_vectors)[:k]


def concept_overlap(va, vb, concept_vectors, k=3):
    """Concepts in both pieces' top k, and a contrast when each piece's top concept
    is in the bottom half of the other's ranking ("this one reads formal, yours sporty")."""
    if va is None or vb is None or not concept_vectors:
        return {"both": [], "contrast": None}
    ra, rb = _ranking(va, concept_vectors), _ranking(vb, concept_vectors)
    both = [c for c in ra[:k] if c in rb[:k]]
    half = len(ra) // 2
    contrast = None
    if not both and ra[0] in rb[half:] and rb[0] in ra[half:]:
        contrast = {"a": ra[0], "b": rb[0]}
    return {"both": both, "contrast": contrast}


def explain_pair(a, b, va, vb, concept_vectors, k=3):
    """Why look-alike `b` came up for piece `a`: shared labels + concepts."""
    return {**shared_attributes(a, b), **concept_overlap(va, vb, concept_vectors, k)}
