"""
The {n} rule: the model names pieces as {1}, {2}... and only numbers shown this turn are real (step 3c).

A known {n} stays in the text (the app will turn it into the piece's photo and name). An invented one is removed
from the text, so no ghost piece is ever shown, and is returned so the turn can log it.
"""

import re

PLACEHOLDER = re.compile(r"\{(\d+)\}")


def resolve(text, ledger):
    """(clean text, refs used, unknown refs); both lists are in order of first appearance, without repeats."""
    used, unknown = [], []

    def keep_or_drop(match):
        ref = int(match.group(1))
        if ledger.item_id(ref) is not None:
            if ref not in used:
                used.append(ref)
            return match.group(0)
        if ref not in unknown:
            unknown.append(ref)
        return ""

    clean = PLACEHOLDER.sub(keep_or_drop, text)
    if unknown:                                           # tidy the gaps the removal left
        clean = re.sub(r"[ \t]{2,}", " ", clean)
        clean = re.sub(r"\s+([.,;:!?])", r"\1", clean).strip()
    return clean, used, unknown
