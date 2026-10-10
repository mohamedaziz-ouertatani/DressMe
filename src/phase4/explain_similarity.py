"""
Why two pieces look alike (XAI sub-project 3). DressMe finds look-alikes with
FashionCLIP picture vectors only; this explains a pair in two ways:

    shared_attributes(a, b)      what the stored labels have in common or not
    concept_overlap(va, vb, cv)  what the picture model associates with each piece
                                 (above the average picture: concept_baseline),
                                 from the team's list of short texts
                                 (mappings/style_concepts.csv, REVIEW)
    explain_pair(...)            both, for one look-alike

Concepts are the picture model's associations, not facts about the piece
(src/phase4/evaluate_concepts.py checks how well they match known labels).
"""

import numpy as np
import pandas as pd

import genders
from item_images import ROOT

CONCEPTS_PATH = ROOT / "mappings" / "style_concepts.csv"
FIELDS = ["category", "sub_category", "colour", "pattern"]


def load_concepts(path=CONCEPTS_PATH, gender=None):
    """The team's concepts: [{"concept", "prompt", "group", "check"}]. gender = men / women
    uses that gender's wording of a concept when the team wrote one."""
    df = genders.for_gender(pd.read_csv(path, dtype=str, keep_default_na=False), gender,
                            lambda r: r.concept)
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


def concept_baseline(mean_vector, concept_vectors):
    """How much the average picture matches each concept. Some prompts ("trendy") match
    nearly every photo; subtracting this keeps only what is special about a piece. The
    mean of the dot products over many pictures = the dot product with their mean vector."""
    if mean_vector is None:
        return None
    mean = np.asarray(mean_vector, np.float32)
    return {c: float(mean @ v) for c, v in concept_vectors.items()}


def _ranking(vector, concept_vectors, baseline=None):
    """Concept names, most associated first (above the average picture, with a baseline)."""
    names = list(concept_vectors)
    vec = np.asarray(vector, np.float32)
    scores = np.array([float(vec @ concept_vectors[n]) - (baseline or {}).get(n, 0.0) for n in names])
    return [names[i] for i in np.argsort(-scores, kind="stable")]


def top_concepts(vector, concept_vectors, k=3, baseline=None):
    """The k concepts the picture vector is closest to."""
    return _ranking(vector, concept_vectors, baseline)[:k]


def concept_overlap(va, vb, concept_vectors, k=3, baseline=None):
    """Concepts in both pieces' top k, and a contrast when each piece's top concept
    is in the bottom half of the other's ranking ("this one reads formal, yours sporty")."""
    if va is None or vb is None or not concept_vectors:
        return {"both": [], "contrast": None}
    ra, rb = _ranking(va, concept_vectors, baseline), _ranking(vb, concept_vectors, baseline)
    both = [c for c in ra[:k] if c in rb[:k]]
    half = len(ra) // 2
    contrast = None
    if not both and ra[0] in rb[half:] and rb[0] in ra[half:]:
        contrast = {"a": ra[0], "b": rb[0]}
    return {"both": both, "contrast": contrast}


def explain_pair(a, b, va, vb, concept_vectors, k=3, baseline=None):
    """Why look-alike `b` came up for piece `a`: shared labels + concepts."""
    return {**shared_attributes(a, b), **concept_overlap(va, vb, concept_vectors, k, baseline)}
