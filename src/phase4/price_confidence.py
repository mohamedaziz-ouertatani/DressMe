"""
Which (channel, category) price estimates are low-confidence.

The price model ranks some groups badly: on the friperie channel its ranking of
shoes is negative (Spearman -0.22 on only 16 pieces). For those groups the band
is still shown, but marked `reliable: false` with a short note, and the deal tags
("Good price" / "Above usual price") are not given.

The list is a TEAM setting, mappings/price_low_confidence.csv
(columns channel, category, reason), never hard-coded here. A missing file
means no group is low-confidence: everything behaves as before.

    low = load_low_confidence()
    reason = low.get(("friperie", "shoes"))      # None = reliable
"""

from __future__ import annotations

import csv
from pathlib import Path

try:                                    # the API puts src/phase4 on the path
    from item_images import ROOT
except ImportError:                     # standalone use
    ROOT = Path(__file__).resolve().parents[2]

LOW_CONFIDENCE_CSV = ROOT / "mappings" / "price_low_confidence.csv"
CHANNELS = ("friperie", "classified")   # the same channels as price.CHANNELS


def load_low_confidence(path: Path | None = None) -> dict[tuple[str, str], str]:
    """{(channel, category): reason}. A missing file gives {} (nothing low-confidence).

    A row with an unknown channel or an empty category stops with an error naming
    the line, like price.load_rules: a typo must fail loudly, not be ignored.
    """
    path = Path(path) if path is not None else LOW_CONFIDENCE_CSV
    if not path.exists():
        return {}
    pairs: dict[tuple[str, str], str] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            channel = (row.get("channel") or "").strip()
            category = (row.get("category") or "").strip()
            if channel not in CHANNELS:
                raise ValueError(f"{path.name} line {line}: unknown channel {channel!r}")
            if not category:
                raise ValueError(f"{path.name} line {line}: empty category")
            pairs[(channel, category)] = (row.get("reason") or "").strip()
    return pairs


def rough_note(channel: str, category: str) -> str:
    """The English line that travels with a low-confidence band (the app shows its own translation)."""
    return f"Few {channel} {category} in our data: treat this range as rough."
