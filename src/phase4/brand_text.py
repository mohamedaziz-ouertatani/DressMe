"""Find the brand an ad CLAIMS, from its title and description.

Same normalisation and brand list as condition_analysis.py, so the numbers in
the report and the app agree. Returns None when no known brand is named.
"""
from __future__ import annotations
import re
import unicodedata

BRANDS = ['nike', 'adidas', 'zara', 'h&m', 'lacoste', 'louis vuitton', 'gucci', 'chanel', 'dior',
          'prada', 'guess', 'tommy', 'ralph lauren', 'puma', 'new balance', "levi", 'north face',
          'stone island', 'mango', 'bershka', 'pull&bear', 'massimo dutti', 'michael kors',
          'calvin klein', 'hugo boss', 'versace', 'balenciaga', 'jordan', 'converse', 'vans',
          'timberland', 'skechers', 'reebok', 'fila', 'kappa', 'under armour', 'longchamp']
ORIGINAL = r"\b(original(e|es|s)?|authentique(s)?|orijinal|vrai(e|es|s)?|100 ?%)"


def norm(s) -> str:
    s = unicodedata.normalize('NFKD', str(s or '').lower())
    return ''.join(c for c in s if not unicodedata.combining(c) or '؀' <= c <= 'ۿ')


def claimed_brand(title: str, description: str = '') -> str | None:
    t = norm(f"{title} . {description}")
    return next((b for b in BRANDS if re.search(r'\b' + re.escape(b), t)), None)


def claims_original(title: str, description: str = '') -> bool:
    return bool(re.search(ORIGINAL, norm(f"{title} . {description}")))
