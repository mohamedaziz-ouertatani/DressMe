# Outfit score + buy advice XAI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain every outfit score (points per part, strengths and problems, swaps, pair map) and every buy verdict (what it beats, path to the verdict, near twins, what would change it), and measure whether "weakest piece" is faithful.

**Architecture:** `src/phase4/compatibility.py` keeps its formula; its part functions also return structured problem lines and `buy_advice` adds a `detail` block. A new pure module `src/phase4/explain_outfit.py` turns results into contributions, strengths, swaps, a pair map and the buy explanation. The API adds the cheap parts to every outfit answer (`outfit_out(..., explain=True)`), a new `POST /outfits/explain` for swaps + pair map, and `explanation` on `/buy-advice`. The React app renders the structured lines in en / fr / ar.

**Tech Stack:** Python (numpy, pandas), FastAPI + pymongo, React + TypeScript + Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-08-outfit-xai-design.md`

## Global Constraints

- Weights and rules stay the team's (`mappings/*.csv`); new thresholds go in `mappings/xai_settings.csv`, every row marked `REVIEW`: `strength_style` = 0.7, `strength_colour_pair` = 0.8, `near_miss` = 5.
- `score_outfit`'s `score`, `parts` and English `reasons` must not change (the chat agents and `i18n.reason` read them); it only gains the key `problems`.
- The chat tools keep their output: `outfit_out` adds the explanation fields only when called with `explain=True` (the routers do; `backend/app/agents/*` do not).
- Points per part are rounded to 0.1 and add up exactly to `score`.
- Swaps never propose a clash (`compatibility.clashes`).
- Privacy: every item goes through `own_item` (another user's item answers 404).
- No new dependency. Keep code simple and commented (mixed-experience team).
- Commits: no Co-Authored-By trailer and no "Generated with Claude Code" footer (user preference).
- Backend tests from `backend/`: `python -m pytest` (MongoDB running). `tests/test_jobs.py` is flaky on main (known, not ours). Runs > 10 min: separate process with a log.

## Changes from the spec (decided while planning)

- `POST /outfits/explain` takes only `item_ids` (no `candidate_id`): the expander is shown on Build and Today, which only use wardrobe items. Scan / Shop explain the verdict instead.
- `buy_advice` `detail` lists every completed outfit (`{item_ids, score, owned_id, owned_score}`); `explain_outfit.buy_explanation` derives beats / lost_to / near_misses from it with the team settings, so `compatibility.py` never reads `xai_settings.csv`.
- When a colour pair strength is shown, `colour_neutral_base` is not (it would say the same thing twice).
- Swaps and gains use the same personal `style_profile` as `/outfits/score`, so the gain matches the score the user sees.

## File structure

| File | Change | Responsibility |
|---|---|---|
| `src/phase4/compatibility.py` | modify | `line`, `rescale_style`, `style_coherence`, `clothing_patterns`; part functions return problems; `score_outfit` adds `problems`; `buy_advice` adds `detail` |
| `src/phase4/explain_outfit.py` | create | contributions, strengths, swaps, weakest, pair map, buy explanation |
| `mappings/xai_settings.csv` | modify | 3 new REVIEW rows |
| `backend/app/wardrobe.py` | modify | `outfit_out(result, docs_by_id, explain=False)`, `short_item` |
| `backend/app/routers/outfits.py` | modify | `explain=True` everywhere, `POST /outfits/explain`, buy `explanation` |
| `backend/tests/test_outfit_explain.py` | create | unit tests (no Mongo) |
| `backend/tests/test_outfits.py` | modify | API tests |
| `frontend/src/api/types.ts`, `api/client.ts` | modify | types + `api.explainOutfit` |
| `frontend/src/i18n/explain.ts` | create | one template per code (en / fr / ar) |
| `frontend/src/i18n/strings.ts` | modify | UI labels |
| `frontend/src/ui/ScoreWhy.tsx` | create | points bar, explanation lines, "Why this score?" expander |
| `frontend/src/ui/VerdictWhy.tsx` | create | "Why this verdict?" |
| `frontend/src/ui/OutfitStrip.tsx` | modify | uses ScoreWhy |
| `frontend/src/pages/BuildPage.tsx`, `TodayPage.tsx`, `ScanPage.tsx`, `ShopPage.tsx` | modify | wire it in |
| `src/phase4/evaluate_outfit_explanations.py` | create | intruder test → report |
| `reports/phase4/outfit_explanations_evaluation.md` | generated | |
| `CLAUDE.md`, the spec | modify | docs |

---

### Task 1: Problem codes in the formula

**Files:**
- Modify: `src/phase4/compatibility.py` (part functions ~lines 144-235, `score_outfit`)
- Create: `backend/tests/test_outfit_explain.py`

**Interfaces:**
- Produces: `compatibility.line(part, sign, code, **params) -> {"code", "part", "sign", "params"}`.
- Produces: `compatibility.rescale_style(sim, rules) -> float in [0, 1]`; `compatibility.style_coherence(items, rules) -> float | None` (None with < 2 vectors).
- Produces: `compatibility.clothing_patterns(items, rules) -> list[str]` (patterns of clothes with confidence ≥ `min_pattern_conf`).
- Produces: each `*_part` returns `(value, reasons, problems)`; `score_outfit(...)` result gains `"problems": [line, ...]`.
- Problem codes: `style_unlike_you`, `style_mixed`, `colour_clash` {a, b}, `colour_too_bold` {colours: list}, `pattern_clash` {a, b}, `structure_no_shoes`, `structure_incomplete` {missing: "top_or_bottom" | "main_piece"}, `structure_full_and_bottom`, `structure_over_limit` {category, n}, `structure_pair` {a, b}.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_outfit_explain.py`

```python
"""Outfit score and buy-advice explanations (src/phase4/explain_outfit.py) and the
problem codes of the formula. Pure functions: no Mongo, no model."""

import sys

import numpy as np
import pytest

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import compatibility as C  # noqa: E402


def vec(seed, base=3.0):
    v = np.random.default_rng(seed).normal(size=512) + base
    return (v / np.linalg.norm(v)).astype(np.float32)


def item(id, category, sub="", colour="", pattern="", seed=0):
    return {"id": id, "category": category, "sub_category": sub, "colour": colour,
            "pattern": pattern, "pattern_conf": 1.0, "vector": vec(seed)}


def codes(lines):
    return [(l["sign"], l["code"]) for l in lines]


def test_problems_mirror_the_english_reasons():
    outfit = [item("t", "top", "t-shirt", "red", "striped", 1), item("b", "bottom", "jeans", "orange", "floral", 2)]
    r = C.score_outfit(outfit)
    got = codes(r["problems"])
    assert ("-", "structure_no_shoes") in got
    assert ("-", "pattern_clash") in got
    clash = next(l for l in r["problems"] if l["code"] == "pattern_clash")
    assert set(clash["params"].values()) == {"striped", "floral"}
    assert "no shoes" in r["reasons"]                              # English reasons unchanged
    assert all(l["sign"] == "-" for l in r["problems"])


def test_incomplete_and_over_limit_codes():
    r = C.score_outfit([item("t", "top", "t-shirt", "black")])
    inc = next(l for l in r["problems"] if l["code"] == "structure_incomplete")
    assert inc["params"] == {"missing": "top_or_bottom"}
    r = C.score_outfit([item("s", "shoes", "sneakers"), item("s2", "shoes", "heels")])
    assert inc != next(l for l in r["problems"] if l["code"] == "structure_incomplete")
    over = [l for l in r["problems"] if l["code"] == "structure_over_limit"]
    assert over and over[0]["params"] == {"category": "shoes", "n": 2}


def test_style_helpers():
    a, b = item("a", "top", seed=1), item("b", "bottom", seed=1)      # same vector
    assert C.style_coherence([a, b], C.RULES) == 1.0
    assert C.style_coherence([a], C.RULES) is None
    assert C.rescale_style(C.RULES.settings["style_low"], C.RULES) == 0.0
    shirt = item("s", "top", pattern="striped")
    shoes = item("f", "shoes", pattern="striped")                     # shoes are not clothes here
    assert C.clothing_patterns([shirt, shoes], C.RULES) == ["striped"]
```

- [ ] **Step 2: Run to see them fail**

Run (from `backend/`): `python -m pytest tests/test_outfit_explain.py -q`
Expected: FAIL — `KeyError: 'problems'`, `AttributeError: ... style_coherence`.

- [ ] **Step 3: Add the helpers** in `compatibility.py`, right after `outfit_vector`:

```python
def line(part, sign, code, **params):
    """One structured explanation line; the app turns `code` into a sentence in
    en / fr / ar (frontend/src/i18n/explain.ts)."""
    return {"code": code, "part": part, "sign": sign, "params": params}


def rescale_style(sim, rules):
    """A FashionCLIP similarity on the team's 0-1 style scale (style_low / style_high)."""
    lo, hi = rules.settings["style_low"], rules.settings["style_high"]
    return float(np.clip((sim - lo) / (hi - lo), 0, 1))


def style_coherence(items, rules):
    """How alike the pieces look: mean pairwise similarity, rescaled (None if < 2 vectors)."""
    vecs = [np.asarray(i["vector"], np.float32) for i in items if i.get("vector") is not None]
    if len(vecs) < 2:
        return None
    return rescale_style(float(np.mean([a @ b for a, b in combinations(vecs, 2)])), rules)


def clothing_patterns(items, rules):
    """Patterns that count: clothes only, and predicted patterns only when confident."""
    return [i["pattern"] for i in items
            if i.get("pattern") and rules.slot.get(i["category"]) in CLOTHES_SLOTS
            and i.get("pattern_conf", 1.0) >= rules.settings["min_pattern_conf"]]
```

- [ ] **Step 4: Rewrite the four part functions and `score_outfit`** (same values and reasons as today):

```python
def style_part(items, rules, style_profile=None):
    coherence = style_coherence(items, rules)
    if coherence is None:
        return None, [], []
    part, reasons, problems = coherence, [], []
    if style_profile is not None:
        vecs = [np.asarray(i["vector"], np.float32) for i in items if i.get("vector") is not None]
        user_fit = rescale_style(float(np.mean([style_profile @ v for v in vecs])), rules)
        personal_weight = rules.settings["style_personal_weight"]
        part = ((1 - personal_weight) * coherence) + (personal_weight * user_fit)
        if user_fit < 0.3:
            reasons.append("the outfit is unlike your usual style")
            problems.append(line("style", "-", "style_unlike_you"))
    if coherence < 0.3:
        reasons.append("the pieces have quite different styles")
        problems.append(line("style", "-", "style_mixed"))
    return part, reasons, problems


def colour_part(items, rules):
    colours = [i["colour"] for i in items if i.get("colour")]
    if len(colours) < 2:
        return None, [], []
    pairs = [(a, b, rules.colour_score(a, b)) for a, b in combinations(colours, 2)]
    part = float(np.mean([s for _, _, s in pairs]))
    reasons, problems = [], []
    worst = min(pairs, key=lambda p: p[2])
    if worst[2] < 0.5:
        reasons.append(f"{worst[0]} and {worst[1]} clash")
        problems.append(line("colour", "-", "colour_clash", a=worst[0], b=worst[1]))
    bold = {c for c in colours if rules.group[c] not in ("neutral", "metal")}
    extra = len(bold) - rules.settings["max_bold_colours"]
    if extra > 0:
        part -= extra * rules.settings["bold_colour_penalty"]
        reasons.append(f"many bold colours ({', '.join(sorted(bold))})")
        problems.append(line("colour", "-", "colour_too_bold", colours=sorted(bold)))
    return float(max(part, 0)), reasons, problems


def pattern_part(items, rules):
    patterns = clothing_patterns(items, rules)
    if not patterns:
        return None, [], []
    if len(patterns) == 1:
        return 1.0, [], []
    pairs = [(a, b, rules.pattern_pairs[(a, b)]) for a, b in combinations(patterns, 2)]
    worst = min(pairs, key=lambda p: p[2])        # one clash is enough to spoil it
    if worst[2] >= 0.5:
        return worst[2], [], []
    return (worst[2], [f"two bold patterns ({worst[0]} + {worst[1]})"],
            [line("pattern", "-", "pattern_clash", a=worst[0], b=worst[1])])
```

In `structure_part`, keep the logic and add a `problems` list next to every `reasons.append`:

```python
    reasons, problems = [], []
    if core and (slots.get("feet", 0) or swim):   # a swimsuit needs no shoes
        part = 1.0
    elif core:
        part = rules.settings["structure_no_shoes"]
        reasons.append("no shoes")
        problems.append(line("structure", "-", "structure_no_shoes"))
    else:
        part = rules.settings["structure_incomplete"]
        missing = "top_or_bottom" if upper or lower else "main_piece"
        reasons.append("missing a top or a bottom" if upper or lower else "no main piece")
        problems.append(line("structure", "-", "structure_incomplete", missing=missing))
    if full and lower:       # e.g. a dress with trousers: unusual
        part *= rules.settings["structure_over_limit"]
        reasons.append("a full piece and a bottom together")
        problems.append(line("structure", "-", "structure_full_and_bottom"))
    for cat, n in counts.items():
        if n > rules.max_items[cat]:
            part *= rules.settings["structure_over_limit"] ** (n - rules.max_items[cat])
            reasons.append(f"{n} items of {cat}")
            problems.append(line("structure", "-", "structure_over_limit", category=cat, n=int(n)))
    ...
        if worst[2] < 0.5:
            reasons.append(f"{worst[0]} and {worst[1]} don't go together")
            problems.append(line("structure", "-", "structure_pair", a=worst[0], b=worst[1]))
    return part, reasons, problems
```

`score_outfit`:

```python
def score_outfit(items, rules=RULES, weights=None, style_profile=None):
    """Score from 0 to 100, the value of each part (None = not computable), the
    English reasons and the same problems as structured lines (for the app)."""
    weights = weights or rules.weights
    parts, reasons, problems = {}, [], []
    for name, fn in PART_FUNCTIONS.items():
        if name == "style":
            parts[name], why, lines = fn(items, rules, style_profile)
        else:
            parts[name], why, lines = fn(items, rules)
        reasons += why
        problems += lines
    used = {p: weights[p] for p, v in parts.items() if v is not None and weights[p] > 0}
    total = sum(used.values())
    score = 100 * sum(weights[p] * parts[p] for p in used) / total if total else 0.0
    return {"score": round(score, 1), "parts": parts, "reasons": reasons, "problems": problems}
```

Update the module docstring line `score_outfit(items) -> score, parts, reasons` to `-> score, parts, reasons, problems`.

- [ ] **Step 5: Check the scores did not move** — before editing (git stash) and after, run from the repo root:

```bash
python -c "import sys; sys.path[:0]=['src/common','src/phase3','src/phase4']; import evaluate_compatibility as E, numpy as np, compatibility as C; df, items = E.load_items(); o = E.outfit_lists(df)['PolyVore'][0][:300]; print(sum(C.score_outfit([items[i] for i in x])['score'] for x in o))"
```
Expected: the same number both times.

- [ ] **Step 6: Run the tests** — `python -m pytest tests/test_outfit_explain.py tests/test_outfits.py tests/test_admin.py -q`. Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/phase4/compatibility.py backend/tests/test_outfit_explain.py
git commit -m "Outfit XAI: the formula returns its problems as structured lines"
```

---

### Task 2: Contributions and strengths

**Files:**
- Create: `src/phase4/explain_outfit.py`
- Modify: `mappings/xai_settings.csv`
- Modify: `backend/tests/test_outfit_explain.py`

**Interfaces:**
- Consumes: Task 1 helpers; `explain.load_settings()` (sub-project 1, `src/phase4/explain.py`).
- Produces: `explain_outfit.contributions(result, weights) -> list[dict]` with keys `part, weight, value, counted, points, max_points, why_not` (in `PARTS` order; `why_not` ∈ None / `no_vectors` / `no_colours` / `no_patterns` / `weight_zero`).
- Produces: `explain_outfit.strengths(items, parts, rules=None, settings=None) -> list[line]` with codes `style_coherent`, `colour_pair` {a, b}, `colour_neutral_base` {n}, `pattern_one_bold` {pattern}, `pattern_calm`, `structure_complete`.

- [ ] **Step 1: Failing tests** (append; add `import explain_outfit as X  # noqa: E402`):

```python
SETTINGS = {"strength_style": 0.7, "strength_colour_pair": 0.8, "near_miss": 5}


def test_contributions_add_up_and_rescale():
    result = {"score": 71.8, "parts": {"style": 0.8, "colour": 0.6, "pattern": None, "structure": 0.75}}
    w = {"style": 0.35, "colour": 0.30, "pattern": 0.15, "structure": 0.20}
    rows = {r["part"]: r for r in X.contributions(result, w)}
    assert round(sum(r["points"] for r in rows.values()), 1) == 71.8   # 71.76 exact
    assert rows["pattern"]["counted"] is False and rows["pattern"]["why_not"] == "no_patterns"
    assert rows["style"]["max_points"] == round(100 * 0.35 / 0.85, 1)     # rescaled without pattern
    w0 = {**w, "colour": 0.0}
    assert {r["part"]: r for r in X.contributions(result, w0)}["colour"]["why_not"] == "weight_zero"


def test_contributions_match_score_outfit():
    outfit = [item("t", "top", "t-shirt", "navy", "solid", 1), item("b", "bottom", "jeans", "white", "solid", 2),
              item("s", "shoes", "sneakers", "white", seed=3)]
    r = C.score_outfit(outfit)
    assert round(sum(x["points"] for x in X.contributions(r, C.RULES.weights)), 1) == r["score"]


def test_strengths():
    same = [item("t", "top", "t-shirt", "navy", "striped", 1), item("b", "bottom", "jeans", "white", "solid", 1),
            item("s", "shoes", "sneakers", "white", seed=1)]
    r = C.score_outfit(same)
    got = codes(X.strengths(same, r["parts"], C.RULES, SETTINGS))
    assert ("+", "style_coherent") in got                      # identical vectors
    assert ("+", "pattern_one_bold") in got and ("+", "structure_complete") in got
    assert all(sign == "+" for sign, _ in got)
    plain = [item("t", "top", "t-shirt", "", "solid", 1), item("b", "bottom", "jeans", "", "solid", 9)]
    got = codes(X.strengths(plain, C.score_outfit(plain)["parts"], C.RULES, SETTINGS))
    assert ("+", "pattern_calm") in got and ("+", "structure_complete") not in got


def test_settings_file_has_outfit_rows():
    import explain
    s = explain.load_settings()
    assert {"strength_style", "strength_colour_pair", "near_miss"} <= set(s)
```

- [ ] **Step 2: Run to see them fail** — `ModuleNotFoundError: explain_outfit`.

- [ ] **Step 3: Settings rows** — append to `mappings/xai_settings.csv`:

```csv
strength_style,0.7,"REVIEW: outfit style coherence (0-1) from which the app says ""the pieces share one style"""
strength_colour_pair,0.8,"REVIEW: colour pair score from which the app says ""navy and white go together"""
near_miss,5,"REVIEW: buy advice: outfits this many points below good_outfit count as near misses"
```

(The sub-project 1 test `test_settings_file_has_every_cut` asserts an exact key set: change it to `assert {"min_conf_" + f for f in explain.FIELDS} | {"margin"} <= set(s)` in `backend/tests/test_explain.py`, and keep `all(0 <= v <= 1 ...)` only for those keys.)

- [ ] **Step 4: Create `src/phase4/explain_outfit.py`**

```python
"""
Why an outfit gets its score, and why "should I buy this?" says what it says
(XAI sub-project 2). Pure functions on the results of compatibility.py:

    contributions(result, weights)  points of each part (they add up to the score)
    strengths(items, parts)         what works ("+" lines; the "-" lines come from score_outfit)
    swaps(items, wardrobe)          for each piece, the best replacement you own and its gain
    weakest(swap_list)              the piece whose swap gains the most
    pair_map(items)                 style / colour / pattern score of every pair of pieces
    buy_explanation(advice)         path to the verdict, what it beats, what would change it

Thresholds of the "+" lines and of near misses are TEAM settings
(mappings/xai_settings.csv, REVIEW). Nothing here changes a score.
"""

from itertools import combinations

import numpy as np

import compatibility as C
import explain

WHY_NOT = {"style": "no_vectors", "colour": "no_colours", "pattern": "no_patterns",
           "structure": "no_items"}


def _round_to(raw, target):
    """Round the values to 0.1 so that they add up exactly to `target`
    (largest remainder: the parts closest to the next 0.1 get it)."""
    tenths = {p: v * 10 for p, v in raw.items()}
    out = {p: int(np.floor(v + 1e-9)) for p, v in tenths.items()}
    left = int(round(target * 10)) - sum(out.values())
    for p in sorted(raw, key=lambda p: tenths[p] - out[p], reverse=True)[:max(left, 0)]:
        out[p] += 1
    return {p: v / 10 for p, v in out.items()}


def contributions(result, weights):
    """Points of each part: 100 x weight x value / (sum of the counted weights)."""
    parts = result["parts"]
    counted = {p for p in C.PARTS if parts[p] is not None and weights[p] > 0}
    total = sum(weights[p] for p in counted)
    raw = {p: (100 * weights[p] * parts[p] / total if p in counted else 0.0) for p in C.PARTS}
    points = _round_to(raw, result["score"])
    rows = []
    for p in C.PARTS:
        row = {"part": p, "weight": weights[p], "counted": p in counted,
               "value": None if parts[p] is None else round(float(parts[p]), 3)}
        if p in counted:
            row.update(points=points[p], max_points=round(100 * weights[p] / total, 1), why_not=None)
        else:
            row.update(points=0.0, max_points=0.0,
                       why_not="weight_zero" if weights[p] <= 0 else WHY_NOT[p])
        rows.append(row)
    return rows


def strengths(items, parts, rules=None, settings=None):
    """What works in the outfit, from the same rule tables as the score."""
    rules = rules or C.RULES
    settings = settings or explain.load_settings()
    out = []
    coherence = C.style_coherence(items, rules)
    if coherence is not None and coherence >= settings["strength_style"]:
        out.append(C.line("style", "+", "style_coherent"))
    colours = [i["colour"] for i in items if i.get("colour")]
    if len(colours) >= 2:
        pairs = [(a, b, rules.colour_score(a, b)) for a, b in combinations(colours, 2)]
        if min(s for _, _, s in pairs) >= 0.5:                       # no clash
            distinct = [p for p in pairs if p[0] != p[1]] or pairs
            best = max(distinct, key=lambda p: p[2])
            neutrals = [c for c in colours if rules.group[c] == "neutral"]
            if best[2] >= settings["strength_colour_pair"] and best[0] != best[1]:
                out.append(C.line("colour", "+", "colour_pair", a=best[0], b=best[1]))
            elif len(neutrals) >= 2:
                out.append(C.line("colour", "+", "colour_neutral_base", n=len(neutrals)))
    patterns = C.clothing_patterns(items, rules)
    bold = [p for p in patterns if p != "solid"]
    if len(bold) == 1:
        out.append(C.line("pattern", "+", "pattern_one_bold", pattern=bold[0]))
    elif len(patterns) >= 2 and not bold:
        out.append(C.line("pattern", "+", "pattern_calm"))
    if parts.get("structure") == 1.0:
        out.append(C.line("structure", "+", "structure_complete"))
    return out
```

- [ ] **Step 5: Run the tests** — `python -m pytest tests/test_outfit_explain.py tests/test_explain.py -q`. Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/phase4/explain_outfit.py mappings/xai_settings.csv backend/tests/test_outfit_explain.py backend/tests/test_explain.py
git commit -m "Outfit XAI: points per part and strengths"
```

---

### Task 3: Swaps, weakest piece, pair map

**Files:**
- Modify: `src/phase4/explain_outfit.py`
- Modify: `backend/tests/test_outfit_explain.py`

**Interfaces:**
- Produces: `swaps(items, wardrobe, rules=None, style_profile=None) -> list[{"item_id", "best_swap_id" | None, "gain"}]` (one per piece, in outfit order; gain rounded to 0.1, 0.0 when nothing better).
- Produces: `weakest(swap_list, positive_only=True) -> item_id | None`.
- Produces: `pair_map(items, rules=None) -> list[{"a", "b", "style", "colour", "pattern"}]` (values 0-1 rounded to 3, or None).

- [ ] **Step 1: Failing tests** (append):

```python
def test_swaps_find_a_better_piece_and_never_clash():
    top = item("t", "top", "t-shirt", "orange", "solid", 1)
    jeans = item("j", "bottom", "jeans", "blue", "solid", 1)
    shoes = item("s", "shoes", "sneakers", "white", seed=1)
    bad_top = item("x", "top", "shirt", "red", "solid", 1)          # orange is replaced by...
    good_top = item("g", "top", "shirt", "white", "solid", 1)        # ...a neutral white shirt
    jeans2 = item("j2", "bottom", "jeans", "black", "solid", 1)      # same sub_category: swap OK
    wardrobe = [top, jeans, shoes, bad_top, good_top, jeans2]
    rows = {r["item_id"]: r for r in X.swaps([top, jeans, shoes], wardrobe)}
    assert set(rows) == {"t", "j", "s"}
    assert rows["t"]["best_swap_id"] == "g" and rows["t"]["gain"] > 0
    assert rows["s"]["best_swap_id"] is None and rows["s"]["gain"] == 0.0   # no other shoes
    assert X.weakest(list(rows.values())) == max(rows.values(), key=lambda r: r["gain"])["item_id"]
    assert X.weakest([{"item_id": "a", "gain": 0.0}]) is None
    assert X.weakest([{"item_id": "a", "gain": 0.0}], positive_only=False) == "a"


def test_pair_map():
    a = item("a", "top", "t-shirt", "navy", "striped", 1)
    b = item("b", "bottom", "jeans", "", "floral", 1)
    s = {**item("s", "shoes", "sneakers", "white", seed=5), "vector": None}
    rows = {(r["a"], r["b"]): r for r in X.pair_map([a, b, s])}
    assert len(rows) == 3
    assert rows[("a", "b")]["style"] == 1.0 and rows[("a", "b")]["colour"] is None
    assert rows[("a", "b")]["pattern"] == C.RULES.pattern_pairs[("striped", "floral")]
    assert rows[("a", "s")]["style"] is None and rows[("a", "s")]["pattern"] is None   # shoes: no pattern
    assert rows[("a", "s")]["colour"] == round(C.RULES.colour_score("navy", "white"), 3)
```

- [ ] **Step 2: Run to see them fail** — `AttributeError: ... swaps`.

- [ ] **Step 3: Implement** (append to `explain_outfit.py`):

```python
def swaps(items, wardrobe, rules=None, style_profile=None):
    """For each piece: the wardrobe item of the same category that raises the score
    most when it takes the piece's place (never a clash), and how many points."""
    rules = rules or C.RULES
    base = C.score_outfit(items, rules, style_profile=style_profile)["score"]
    in_outfit = {i["id"] for i in items}
    out = []
    for k, piece in enumerate(items):
        rest = items[:k] + items[k + 1:]
        best, best_score = None, base
        for w in wardrobe:
            if w["id"] in in_outfit or w["category"] != piece["category"]:
                continue
            trial = rest + [w]
            if C.clashes(trial, rules):
                continue
            s = C.score_outfit(trial, rules, style_profile=style_profile)["score"]
            if s > best_score:
                best, best_score = w, s
        out.append({"item_id": piece["id"], "best_swap_id": best["id"] if best else None,
                    "gain": round(best_score - base, 1)})
    return out


def weakest(swap_list, positive_only=True):
    """The piece whose best swap gains the most (None if no swap helps).
    positive_only=False always names one (used by the offline evaluation)."""
    rows = [s for s in swap_list if s["gain"] > 0] if positive_only else list(swap_list)
    return max(rows, key=lambda s: s["gain"])["item_id"] if rows else None


def pair_map(items, rules=None):
    """Style / colour / pattern score (0-1) of every pair of pieces; None = unknown."""
    rules = rules or C.RULES
    out = []
    for a, b in combinations(items, 2):
        style = colour = pattern = None
        if a.get("vector") is not None and b.get("vector") is not None:
            sim = float(np.asarray(a["vector"], np.float32) @ np.asarray(b["vector"], np.float32))
            style = round(C.rescale_style(sim, rules), 3)
        if a.get("colour") and b.get("colour"):
            colour = round(rules.colour_score(a["colour"], b["colour"]), 3)
        pa, pb = C.clothing_patterns([a], rules), C.clothing_patterns([b], rules)
        if pa and pb:
            pattern = round(rules.pattern_pairs[(pa[0], pb[0])], 3)
        out.append({"a": a["id"], "b": b["id"], "style": style, "colour": colour, "pattern": pattern})
    return out
```

- [ ] **Step 4: Run** — `python -m pytest tests/test_outfit_explain.py -q`. Expected: pass. If `test_swaps...` picks another top than `g`, print `rows` and the scores: the test data must make white clearly better than red with blue jeans (check `mappings/colour_harmony.csv`); adjust the *test colours*, never the rules.

- [ ] **Step 5: Commit**

```bash
git add src/phase4/explain_outfit.py backend/tests/test_outfit_explain.py
git commit -m "Outfit XAI: swaps, weakest piece and pair map"
```

---

### Task 4: Buy advice detail and explanation

**Files:**
- Modify: `src/phase4/compatibility.py` (`buy_advice`, ~line 396)
- Modify: `src/phase4/explain_outfit.py`
- Modify: `backend/tests/test_outfit_explain.py`

**Interfaces:**
- Produces: `buy_advice(...)` result gains `detail = {"outfits": [{"item_ids", "score", "owned_id" | None, "owned_score"}], "twins": [{"id", "similarity"}]}` (every completed outfit containing the candidate, best first; when the candidate is filtered out by the profile: `{"outfits": [], "twins": []}`).
- Produces: `buy_explanation(advice, rules=None, settings=None) -> {"path": {"good", "buy_min", "think_min", "verdict"}, "beats": [{"item_ids", "owned_id", "owned_score", "margin"}], "lost_to": [{"owned_id", "outfits"}], "near_misses": int, "to_next_verdict": int | None, "twins": [...]}`.

- [ ] **Step 1: Failing tests** (append):

```python
def test_buy_advice_detail_and_explanation():
    cand = item("c", "top", "shirt", "white", "solid", 1)
    owned_top = item("o", "top", "t-shirt", "orange", "solid", 1)
    wardrobe = [owned_top, item("j", "bottom", "jeans", "blue", "solid", 1),
                item("s", "shoes", "sneakers", "white", seed=1)]
    advice = C.buy_advice(cand, wardrobe)
    d = advice["detail"]
    assert d["outfits"] and all("c" in o["item_ids"] for o in d["outfits"])
    assert d["outfits"][0]["owned_id"] == "o"
    assert [t["id"] for t in d["twins"]] == ["o"]                   # identical vectors: a twin
    why = X.buy_explanation(advice, settings=SETTINGS)
    assert why["path"]["verdict"] == advice["verdict"] and why["path"]["good"] == advice["good_outfits"]
    assert why["path"]["buy_min"] == C.RULES.settings["buy_min_outfits"]
    assert all(b["margin"] > 0 for b in why["beats"])
    if advice["verdict"] != "buy":
        assert why["to_next_verdict"] >= 1
    assert why["twins"] == d["twins"]


def test_buy_explanation_counts():
    advice = {"verdict": "think", "good_outfits": 1, "detail": {"twins": [], "outfits": [
        {"item_ids": ["c", "a"], "score": 80.0, "owned_id": "o1", "owned_score": 70.0},   # beats o1
        {"item_ids": ["c", "b"], "score": 75.0, "owned_id": "o2", "owned_score": 78.0},   # o2 wins
        {"item_ids": ["c", "d"], "score": 73.0, "owned_id": "o2", "owned_score": 73.0},   # tie: o2 wins
        {"item_ids": ["c", "e"], "score": 57.0, "owned_id": None, "owned_score": 0.0},    # near miss
        {"item_ids": ["c", "f"], "score": 40.0, "owned_id": None, "owned_score": 0.0}]}}
    why = X.buy_explanation(advice, settings=SETTINGS)
    assert [b["owned_id"] for b in why["beats"]] == ["o1"] and why["beats"][0]["margin"] == 10.0
    assert why["lost_to"] == [{"owned_id": "o2", "outfits": 2}]
    assert why["near_misses"] == 1                                   # 57 is within 5 of 60
    buy_min = C.RULES.settings["buy_min_outfits"]
    assert why["to_next_verdict"] == int(buy_min) - 1
```

- [ ] **Step 2: Run to see them fail** — `KeyError: 'detail'`.

- [ ] **Step 3: `buy_advice`** — replace the body from `same_cat = ...` to the end:

```python
    # an outfit only counts if the new item beats every piece you already own
    # in the same slot (otherwise buying it changes nothing)
    same_cat = [w for w in items if w["category"] == candidate["category"]]
    good, rows = [], []
    for result, outfit in outfits:
        others = [i for i in outfit if i is not candidate]
        owned = [(score_outfit(others + [w], rules, style_profile=style_profile)["score"], w)
                 for w in same_cat] if result["score"] >= rules.settings["good_outfit"] - 20 else []
        best_score, best_item = max(owned, key=lambda o: o[0], default=(0, None))
        rows.append({"item_ids": [i["id"] for i in outfit], "score": result["score"],
                     "owned_id": best_item["id"] if best_item else None, "owned_score": best_score})
        if result["score"] >= rules.settings["good_outfit"] and result["score"] > best_score:
            good.append((result, outfit))
    s = rules.settings
    verdict = ("buy" if len(good) >= s["buy_min_outfits"]
               else "think" if len(good) >= s["think_min_outfits"] else "skip")
    reasons, twins = [], []
    if candidate.get("vector") is not None:      # friperie items can't be returned
        for w in items:
            if w["category"] == candidate["category"] and w.get("vector") is not None:
                sim = float(np.asarray(w["vector"], np.float32) @ np.asarray(candidate["vector"], np.float32))
                if sim >= s["similar_item"]:
                    twins.append({"id": w["id"], "similarity": round(sim, 3)})
        if twins:
            reasons.append(f"you already own {len(twins)} very similar {candidate['category']} item(s)")
    return {"verdict": verdict, "good_outfits": len(good), "reasons": reasons,
            "best": [{**r, "items": o} for r, o in (good or outfits)[:3]],
            "detail": {"outfits": rows, "twins": twins}}
```

(The owned pieces are scored for outfits from `good_outfit - 20` points up: enough for near misses with any team `near_miss` ≤ 20, and the same work as before for the good ones. Note it in a comment.) Also add `"detail": {"outfits": [], "twins": []}` to the early `return` when the candidate is filtered out.

- [ ] **Step 4: `buy_explanation`** (append to `explain_outfit.py`):

```python
def buy_explanation(advice, rules=None, settings=None):
    """The verdict made visible: good outfits vs the team's thresholds, what the new
    piece beats, which owned pieces beat it, near misses and near twins."""
    rules = rules or C.RULES
    settings = settings or explain.load_settings()
    s = rules.settings
    good_cut, near = s["good_outfit"], settings["near_miss"]
    beats, lost, near_misses = [], {}, 0
    for o in advice["detail"]["outfits"]:
        if o["score"] >= good_cut:
            if o["score"] > o["owned_score"]:
                beats.append({"item_ids": o["item_ids"], "owned_id": o["owned_id"],
                              "owned_score": o["owned_score"],
                              "margin": round(o["score"] - o["owned_score"], 1)})
            elif o["owned_id"]:
                lost[o["owned_id"]] = lost.get(o["owned_id"], 0) + 1
        elif o["score"] >= good_cut - near and o["score"] > o["owned_score"]:
            near_misses += 1
    good = advice["good_outfits"]
    next_cut = (s["think_min_outfits"] if advice["verdict"] == "skip"
                else s["buy_min_outfits"] if advice["verdict"] == "think" else None)
    return {"path": {"good": good, "buy_min": int(s["buy_min_outfits"]),
                     "think_min": int(s["think_min_outfits"]), "verdict": advice["verdict"]},
            "beats": beats,
            "lost_to": [{"owned_id": k, "outfits": n} for k, n in sorted(lost.items(), key=lambda kv: -kv[1])],
            "near_misses": near_misses,
            "to_next_verdict": int(next_cut - good) if next_cut is not None else None,
            "twins": advice["detail"]["twins"]}
```

- [ ] **Step 5: Run** — `python -m pytest tests/test_outfit_explain.py tests/test_outfits.py tests/test_listings.py -q`. Expected: pass (verdicts unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/phase4/compatibility.py src/phase4/explain_outfit.py backend/tests/test_outfit_explain.py
git commit -m "Outfit XAI: buy advice detail and the path to the verdict"
```

---

### Task 5: API

**Files:**
- Modify: `backend/app/wardrobe.py` (`outfit_out`, new `short_item`)
- Modify: `backend/app/routers/outfits.py`
- Modify: `backend/tests/test_outfits.py`

**Interfaces:**
- Produces: `outfit_out(result, docs_by_id, explain=False)`; with `explain=True` adds `contributions` and `explanations` (strengths + problems).
- Produces: `short_item(doc) -> {"id", "category", "sub_category", "colour", "image_url"}` (`/items/{id}/image`).
- Produces: `POST /outfits/explain {item_ids}` → `{"swaps": [{"item_id", "swap": short_item | None, "gain"}], "weakest": id | None, "pair_map": [...]}`.
- Produces: `/buy-advice` adds `explanation` = `buy_explanation(...)` with `owned_id`s expanded to `owned: short_item` and twins as `{"item": short_item, "similarity"}`.

- [ ] **Step 1: Failing API tests** (append to `backend/tests/test_outfits.py`):

```python
def test_outfit_answers_explain_the_score(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    body = client.post("/outfits/score", json={"item_ids": [w["top"]["id"], w["jeans"]["id"],
                                                            w["shoes"]["id"]]}, headers=headers).json()
    assert round(sum(c["points"] for c in body["contributions"]), 1) == body["score"]
    assert {c["part"] for c in body["contributions"]} == {"style", "colour", "pattern", "structure"}
    assert ("+", "structure_complete") in [(e["sign"], e["code"]) for e in body["explanations"]]
    for o in client.get("/outfits/suggest?n=3", headers=headers).json():
        assert "contributions" in o and "explanations" in o


def test_outfit_explain_endpoint(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    ids = [w["top"]["id"], w["jeans"]["id"], w["shoes"]["id"]]
    r = client.post("/outfits/explain", json={"item_ids": ids}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert [s["item_id"] for s in body["swaps"]] == ids
    assert len(body["pair_map"]) == 3
    assert body["weakest"] in ids + [None]
    other = sign_up(client, "other@example.com", "Other")
    assert client.post("/outfits/explain", json={"item_ids": ids}, headers=other).status_code == 404
    two_jeans = upload(client, headers, BLUE)
    clash = client.post("/outfits/explain", json={"item_ids": [w["jeans"]["id"], two_jeans["id"]]}, headers=headers)
    assert clash.status_code == 422


def test_buy_advice_explains_the_verdict(client):
    headers = sign_up(client)
    wardrobe(client, headers)
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    advice = client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=headers).json()
    why = advice["explanation"]
    assert why["path"]["verdict"] == advice["verdict"] and why["path"]["good"] == advice["good_outfits"]
    for b in why["beats"]:
        assert b["owned"] is None or b["owned"]["image_url"].startswith("/items/")
    for t in why["twins"]:
        assert t["item"]["id"] and 0 <= t["similarity"] <= 1.0001
    assert all("contributions" in o for o in advice["best"])
```


- [ ] **Step 2: Run to see them fail** — `KeyError: 'contributions'` / 404 on `/outfits/explain`.

- [ ] **Step 3: `wardrobe.py`**

```python
def short_item(doc):
    """A wardrobe item in a few fields, for explanations (swaps, twins, what it beats)."""
    return {"id": str(doc["_id"]), "category": doc["category"], "sub_category": doc["sub_category"],
            "colour": doc["colour"], "image_url": f"/items/{doc['_id']}/image"}


def outfit_out(result, docs_by_id, explain=False):
    """A compatibility result (score, parts, reasons, items) as JSON. explain=True
    (the app's routes) adds the points per part and the strengths / problems
    (src/phase4/explain_outfit.py); the chat tools keep the short form."""
    out = {"score": result["score"],
           "parts": {k: (round(v, 3) if v is not None else None) for k, v in result["parts"].items()},
           "reasons": result["reasons"],
           "items": [describe(i, docs_by_id) for i in result.get("items", [])]}
    if explain:
        import compatibility
        import explain_outfit
        out["contributions"] = explain_outfit.contributions(result, compatibility.RULES.weights)
        out["explanations"] = (explain_outfit.strengths(result.get("items", []), result["parts"])
                               + result.get("problems", []))
    return out
```

- [ ] **Step 4: Routers** — in `routers/outfits.py`:
  - import `explain_outfit` next to `compatibility`, and `short_item` from `..wardrobe`;
  - pass `explain=True` to every `outfit_out(...)` call in `score`, `suggest`, `complete`, `buy_advice`;
  - new route after `score`:

```python
@router.post("/outfits/explain")
def explain_outfit_route(body: ItemIds, request: Request, user=Depends(current_user)):
    """Why this score, in more depth: the best swap for each piece (from your own
    wardrobe, same filters as the suggestions) and how every pair of pieces works."""
    docs = [own_item(request, user, i) for i in body.item_ids]
    items = [to_compat(d) for d in docs]
    no_clash(items)
    all_docs, by_id = wardrobe(request, user)
    prof = user_profile(user, all_docs, request)
    pool, _ = compatibility.filter_items([to_compat(d) for d in all_docs], prof)
    swaps = explain_outfit.swaps(items, pool, style_profile=prof["style_vector"])
    return {"swaps": [{"item_id": s["item_id"], "gain": s["gain"],
                       "swap": short_item(by_id[s["best_swap_id"]]) if s["best_swap_id"] else None}
                      for s in swaps],
            "weakest": explain_outfit.weakest(swaps),
            "pair_map": explain_outfit.pair_map(items)}
```

  - in `buy_advice`, before `return`:

```python
    why = explain_outfit.buy_explanation(advice)
    explanation = {**why,
                   "beats": [{**b, "owned": short_item(by_id[b["owned_id"]]) if b["owned_id"] else None}
                             for b in why["beats"]],
                   "lost_to": [{**l, "owned": short_item(by_id[l["owned_id"]])} for l in why["lost_to"]],
                   "twins": [{"item": short_item(by_id[t["id"]]), "similarity": t["similarity"]}
                             for t in why["twins"]]}
```
  and add `"explanation": explanation` to the returned dict.

- [ ] **Step 5: Run** — `python -m pytest -q --deselect tests/test_jobs.py::test_run_to_the_end_with_log_and_progress`. Expected: all pass (agent tests unchanged since `explain` defaults to False).

- [ ] **Step 6: Commit**

```bash
git add backend/app/wardrobe.py backend/app/routers/outfits.py backend/tests/test_outfits.py
git commit -m "Outfit XAI: points and strengths in outfit answers, /outfits/explain, buy explanation"
```

---

### Task 6: Frontend — types, templates, points bar, strengths

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- Create: `frontend/src/i18n/explain.ts`
- Modify: `frontend/src/i18n/strings.ts`
- Create: `frontend/src/ui/ScoreWhy.tsx`
- Modify: `frontend/src/ui/OutfitStrip.tsx`

**Interfaces:**
- Produces: types `ExplainLine`, `Contribution`, `OutfitExplanation`, `BuyExplanation`, `ShortItem`; `Outfit` gains `contributions?`, `explanations?`; `BuyAdvice` gains `explanation?`.
- Produces: `api.explainOutfit(itemIds: string[]): Promise<OutfitExplanation>`.
- Produces: `explainLine(line: ExplainLine, lang: Language): string` in `i18n/explain.ts`.
- Produces: `<PointsBar contributions />`, `<ExplainLines lines />`, `<ScoreDetails outfit onSwap? />` in `ui/ScoreWhy.tsx`.

- [ ] **Step 1: Types** (append to `types.ts`; extend `Outfit` and `BuyAdvice`):

```ts
export type PartName = 'style' | 'colour' | 'pattern' | 'structure'

export interface ExplainLine {
  code: string
  part: PartName
  sign: '+' | '-'
  params: Record<string, string | number | string[]>
}

export interface Contribution {
  part: PartName
  weight: number
  value: number | null
  counted: boolean
  points: number
  max_points: number
  why_not: null | 'no_vectors' | 'no_colours' | 'no_patterns' | 'no_items' | 'weight_zero'
}

export interface ShortItem {
  id: string
  category: Category
  sub_category: string
  colour: string
  image_url: string
}

/** POST /outfits/explain */
export interface OutfitExplanation {
  swaps: { item_id: string; gain: number; swap: ShortItem | null }[]
  weakest: string | null
  pair_map: { a: string; b: string; style: number | null; colour: number | null; pattern: number | null }[]
}

