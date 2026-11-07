"""Condition the SELLER wrote in the ad, from title + description.
Copied from condition_analysis.py (the rules behind the x1.43 / x1.20 factors);
negations like "aucun défaut" are removed before matching."""
import re
from brand_text import norm

NEG = r"(aucun(e)?|sans|pas de|zero|0|ni)\s+(\w+\s+){0,2}"
RULES = [  # (grade, regex) in priority order: first match wins; negations removed first
    ('defect', r"\b(defauts?|taches?|tache[es]?|trous?|troue[es]?|dechire[es]?|decolore[es]?|delave[es]?|abime[es]?|reprise|egratinures?|rayures?)\b"),
    ('new_tags', r"(avec (l'|les |une |des |son |sa )?etiquettes?|jamais (porte|utilise|mis)e?s?|never worn|with tags|sous emballage|dans (sa|son) (boite|emballage)|avec (son|sa) (boite|packaging))"),
    ('like_new', r"(comme neu(f|fs|ve|ves)|presque neu(f|fs|ve|ves)|quasi neu(f|fs|ve|ves)|tres bon(ne)? etat|excellent etat|etat impeccable|impeccable"
                 r"|(porte|utilise|mis)e?s? (une seule|une|1|deux|2|uniquement \\d|seulement \\d)( seule)? fois|(tres|trop) peu(x)? (porte|utilise)|peu (porte|utilise)|a peine (porte|utilise)"
                 r"|(porte|utilise)e?s? (2|deux) ou (3|trois))"),
    ('new', r"(\betat neuf\b|\bneu(f|fs|ve|ves)\b|\bbrand new\b|\bjdid(a)?\b|جديد)"),
    ('good', r"(\bbon(ne)? etat\b|\bndhif(a)?\b|نظيف)"),
    ('used', r"((?<![a-z-])(porte|utilise)(e|es|s)?(?![-a-z])(?! a la main| a l'epaule| a l epaule)|\buse(e|es|s)?\b|\bmest3mel\b|\bmsta3mel\b|مستعمل|\bused\b|\busage\b)"),
]


def grade(text):
    t = norm(text)
    t = re.sub(NEG + r"(defauts?|taches?|trous?|rayures?|egratinures?)", " ", t)   # "aucun defaut"
    t = re.sub(r"porte[- ](cles?|monnaie|cartes?|feuilles?|documents?)", " ", t)
    for g, rx in RULES:
        if re.search(rx, t):
            return g
    return 'no mention'