/** /buy-advice explanation */
export interface BuyExplanation {
  path: { good: number; buy_min: number; think_min: number; verdict: Verdict }
  beats: { item_ids: string[]; owned_id: string | null; owned: ShortItem | null; owned_score: number; margin: number }[]
  lost_to: { owned_id: string; owned: ShortItem; outfits: number }[]
  near_misses: number
  to_next_verdict: number | null
  twins: { item: ShortItem; similarity: number }[]
}
```

In `Outfit` add `contributions?: Contribution[]` and `explanations?: ExplainLine[]`; in `BuyAdvice` add `explanation?: BuyExplanation`.

- [ ] **Step 2: Client** — add `OutfitExplanation` to the type import and, after `score`:

```ts
  explainOutfit: (itemIds: string[]) =>
    request<OutfitExplanation>('/outfits/explain', json('POST', { item_ids: itemIds })),
```

- [ ] **Step 3: `frontend/src/i18n/explain.ts`**

```ts
// One sentence per explanation code of the outfit formula (src/phase4/compatibility.py
// and explain_outfit.py), in en / fr / ar. Unknown codes fall back to the code itself.
import type { ExplainLine, Language } from '../api/types'
import { CATEGORY_LABELS, COLOUR_LABELS, PATTERN_LABELS, SUB_LABELS, vocab } from './vocab'

type T = Record<Language, string>
const sep = (l: Language) => (l === 'ar' ? '، ' : ', ')

export function explainLine(line: ExplainLine, l: Language): string {
  const p = line.params
  const col = (k: string) => vocab(COLOUR_LABELS, String(p[k]), l)
  const sub = (k: string) => vocab(SUB_LABELS, String(p[k]), l)
  const pat = (k: string) => vocab(PATTERN_LABELS, String(p[k]), l)
  const texts: Record<string, () => T> = {
    style_coherent: () => ({ en: 'The pieces share one style', fr: 'Les pièces partagent un même style', ar: 'القطع بأسلوب واحد' }),
    style_mixed: () => ({ en: 'The pieces have quite different styles', fr: 'Les pièces ont des styles assez différents', ar: 'القطع مختلفة الأسلوب' }),
    style_unlike_you: () => ({ en: 'Unlike your usual style', fr: 'Différent de ton style habituel', ar: 'مختلف عن أسلوبك المعتاد' }),
    colour_pair: () => ({ en: `${col('a')} and ${col('b')} go together`, fr: `${col('a')} et ${col('b')} vont bien ensemble`, ar: `${col('a')} و${col('b')} يتناسقان` }),
    colour_neutral_base: () => ({ en: `A calm base of ${p.n} neutral colours`, fr: `Une base calme de ${p.n} couleurs neutres`, ar: `قاعدة هادئة من ${p.n} ألوان محايدة` }),
    colour_clash: () => ({ en: `${col('a')} and ${col('b')} clash`, fr: `${col('a')} et ${col('b')} jurent ensemble`, ar: `${col('a')} و${col('b')} لا يتناسقان` }),
    colour_too_bold: () => {
      const list = (p.colours as string[]).map((c) => vocab(COLOUR_LABELS, c, l)).join(sep(l))
      return { en: `Many bold colours (${list})`, fr: `Beaucoup de couleurs vives (${list})`, ar: `ألوان صارخة كثيرة (${list})` }
    },
    pattern_one_bold: () => ({ en: `One statement pattern (${pat('pattern')})`, fr: `Un seul motif fort (${pat('pattern')})`, ar: `نقشة بارزة واحدة (${pat('pattern')})` }),
    pattern_calm: () => ({ en: 'Calm, plain pieces', fr: 'Des pièces unies et calmes', ar: 'قطع سادة هادئة' }),
    pattern_clash: () => ({ en: `Two bold patterns (${pat('a')} + ${pat('b')})`, fr: `Deux motifs forts (${pat('a')} + ${pat('b')})`, ar: `نقشتان قويتان (${pat('a')} + ${pat('b')})` }),
    structure_complete: () => ({ en: 'Complete outfit, shoes included', fr: 'Tenue complète, chaussures comprises', ar: 'إطلالة كاملة مع الحذاء' }),
    structure_no_shoes: () => ({ en: 'No shoes', fr: 'Pas de chaussures', ar: 'بدون حذاء' }),
    structure_incomplete: () => p.missing === 'main_piece'
      ? { en: 'No main piece', fr: 'Pas de pièce principale', ar: 'لا توجد قطعة أساسية' }
      : { en: 'Missing a top or a bottom', fr: 'Il manque un haut ou un bas', ar: 'تنقص قطعة علوية أو سفلية' },
    structure_full_and_bottom: () => ({ en: 'A full piece and a bottom together', fr: 'Une pièce entière et un bas ensemble', ar: 'قطعة كاملة مع قطعة سفلية' }),
    structure_over_limit: () => {
      const c = vocab(CATEGORY_LABELS, String(p.category), l)
      return { en: `${p.n} pieces of ${c}`, fr: `${p.n} pièces de type ${c}`, ar: `${p.n} قطع من ${c}` }
    },
    structure_pair: () => ({ en: `${sub('a')} and ${sub('b')} don't go together`, fr: `${sub('a')} et ${sub('b')} ne vont pas ensemble`, ar: `${sub('a')} و${sub('b')} لا يتماشيان` }),
  }
  return texts[line.code]?.()[l] ?? line.code
}
```

- [ ] **Step 4: Strings** — add to `en` / `fr` / `ar` (after `noReasons` in each):

| key | en | fr | ar |
|---|---|---|---|
| `partStyle` | Style | Style | الأسلوب |
| `partColour` | Colour | Couleur | اللون |
| `partPattern` | Pattern | Motif | النقشة |
| `partStructure` | Structure | Structure | البنية |
| `partNotCounted` | not counted | non compté | غير محتسب |
| `pointsOf` | {p} of {max} | {p} sur {max} | {p} من {max} |
| `whyScore` | Why this score? | Pourquoi ce score ? | لماذا هذه النتيجة؟ |
| `hideWhyScore` | Hide the details | Masquer le détail | إخفاء التفاصيل |
| `weakestPiece` | Weakest piece: {piece}. Swap it for {swap}: +{gain} | Pièce la plus faible : {piece}. Remplace-la par : {swap} (+{gain}) | أضعف قطعة: {piece}. استبدلها بـ{swap}: +{gain} |
| `noBetterSwap` | No piece of your wardrobe would do better. | Aucune pièce de ta garde-robe ne ferait mieux. | لا توجد قطعة في خزانتك أفضل منها. |
| `applySwap` | Apply swap | Faire l’échange | طبّق الاستبدال |
| `pairMap` | How each pair works | Comment chaque paire s’accorde | كيف يتناسق كل زوج |
| `verdictWhy` | Why this verdict? | Pourquoi ce verdict ? | لماذا هذا الحكم؟ |
| `verdictPath` | {good} good outfits. “Buy” needs {buy}, “think about it” needs {think}. | {good} bonnes tenues. « Achète » demande {buy}, « Réfléchis » {think}. | {good} إطلالات جيدة. «اشترِ» يحتاج {buy}، و«فكّر» يحتاج {think}. |
| `toNextVerdict` | {n} more good outfit(s) would raise the verdict. | {n} bonne(s) tenue(s) de plus relèverait le verdict. | {n} إطلالة جيدة إضافية سترفع الحكم. |
| `beatsOwned` | Beats your {piece} by +{margin} | Fait mieux que : {piece} (+{margin}) | أفضل من {piece} بـ+{margin} |
| `fillsGap` | Nothing you own does this job in this outfit | Rien dans ta garde-robe ne joue ce rôle dans cette tenue | لا شيء في خزانتك يؤدي هذا الدور في هذه الإطلالة |
| `lostTo` | Your {piece} does as well in {n} outfit(s) | {piece} (déjà à toi) fait aussi bien dans {n} tenue(s) | {piece} لديك يؤدي نفس الدور في {n} إطلالة |
| `nearMisses` | {n} more outfit(s) were just below “good” | {n} tenue(s) de plus étaient juste en dessous de « bonne » | {n} إطلالة أخرى كانت دون «جيدة» بقليل |
| `twinsTitle` | Very similar pieces you own | Pièces très proches que tu as déjà | قطع مشابهة جدًا تملكها |

Write them as `key: 'text',` lines (escape `’` is fine inside single quotes; `l’` uses the typographic apostrophe, no escaping needed).

- [ ] **Step 5: `frontend/src/ui/ScoreWhy.tsx`**

```tsx
import { useState } from 'react'
import { Lightbulb } from 'lucide-react'
import { api } from '../api/client'
import type { Contribution, ExplainLine, Outfit, OutfitExplanation, PartName } from '../api/types'
import { useI18n } from '../i18n'
import { explainLine } from '../i18n/explain'
import type { StringKey } from '../i18n/strings'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Button } from './controls'
import { ItemPhoto } from './ItemPhoto'
import { ErrorNote, Skeleton } from './states'

const PART_KEY: Record<PartName, StringKey> = {
  style: 'partStyle', colour: 'partColour', pattern: 'partPattern', structure: 'partStructure',
}
const PART_COLOUR: Record<PartName, string> = {
  style: 'bg-ink', colour: 'bg-stamp', pattern: 'bg-ink-soft', structure: 'bg-carbon-soft',
}

/** The score split into its four parts: one segment per part, as wide as its
 *  points; the light rest of each slot is the points that part could still win. */
export function PointsBar({ contributions }: { contributions: Contribution[] }) {
  const { t } = useI18n()
  return (
    <div className="space-y-1.5">
      <div className="flex h-2.5 w-full overflow-hidden bg-stock-deep" aria-hidden>
        {contributions.filter((c) => c.counted).map((c) => (
          <span key={c.part} className="flex h-full" style={{ width: `${c.max_points}%` }}>
            <span className={`h-full ${PART_COLOUR[c.part]}`} style={{ width: `${c.max_points ? (100 * c.points) / c.max_points : 0}%` }} />
          </span>
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-carbon-soft">
        {contributions.map((c) => (
          <li key={c.part} className="inline-flex items-center gap-1.5">
            <span aria-hidden className={`size-2 ${c.counted ? PART_COLOUR[c.part] : 'bg-perf'}`} />
            {t(PART_KEY[c.part])}{' '}
            <span className="font-mono tabular" dir="ltr">
              {c.counted ? t('pointsOf', { p: c.points.toFixed(1), max: c.max_points.toFixed(1) }) : t('partNotCounted')}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Strengths (+) then problems (−), as sentences in the user's language. */
export function ExplainLines({ lines }: { lines: ExplainLine[] }) {
  const { lang } = useI18n()
  const sorted = [...lines.filter((l) => l.sign === '+'), ...lines.filter((l) => l.sign === '-')]
  return (
    <ul className="space-y-1 text-[14px]">
      {sorted.map((l, i) => (
        <li key={i} className={`flex gap-2 ${l.sign === '+' ? 'text-carbon' : 'text-carbon-soft'}`}>
          <span aria-hidden className={`w-3 shrink-0 font-mono ${l.sign === '+' ? 'text-ink' : 'text-stamp'}`}>{l.sign === '+' ? '+' : '−'}</span>
          {explainLine(l, lang)}
        </li>
      ))}
    </ul>
  )
}

/** "Why this score?": loads the swaps and the pair map on demand. */
export function ScoreDetails({ outfit, onSwap }: { outfit: Outfit; onSwap?: (from: string, to: string) => void }) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<OutfitExplanation | null>(null)
  const [error, setError] = useState<unknown>(null)
  const ids = outfit.items.map((i) => i.id)
  const key = ids.join(',')
  const [loadedFor, setLoadedFor] = useState('')

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next && loadedFor !== key) {
      setData(null)
      setError(null)
      setLoadedFor(key)
      api.explainOutfit(ids).then(setData).catch(setError)
    }
  }
  const name = (id: string) => {
    const it = outfit.items.find((i) => i.id === id)
    return it ? vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang) : ''
  }
  const pct = (v: number | null) => (v === null ? '–' : `${Math.round(v * 100)}`)
  const weakest = data?.swaps.find((s) => s.item_id === data.weakest)

  return (
    <div className="mt-2">
      <Button variant="quiet" onClick={toggle} aria-expanded={open}>
        <Lightbulb className="size-4" aria-hidden /> {open ? t('hideWhyScore') : t('whyScore')}
      </Button>
      {open && (
        <div className="mt-2 space-y-4 border-t border-perf/40 pt-3">
          {error ? <ErrorNote error={error} /> : !data ? <Skeleton className="h-32" /> : (
            <>
              {weakest?.swap ? (
                <div className="flex items-center gap-3">
                  <ItemPhoto src={weakest.swap.image_url} alt="" size={56} />
                  <p className="flex-1 text-[14px] text-carbon">
                    {t('weakestPiece', {
                      piece: name(weakest.item_id),
                      swap: vocab(SUB_LABELS, weakest.swap.sub_category, lang) || vocab(CATEGORY_LABELS, weakest.swap.category, lang),
                      gain: weakest.gain.toFixed(1),
                    })}
                  </p>
                  {onSwap && <Button variant="secondary" onClick={() => onSwap(weakest.item_id, weakest.swap!.id)}>{t('applySwap')}</Button>}
                </div>
              ) : <p className="text-[14px] text-carbon-soft">{t('noBetterSwap')}</p>}
              <div>
                <h3 className="mb-1 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('pairMap')}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="text-carbon-soft">
                        <th className="py-1 text-start font-normal" />
                        <th className="py-1 text-end font-normal">{t('partStyle')}</th>
                        <th className="py-1 text-end font-normal">{t('partColour')}</th>
                        <th className="py-1 text-end font-normal">{t('partPattern')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.pair_map.map((p) => (
                        <tr key={`${p.a}-${p.b}`} className="border-t border-perf/30">
                          <td className="py-1 pe-2 text-carbon">{name(p.a)} + {name(p.b)}</td>
                          {[p.style, p.colour, p.pattern].map((v, i) => (
                            <td key={i} className="py-1 text-end font-mono tabular" dir="ltr">{pct(v)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 6: `OutfitStrip`** — import `PointsBar, ExplainLines, ScoreDetails` from `./ScoreWhy`; add props `explainable?: boolean` and `onSwap?: (from: string, to: string) => void`; replace the reasons `<ul>` with:

```tsx
      {outfit.contributions && <div className="mt-3"><PointsBar contributions={outfit.contributions} /></div>}
      <div className="mt-3">
        {outfit.explanations
          ? (outfit.explanations.length ? <ExplainLines lines={outfit.explanations} /> : <p className="text-[14px] text-carbon-soft">{t('noReasons')}</p>)
          : (
            <ul className="space-y-1 text-[14px] text-carbon-soft">
              {(outfit.reasons.length ? outfit.reasons : ['']).map((r, i) => (
                <li key={i} className="flex gap-2">
                  <span aria-hidden className="mt-[9px] h-px w-3 shrink-0 bg-perf" />
                  {r ? reason(r) : t('noReasons')}
                </li>
              ))}
            </ul>
          )}
      </div>
      {explainable && <ScoreDetails outfit={outfit} onSwap={onSwap} />}
```

- [ ] **Step 7: Build and lint** — `npm --prefix frontend run build` and `npm --prefix frontend run lint`. Expected: no errors (the existing `BuildPage.tsx` warning is not ours).

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "Outfit XAI: points bar and strengths / problems in every outfit"
```

---

### Task 7: Frontend — Build, Today, and "Why this verdict?"

**Files:**
- Create: `frontend/src/ui/VerdictWhy.tsx`
- Modify: `frontend/src/pages/BuildPage.tsx`, `TodayPage.tsx`, `ScanPage.tsx`, `ShopPage.tsx`

**Interfaces:**
- Consumes: Task 6 components and types.
- Produces: `<VerdictWhy explanation={advice.explanation} />`.

- [ ] **Step 1: `frontend/src/ui/VerdictWhy.tsx`**

```tsx
import { useState } from 'react'
import { Lightbulb } from 'lucide-react'
import type { BuyExplanation, ShortItem } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Button } from './controls'
import { ItemPhoto } from './ItemPhoto'

/** "Why this verdict?": the team's thresholds, what the piece beats, which owned
 *  pieces beat it, near misses, and the near twins with their pictures. */
export function VerdictWhy({ explanation: e }: { explanation: BuyExplanation }) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const name = (it: ShortItem) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)
  return (
    <div className="mt-3">
      <Button variant="quiet" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Lightbulb className="size-4" aria-hidden /> {open ? t('hideWhyScore') : t('verdictWhy')}
      </Button>
      {open && (
        <div className="ticket mt-2 space-y-3 px-4 py-4 text-[14px] text-carbon">
          <p>{t('verdictPath', { good: e.path.good, buy: e.path.buy_min, think: e.path.think_min })}</p>
          {e.to_next_verdict !== null && e.to_next_verdict > 0 && <p>{t('toNextVerdict', { n: e.to_next_verdict })}</p>}
          {e.beats.length > 0 && (
            <ul className="space-y-1">
              {e.beats.slice(0, 3).map((b, i) => (
                <li key={i} className="flex items-center gap-2">
                  {b.owned && <ItemPhoto src={b.owned.image_url} alt="" size={40} />}
                  {b.owned ? t('beatsOwned', { piece: name(b.owned), margin: b.margin.toFixed(1) }) : t('fillsGap')}
                </li>
              ))}
            </ul>
          )}
          {e.lost_to.map((l) => (
            <p key={l.owned_id} className="flex items-center gap-2 text-carbon-soft">
              <ItemPhoto src={l.owned.image_url} alt="" size={40} /> {t('lostTo', { piece: name(l.owned), n: l.outfits })}
            </p>
          ))}
          {e.near_misses > 0 && <p className="text-carbon-soft">{t('nearMisses', { n: e.near_misses })}</p>}
          {e.twins.length > 0 && (
            <div>
              <h3 className="mb-1 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('twinsTitle')}</h3>
              <ul className="flex flex-wrap gap-3">
                {e.twins.map((tw) => (
                  <li key={tw.item.id} className="flex flex-col items-center gap-1">
                    <ItemPhoto src={tw.item.image_url} alt={name(tw.item)} size={64} />
                    <span className="font-mono text-[11px] tabular" dir="ltr">{Math.round(tw.similarity * 100)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Build page** — pass `explainable` and a swap handler to its `OutfitStrip`:

```tsx
            explainable
            onSwap={(from, to) => setPicked((p) => p.map((x) => (x === from ? to : x)))}
```

- [ ] **Step 3: Today page** — add `explainable` to its main `OutfitStrip` (no `onSwap`: Today shows suggestions, not a built outfit).

- [ ] **Step 4: Scan and Shop** — after the verdict line / reasons block, add
`{advice.explanation && <VerdictWhy explanation={advice.explanation} />}` (import from `../ui/VerdictWhy`). On Shop, the advice variable is the one already used for `advice.reasons` (read the page and use the same name).

- [ ] **Step 5: Build, lint, browser check** — `npm --prefix frontend run build`, `npm --prefix frontend run lint`. Then with the API on 8000 running this branch (restart it if it runs older code — ask the user first if it is their process) and a Vite server started after these files exist (a dev server started before a NEW .tsx misses its Tailwind classes): log in as the demo user (`backend/.env` DEMO_PASSWORD, via the API, token into `localStorage['dressme.token']`), check Build (pick a top + bottom + shoes: points bar, lines, "Why this score?", apply swap), Today, Scan (scan a photo, verdict, "Why this verdict?"), phone width 375 px (no horizontal scroll) and Arabic (set the demo profile language to `ar` through `PUT /me`, then back to `en`). Screenshot as proof.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "Outfit XAI: 'Why this score?' on Build / Today and 'Why this verdict?' on Scan / Shop"
```

---

### Task 8: Offline evaluation of "weakest piece"

**Files:**
- Create: `src/phase4/evaluate_outfit_explanations.py`
- Generated: `reports/phase4/outfit_explanations_evaluation.md`

**Interfaces:**
- Consumes: `evaluate_compatibility.load_items`, `outfit_lists`; `explain_outfit.swaps / weakest / contributions`; `compatibility.score_outfit`.

- [ ] **Step 1: Write the script**

```python
"""
Does "weakest piece" find the piece that does not belong? (XAI sub-project 2)

On the clean PolyVore and Fashionpedia test outfits (the data of
evaluate_compatibility.py): replace one piece by a random test item of the same
category (the intruder); the swap analysis, with a pool of POOL random test items
per category as the "wardrobe", should name the intruder as the weakest piece.
Reported: top-1 accuracy vs chance (1 / number of pieces), per dataset. Also
checks that the points per part add up to the score on every outfit.
-> reports/phase4/outfit_explanations_evaluation.md

    python src/phase4/evaluate_outfit_explanations.py [--limit 500]
"""

import argparse

import numpy as np

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
import explain_outfit as X
from compatibility import RULES, score_outfit
from evaluate_compatibility import load_items, outfit_lists
from item_images import ROOT

REPORT = ROOT / "reports" / "phase4" / "outfit_explanations_evaluation.md"
POOL = 30          # random candidates per category for the swaps (keeps it fast)
SEED = 0


def run(outfits, pool_df, items, rng, limit):
    pool = pool_df.groupby("category")["id"].apply(list).to_dict()
    hits, chance, sums_ok, n = [], [], 0, 0
    for outfit in outfits[:limit]:
        pos = int(rng.integers(len(outfit)))
        cat = items[outfit[pos]]["category"]
        others = [i for i in pool[cat] if i not in outfit]
        if not others:
            continue
        intruder = str(rng.choice(others))
        fake = outfit[:pos] + [intruder] + outfit[pos + 1:]
        fake_items = [items[i] for i in fake]
        cands = []
        for c in {items[i]["category"] for i in fake}:
            ids = [i for i in pool[c] if i not in fake and i != outfit[pos]]
            cands += [items[i] for i in rng.choice(ids, min(POOL, len(ids)), replace=False)]
        swaps = X.swaps(fake_items, cands, RULES)
        hits.append(X.weakest(swaps, positive_only=False) == intruder)
        chance.append(1 / len(fake))
        result = score_outfit(fake_items)
        sums_ok += round(sum(c["points"] for c in X.contributions(result, RULES.weights)), 1) == result["score"]
        n += 1
    return np.array(hits, float), np.array(chance), sums_ok, n


def ci(x):
    """Mean and 95% normal interval, in %."""
    m = x.mean()
    h = 1.96 * np.sqrt(m * (1 - m) / len(x)) if len(x) else 0
    return f"{100 * m:.1f}% [{100 * (m - h):.1f}, {100 * (m + h):.1f}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500, help="test outfits per dataset")
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    df, items = load_items()
    lines = ["# Outfit explanations: evaluation", "",
             "Made by `src/phase4/evaluate_outfit_explanations.py`. One piece of each test outfit is "
             f"replaced by a random test item of the same category; the swap analysis (pool: {POOL} random "
             "test items per category) should name that intruder as the weakest piece.", "",
             "| dataset | outfits | weakest = intruder | chance | points add up |", "|---|---:|---:|---:|---:|"]
    for name, (outfits, pool_df) in outfit_lists(df).items():
        print(f"{name}: {min(args.limit, len(outfits)):,} outfits ...", flush=True)
        hits, chance, sums_ok, n = run(outfits, pool_df, items, rng, args.limit)
        lines.append(f"| {name} | {n:,} | {ci(hits)} | {100 * chance.mean():.1f}% | {sums_ok:,} / {n:,} |")
    lines += ["", "Chance = 1 / number of pieces (mean over the outfits). The intruder is random, "
              "so it can fit by luck: 100% is not expected. A result well above chance means the "
              "swap analysis points at the piece that breaks the outfit."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke run** — `python src/phase4/evaluate_outfit_explanations.py --limit 20`. Expected: two progress lines, the report written, "points add up" equal to the outfit count.

- [ ] **Step 3: Full run** as a separate process with a log (PowerShell):

```powershell
Start-Process python -ArgumentList "src/phase4/evaluate_outfit_explanations.py","--limit","500" -RedirectStandardOutput "$env:TEMP\outfit_eval.log" -RedirectStandardError "$env:TEMP\outfit_eval.err" -NoNewWindow
```

Read the report. If accuracy is near chance, say so in the report's text and tell the user; do not change weights or rules to improve it.

- [ ] **Step 4: Commit**

```bash
git add src/phase4/evaluate_outfit_explanations.py reports/phase4/outfit_explanations_evaluation.md
git commit -m "Outfit XAI: evaluation of the weakest-piece explanation"
```

---

### Task 9: Documentation

**Files:** `CLAUDE.md`, `docs/superpowers/specs/2026-10-08-outfit-xai-design.md`

- [ ] **Step 1:** In `CLAUDE.md`, item 7 (XAI layer): change "sub-project 1 of 4 done: item labels" to "sub-projects 1-2 of 4 done: item labels, outfit score + buy advice" and append: "**Outfits:** `src/phase4/explain_outfit.py`: `contributions` (points per part, add up to the score), `strengths` (+ lines; thresholds `strength_*` in `xai_settings.csv`, REVIEW), `swaps` / `weakest` / `pair_map`, `buy_explanation` (path to verdict, beats, lost_to, near misses with `near_miss`, twins). `score_outfit` adds `problems` (coded lines next to the English `reasons`, which the chat keeps); `buy_advice` adds `detail`. `outfit_out(..., explain=True)` in the app routes only. `POST /outfits/explain`. App: points bar + coded lines in `OutfitStrip` (`ui/ScoreWhy.tsx`, templates in `i18n/explain.ts`), "Why this score?" on Build (apply swap) / Today, "Why this verdict?" (`ui/VerdictWhy.tsx`) on Scan / Shop. `src/phase4/evaluate_outfit_explanations.py` → `reports/phase4/outfit_explanations_evaluation.md` (weakest piece vs a random intruder)." Update the backend test count with the number printed by `python -m pytest -q`.

- [ ] **Step 2:** Spec: `Status: implemented (plan: docs/superpowers/plans/2026-10-08-outfit-xai.md)` and a "Changes while planning" section copying this plan's "Changes from the spec" bullets.

- [ ] **Step 3:** `python -m pytest -q` (backend) and `npm --prefix frontend run build`. Expected: pass (apart from the known flaky `test_jobs.py`).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-08-outfit-xai-design.md
git commit -m "Docs: XAI sub-project 2 (outfit score + buy advice)"
```
