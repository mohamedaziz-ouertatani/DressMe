# Gender-based app (men / women) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every user is a man or a woman; the catalogue, shops, listings, label pickers and the team's compatibility rules follow that choice, while the user's own wardrobe is never filtered.

**Architecture:** A small `src/phase4/genders.py` gives every item a gender (its own label, else the team table `mappings/gender_sub_categories.csv`) and merges gendered rule rows over neutral ones. `compatibility.rules_for(gender)` returns one cached `Rules` per gender; the backend passes the user's rules to every compatibility call and filters catalogue / shop / listing searches to `{user gender, unisex}`. The frontend asks the gender at sign-up (and once for older accounts), orders the pickers, and offers "Show all" on Shop / Similar.

**Tech Stack:** Python 3.13, pandas, FastAPI, pymongo (MongoDB 4.0), pytest; React + TypeScript + Tailwind (Vite).

**Spec:** `docs/superpowers/specs/2026-10-10-gender-based-app-design.md`

## Global Constraints

- User gender values: `men` / `women`. Item gender values: `men` / `women` / `unisex`.
- The wardrobe (`db.items`) is never filtered by gender; outfits use every owned piece.
- Rules live in CSVs, never hard-coded; every new or gendered row is marked `REVIEW` in its note.
- A rule CSV without a `gender` column, or with only empty values, behaves exactly as today.
- `rules_for(None)` = today's neutral rules; the evaluation scripts keep using them (numbers must not move).
- Chat prompts and tool signatures do not change (no model retrain).
- Never commit anything under `data/` or model weights. Commits: no Co-Authored-By trailer, no "Generated with Claude Code" footer (user memory).
- Code style: simple, commented for a mixed-experience team; match the surrounding code.
- Backend tests: `python -m pytest` from `backend/` (uses local MongoDB `dressme_test`). Frontend: `npm run build` from `frontend/`.
- Tailwind's dev server misses classes of a NEW .tsx file until it restarts.

---

### Task 1: Item gender helpers + team table

**Files:**
- Create: `src/phase4/genders.py`
- Create: `mappings/gender_sub_categories.csv`
- Test: `backend/tests/test_genders.py`

**Interfaces:**
- Produces:
  - `genders.GENDERS = ("men", "women")`, `genders.VALUES = ("men", "women", "unisex")`
  - `genders.normalise(value) -> str` (`men` / `women` / `unisex` / `""`)
  - `genders.load_table(map_dir=MAP_DIR) -> dict[str, str]` (sub_category → gender, cached per folder)
  - `genders.item_gender(item: dict, table=None) -> str` (reads `item["gender"]`, `item["sub_category"]`)
  - `genders.item_genders(labels: pd.Series, subs: pd.Series, table=None) -> pd.Series` (vectorised)
  - `genders.shown(user_gender) -> set[str] | None` (`{g, "unisex"}`, or None = no filter)
  - `genders.for_gender(table: pd.DataFrame, gender, key) -> pd.DataFrame` (rule merge; `key(row)` from `itertuples`)

- [ ] **Step 1: Write the team table** `mappings/gender_sub_categories.csv` (one row per value of `mappings/sub_category_vocabulary.csv`):

```csv
sub_category,gender,note
shirt,unisex,REVIEW (team starting values): men / women / unisex; decides the gender of items with no gender label
sweater,unisex,REVIEW
sweatshirt,unisex,REVIEW
t-shirt,unisex,REVIEW
top,unisex,REVIEW
tunic,women,REVIEW
capris,women,REVIEW
jeans,unisex,REVIEW
leggings,women,REVIEW
shorts,unisex,REVIEW
skirt,women,REVIEW
track-pants,unisex,REVIEW
trousers,unisex,REVIEW
dress,women,REVIEW
jumpsuit,women,REVIEW
blazer,unisex,REVIEW
cape,women,REVIEW
cardigan,unisex,REVIEW
coat,unisex,REVIEW
jacket,unisex,REVIEW
waistcoat,unisex,REVIEW
casual-shoes,unisex,REVIEW
flats,women,REVIEW
flip-flops,unisex,REVIEW
formal-shoes,unisex,REVIEW
heels,women,REVIEW
sandals,unisex,REVIEW
sneakers,unisex,REVIEW
backpack,unisex,REVIEW
clutch,women,REVIEW
duffel-bag,unisex,REVIEW
handbag,women,REVIEW
laptop-bag,unisex,REVIEW
messenger-bag,unisex,REVIEW
waist-bag,unisex,REVIEW
belt,unisex,REVIEW
bracelet,women,REVIEW
brooch,women,REVIEW
cap,unisex,REVIEW
cufflinks,men,REVIEW
earrings,women,REVIEW
glasses,unisex,REVIEW
gloves,unisex,REVIEW
hair-accessory,women,REVIEW
hat,unisex,REVIEW
jewellery-set,women,REVIEW
necklace,women,REVIEW
ring,unisex,REVIEW
scarf,unisex,REVIEW
sunglasses,unisex,REVIEW
suspenders,men,REVIEW
tie,men,REVIEW
wallet,unisex,REVIEW
watch,unisex,REVIEW
swim-shorts,men,REVIEW
swimsuit,women,REVIEW
jebba,men,REVIEW: Tunisian men's traditional robe
kaftan,women,REVIEW
```

- [ ] **Step 2: Write the failing tests** `backend/tests/test_genders.py`:

```python
"""Item gender (src/phase4/genders.py): own label first, then the team table, then unisex;
and the merge of gendered rule rows over neutral ones."""

import sys

import pandas as pd

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import genders as G  # noqa: E402
from item_images import ROOT  # noqa: E402


def test_normalise_any_source_spelling():
    assert G.normalise("Men") == G.normalise("homme") == G.normalise("MAN") == "men"
    assert G.normalise("Women") == G.normalise("femme") == "women"
    assert G.normalise("Unisex") == "unisex"
    assert G.normalise("Boys") == G.normalise("Girls") == G.normalise("") == G.normalise(None) == ""


def test_table_covers_exactly_the_vocabulary():
    vocab = pd.read_csv(ROOT / "mappings" / "sub_category_vocabulary.csv", dtype=str)
    table = G.load_table()
    assert set(table) == set(vocab["sub_category"])
    assert set(table.values()) <= set(G.VALUES)


def test_item_gender_label_beats_table_beats_default():
    assert G.item_gender({"gender": "Men", "sub_category": "skirt"}) == "men"
    assert G.item_gender({"gender": "", "sub_category": "skirt"}) == "women"
    assert G.item_gender({"sub_category": "tie"}) == "men"
    assert G.item_gender({"sub_category": "jeans"}) == "unisex"
    assert G.item_gender({"sub_category": ""}) == "unisex"
    assert G.item_gender({}) == "unisex"


def test_item_genders_vectorised_matches_item_gender():
    labels = pd.Series(["Women", "", "", "Boys"])
    subs = pd.Series(["tie", "tie", "jeans", "heels"])
    assert G.item_genders(labels, subs).tolist() == ["women", "men", "unisex", "women"]


def test_shown():
    assert G.shown("men") == {"men", "unisex"}
    assert G.shown(None) is None and G.shown("") is None


def test_for_gender_overrides_neutral_rows_and_ignores_the_other_gender():
    t = pd.DataFrame({"category": ["top", "accessory", "accessory", "accessory"],
                      "max_items": ["1", "4", "2", "6"], "gender": ["", "", "men", "women"]})
    key = lambda r: r.category
    men = G.for_gender(t, "men", key).set_index("category")["max_items"].to_dict()
    women = G.for_gender(t, "women", key).set_index("category")["max_items"].to_dict()
    neutral = G.for_gender(t, None, key).set_index("category")["max_items"].to_dict()
    assert men == {"top": "1", "accessory": "2"}
    assert women == {"top": "1", "accessory": "6"}
    assert neutral == {"top": "1", "accessory": "4"}


def test_for_gender_without_the_column_keeps_everything():
    t = pd.DataFrame({"name": ["a", "b"], "value": ["1", "2"]})
    assert G.for_gender(t, "men", lambda r: r.name).equals(t)


def test_for_gender_unordered_pair_key():
    t = pd.DataFrame({"a": ["shorts", "blazer"], "b": ["blazer", "shorts"],
                      "score": ["0.4", "0.1"], "gender": ["", "men"]})
    out = G.for_gender(t, "men", lambda r: frozenset((r.a, r.b)))
    assert out["score"].tolist() == ["0.1"]
```

- [ ] **Step 3: Run them to verify they fail**

Run (from `backend/`): `python -m pytest tests/test_genders.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'genders'`.

- [ ] **Step 4: Write** `src/phase4/genders.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_genders.py -q`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add src/phase4/genders.py mappings/gender_sub_categories.csv backend/tests/test_genders.py
git commit -m "Gender: item gender helpers + team table of men's / women's pieces"
```

---

### Task 2: Gender-aware compatibility rules and concepts

**Files:**
- Modify: `src/phase4/compatibility.py:58-106` (Rules, RULES, reload_rules)
- Modify: `src/phase4/explain_similarity.py:25-28` (load_concepts)
- Modify: `backend/app/ml.py:85-94` (Analyzer.concept_vectors)
- Modify: `backend/app/routers/admin.py:182-205` (put_formula keeps gendered rows)
- Modify: `backend/app/routers/admin.py` `get_formula` (show neutral rows only)
- Modify: `backend/tests/conftest.py:47-51` (FakeAnalyzer.concept_vectors)
- Modify CSVs (add `gender` column, empty on every existing row): `mappings/outfit_structure.csv`, `mappings/sub_category_pairing.csv`, `mappings/item_seasons.csv`, `mappings/compatibility_weights.csv`, `mappings/style_concepts.csv`
- Test: `backend/tests/test_gender_rules.py`

**Interfaces:**
- Consumes: `genders.for_gender(table, gender, key)` (Task 1)
- Produces:
  - `compatibility.Rules(map_dir=MAP_DIR, gender=None)` with attribute `.gender`
  - `compatibility.rules_for(gender) -> Rules` (same object every call for a gender; `rules_for(None) is RULES`)
  - `compatibility.reload_rules(map_dir=MAP_DIR)` reloads all cached Rules in place
  - `explain_similarity.load_concepts(path=CONCEPTS_PATH, gender=None)`
  - `Analyzer.concept_vectors(gender=None)` / `FakeAnalyzer.concept_vectors(gender=None)`

- [ ] **Step 1: Add the `gender` column to the five rule CSVs.** Append `,gender` to each header and `,` to every data row (empty = both genders). Use a short script so quoting stays right:

```bash
python - <<'EOF'
import csv, pathlib
for name in ["outfit_structure", "sub_category_pairing", "item_seasons",
             "compatibility_weights", "style_concepts"]:
    p = pathlib.Path("mappings") / f"{name}.csv"
    rows = list(csv.reader(p.open(encoding="utf-8", newline="")))
    rows[0].append("gender")
    for r in rows[1:]:
        r.append("")
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
EOF
git diff --stat mappings/
```

Then append the starter gendered concept rows to `mappings/style_concepts.csv`:

```csv
formal,a photo of formal elegant menswear,style,usage=formal,REVIEW: men's wording of the neutral row,men
formal,a photo of formal elegant womenswear,style,usage=formal,REVIEW: women's wording of the neutral row,women
modest,a photo of modest loose menswear that covers the body,style,,REVIEW: men's wording of the neutral row,men
modest,a photo of modest loose womenswear that covers the body,style,,REVIEW: women's wording of the neutral row,women
```

- [ ] **Step 2: Write the failing tests** `backend/tests/test_gender_rules.py`:

```python
"""The team's rules per gender (compatibility.rules_for): gendered rows override the
neutral ones, the other gender's rows are ignored, and neutral rules = today's rules."""

import shutil
import sys

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import compatibility as C  # noqa: E402
import explain_similarity as S  # noqa: E402


def copy_mappings(tmp_path):
    folder = tmp_path / "mappings"
    shutil.copytree(C.MAP_DIR, folder)
    return folder


def add_row(path, line):
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(line + "\n")


def test_neutral_rules_are_the_default_rules():
    assert C.rules_for(None) is C.RULES
    assert C.rules_for("") is C.RULES
    assert C.rules_for("men") is C.rules_for("men")      # cached
    assert C.RULES.gender is None


def test_gendered_rows_override_neutral_ones(tmp_path):
    folder = copy_mappings(tmp_path)
    add_row(folder / "outfit_structure.csv", "accessory,extra,2,REVIEW test,men")
    add_row(folder / "compatibility_weights.csv", "good_outfit,70,REVIEW test,women")
    add_row(folder / "sub_category_pairing.csv", "shorts,blazer,0.1,REVIEW test,men")
    add_row(folder / "item_seasons.csv", "sub_category,skirt,summer,REVIEW test,women")
    men, women = C.Rules(folder, "men"), C.Rules(folder, "women")
    neutral = C.Rules(folder)
    assert men.max_items["accessory"] == 2 and women.max_items["accessory"] == 4
    assert women.settings["good_outfit"] == 70 and men.settings["good_outfit"] == 60
    assert men.sub_pairs[("blazer", "shorts")] == 0.1 and women.sub_pairs[("blazer", "shorts")] == 0.4
    assert women.default_seasons({"sub_category": "skirt"}) == {"summer"}
    assert men.default_seasons({"sub_category": "skirt"}) is None
    assert neutral.max_items == C.RULES.max_items and neutral.settings == C.RULES.settings


def test_reload_rules_refreshes_every_gender_in_place(tmp_path):
    folder = copy_mappings(tmp_path)
    men = C.rules_for("men")
    try:
        add_row(folder / "outfit_structure.csv", "accessory,extra,3,REVIEW test,men")
        C.reload_rules(folder)
        assert C.rules_for("men") is men and men.max_items["accessory"] == 3
    finally:
        C.reload_rules()
    assert C.rules_for("men").max_items["accessory"] == 4


def test_concepts_per_gender():
    neutral = {r["concept"]: r["prompt"] for r in S.load_concepts()}
    men = {r["concept"]: r["prompt"] for r in S.load_concepts(gender="men")}
    assert set(neutral) == set(men)                      # same concepts, one row each
    assert "menswear" in men["formal"] and "menswear" not in neutral["formal"]
    assert men["denim"] == neutral["denim"]
```

- [ ] **Step 3: Run them to verify they fail**

Run: `python -m pytest tests/test_gender_rules.py -q`
Expected: FAIL (`AttributeError: module 'compatibility' has no attribute 'rules_for'`).

- [ ] **Step 4: Make `Rules` gender-aware** in `src/phase4/compatibility.py`. Add `import genders` under `from item_images import ROOT`, then replace the `Rules.__init__` body and the `RULES` / `reload_rules` block:

```python
class Rules:
    """All team-editable settings, read from the CSV files in mappings/. gender = men / women
    keeps the neutral rows plus that gender's rows (a gendered row wins); None = neutral only."""

    def __init__(self, map_dir=MAP_DIR, gender=None):
        self.gender = gender or None
        read = lambda name: pd.read_csv(map_dir / name, dtype=str, keep_default_na=False)
        mine = lambda name, key: genders.for_gender(read(name), self.gender, key)
        w = mine("compatibility_weights.csv", lambda r: r.name).set_index("name")["value"].astype(float)
        self.settings = w.to_dict()
        self.weights = {p: self.settings[f"weight_{p}"] for p in PARTS}
        self.group = read("colour_groups.csv").set_index("colour")["group"].to_dict()
        self.colour_pairs = self._pairs(read("colour_harmony.csv"))
        self.pattern_pairs = self._pairs(read("pattern_mixing.csv"))
        s = mine("outfit_structure.csv", lambda r: r.category)
        self.slot = dict(zip(s["category"], s["slot"]))
        self.max_items = dict(zip(s["category"], s["max_items"].astype(int)))
        # default seasons, e.g. shorts -> summer; a sub_category rule beats a category rule
        # sub_category pairs that do not go together (pairs not listed count as 1)
        self.sub_pairs = self._pairs(mine("sub_category_pairing.csv", lambda r: frozenset((r.a, r.b))))
        seasons = mine("item_seasons.csv", lambda r: (r.kind, r.value))
        self.seasons = {(r.kind, r.value): set(r.season.split("|")) for r in seasons.itertuples()}
```

(keep `default_seasons`, `_pairs`, `colour_score` unchanged), and:

```python
RULES = Rules()
_BY_GENDER = {None: RULES}


def rules_for(gender):
    """The rules for a user's gender (men / women), or the neutral RULES (None / "").
    One object per gender, so reload_rules can refresh them in place."""
    gender = gender or None
    if gender not in _BY_GENDER:
        _BY_GENDER[gender] = Rules(MAP_DIR, gender)
    return _BY_GENDER[gender]


def reload_rules(map_dir=MAP_DIR):
    """Re-read the CSV files into the SAME Rules objects (the functions below use RULES
    as their default), e.g. after an admin edits the weights in the app."""
    for gender, rules in _BY_GENDER.items():
        rules.__init__(map_dir, gender)
```

- [ ] **Step 5: Gendered concepts.** In `src/phase4/explain_similarity.py`, add `import genders` after `from item_images import ROOT` and replace `load_concepts`:

```python
def load_concepts(path=CONCEPTS_PATH, gender=None):
    """The team's concepts: [{"concept", "prompt", "group", "check"}]. gender = men / women
    uses that gender's wording of a concept when the team wrote one."""
    df = genders.for_gender(pd.read_csv(path, dtype=str, keep_default_na=False), gender,
                            lambda r: r.concept)
    return df[["concept", "prompt", "group", "check"]].to_dict("records")
```

In `backend/app/ml.py` replace `concept_vectors`:

```python
    def concept_vectors(self, gender=None):
        """{concept: unit text vector} for the team's concepts (mappings/style_concepts.csv),
        computed once per gender with FashionCLIP's text side (XAI: why two pieces look alike)."""
        cache = self.__dict__.setdefault("_concepts", {})
        if gender not in cache:
            import explain_similarity
            fashionclip = self._modules[1]
            rows = explain_similarity.load_concepts(gender=gender)
            vecs = fashionclip.embed_texts([r["prompt"] for r in rows], self._clip, self._processor, self.device)
            cache[gender] = {r["concept"]: v.astype("float32") for r, v in zip(rows, vecs)}
        return cache[gender]
```

In `backend/tests/conftest.py` change the fake's signature:

```python
    def concept_vectors(self, gender=None):
        """{concept: vector} for the team's concepts (fixed fakes, like the real text vectors)."""
        import explain_similarity
        return {r["concept"]: fake_vector(1000 + i)
                for i, r in enumerate(explain_similarity.load_concepts(gender=gender))}
```

- [ ] **Step 6: Keep the admin formula editor working with gendered rows.** In `backend/app/routers/admin.py`, `get_formula` shows only neutral rows:

```python
        "settings": [{"name": r["name"], "value": float(r["value"]), "note": r["note"]}
                     for r in read_csv(folder / WEIGHTS_FILE) if not r.get("gender")],
```

and in `put_formula` edit only neutral rows and keep the `gender` column when writing:

```python
    rows = read_csv(path)
    neutral = [r for r in rows if not r.get("gender")]      # gendered rows are edited in the CSV
    current = {r["name"]: float(r["value"]) for r in neutral}
    ...
    for r in neutral:
        v = new[r["name"]]
        r["value"] = str(int(v)) if v.is_integer() and r["value"].isdigit() else f"{v:g}"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
```

(the `...` lines — unknown / negative / weights / style checks — stay exactly as they are.)

- [ ] **Step 7: Run the new tests and the whole suite**

Run: `python -m pytest tests/test_gender_rules.py -q` → Expected: 4 passed.
Run: `python -m pytest -q -x` → Expected: all pass (neutral rules unchanged; admin formula tests still pass).

- [ ] **Step 8: Commit**

```bash
git add mappings/outfit_structure.csv mappings/sub_category_pairing.csv mappings/item_seasons.csv mappings/compatibility_weights.csv mappings/style_concepts.csv src/phase4/compatibility.py src/phase4/explain_similarity.py backend/app/ml.py backend/app/routers/admin.py backend/tests/conftest.py backend/tests/test_gender_rules.py
git commit -m "Gender: team rules and style concepts per gender (gendered rows override neutral ones)"
```

---

### Task 3: Gender in the catalogue (dataset shots + H&M)

**Files:**
- Modify: `mappings/hm_index_group.csv` (add `gender` column)
- Modify: `src/phase3/map_hm.py:59-120` (write `gender`)
- Modify: `src/phase4/similarity.py:24-60` and `search` (gender column + `genders=` filter)
- Modify: `backend/app/ml.py:121-135` (`Catalog.search` / `search_shop` take `genders`)
- Modify: `backend/tests/conftest.py:76-97` (FakeCatalog records `genders`)
- Test: `backend/tests/test_genders.py` (add a SimilarityIndex test)

**Interfaces:**
- Consumes: `genders.item_genders` (Task 1)
- Produces:
  - `SimilarityIndex.meta["gender"]` (always `men` / `women` / `unisex`)
  - `SimilarityIndex.search(query, k=5, datasets=None, category=None, exclude_ids=(), genders=None)`
  - `Catalog.search(vector, k=6, category=None, genders=None)`, `Catalog.search_shop(vector, k=6, category=None, genders=None)`
  - `FakeCatalog.last_genders` (the `genders` of the last search / search_shop call)

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_genders.py`):

```python
def test_similarity_index_filters_by_gender():
    import numpy as np
    from similarity import SimilarityIndex

    meta = pd.DataFrame({"id": ["a", "b", "c"], "dataset": ["polyvore"] * 3,
                         "category": ["top"] * 3, "sub_category": ["top", "tie", "skirt"],
                         "gender": ["", "", ""], "image_group": ["a", "b", "c"]})
    vectors = np.eye(3, 512, dtype=np.float16)
    index = SimilarityIndex(vectors, SimilarityIndex.with_gender(meta))
    assert index.meta["gender"].tolist() == ["unisex", "men", "women"]
    hits = index.search(np.ones(512, np.float32), k=3, genders={"men", "unisex"})
    assert set(hits["id"]) == {"a", "b"}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_genders.py::test_similarity_index_filters_by_gender -q`
Expected: FAIL (`AttributeError: type object 'SimilarityIndex' has no attribute 'with_gender'`).

- [ ] **Step 3: Implement in `src/phase4/similarity.py`.** Add `import genders` after `from item_images import DATA`; add `"gender"` to `META_COLS`; add the class method and use it in both loaders:

```python
    @staticmethod
    def with_gender(meta):
        """Every row gets men / women / unisex: its own label (Fashion Product, H&M), else
        the team table mappings/gender_sub_categories.csv (src/phase4/genders.py)."""
        labels = meta["gender"] if "gender" in meta.columns else pd.Series("", index=meta.index)
        return meta.assign(gender=genders.item_genders(labels, meta["sub_category"]))
```

In `load`: `return cls(vectors, cls.with_gender(meta))`. In `load_shop`, read the columns with a callable so an `hm.csv` written before this change still loads:

```python
        wanted = {"id", "dataset", "image_path", "category", "sub_category", "primary_colour",
                  "name", "department", "product_code", "gender"}
        meta = pd.read_csv(DATA / "processed" / "hm.csv", dtype=str, keep_default_na=False,
                           usecols=lambda c: c in wanted)
```

and end with `return cls(vectors, cls.with_gender(meta))`. In `search`, add `genders=None` to the signature and docstring, and after the `category` filter:

```python
        if genders is not None:
            keep &= self.meta["gender"].isin(genders).to_numpy()
```

- [ ] **Step 4: Pass it through `Catalog`** in `backend/app/ml.py`:

```python
    def search(self, vector, k=6, category=None, genders=None):
        hits = self._index.search(vector, k=k + 3, datasets=self.DATASETS, category=category,
                                  genders=genders)
        ...  # rest unchanged

    def search_shop(self, vector, k=6, category=None, genders=None):
        if self._shop is None:
            return []
        hits = self._shop.search(vector, k=k, category=category, genders=genders)
        ...  # rest unchanged
```

and in `backend/tests/conftest.py`:

```python
class FakeCatalog:
    last_genders = "not called"     # what the last search asked for (tests check the filter)

    def search(self, vector, k=6, category=None, genders=None):
        self.last_genders = genders
        return [...]                # unchanged list

    def search_shop(self, vector, k=6, category=None, genders=None):
        self.last_genders = genders
        return [...]                # unchanged list
```

- [ ] **Step 5: H&M gender at the source.** Replace `mappings/hm_index_group.csv` with:

```csv
index_group_name,keep,usage,note,gender
Ladieswear,yes,,,women
Divided,yes,,H&M's young / trend line,
Menswear,yes,,,men
Sport,yes,sport,,
Baby/Children,no,,not our users (young adults),
```

In `src/phase3/map_hm.py`, next to the `"usage": df["index_group_name"].map(groups["usage"]),` line of the output frame, add:

```python
        # Ladieswear / Menswear; empty (Divided, Sport) = decided later by the team's
        # table of men's / women's pieces (src/phase4/genders.py)
        "gender": df["index_group_name"].map(groups["gender"]),
```

and add `hm_index_group.csv -> gender` to the module docstring line for that file.

- [ ] **Step 6: Run the tests, then re-map H&M**

Run: `python -m pytest tests/test_genders.py -q` → Expected: 9 passed.
Run (project root): `python src/phase3/map_hm.py` → Expected: writes `data/processed/hm.csv` with a `gender` column; same row count as before (63k). Check: `python -c "import pandas as pd; print(pd.read_csv('data/processed/hm.csv', dtype=str, keep_default_na=False)['gender'].value_counts())"` → women / men / empty counts. The embeddings need no re-run (same ids).

- [ ] **Step 7: Commit**

```bash
git add mappings/hm_index_group.csv src/phase3/map_hm.py src/phase4/similarity.py backend/app/ml.py backend/tests/conftest.py backend/tests/test_genders.py
git commit -m "Gender: catalogue and H&M searches can keep one gender + unisex"
```

---

### Task 4: Gender on the profile (required) + the vocabulary endpoint

**Files:**
- Modify: `backend/app/schemas.py:10-31` (Register, ProfileUpdate)
- Modify: `backend/app/routers/auth.py:14-29` (profile_out, register)
- Modify: `backend/app/security.py` (user_gender, gendered_user)
- Create: `backend/app/routers/vocab.py`
- Modify: `backend/app/main.py:56-57` (include the vocab router)
- Modify: `backend/app/seed_demo.py:50-56` (register with a gender)
- Modify: `backend/tests/conftest.py` (`sign_up(..., gender="women")`)
- Modify: `backend/tests/test_auth.py:19,35` (register calls send a gender)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `genders.GENDERS`, `genders.load_table` (Task 1)
- Produces:
  - `security.user_gender(user) -> "men" | "women" | None`
  - `security.gendered_user` (FastAPI dependency: `current_user` + 409 `gender_required`)
  - `/me` JSON adds `gender` and `needs_gender: bool`
  - `GET /vocab/sub-category-gender` → `{sub_category: "men"|"women"|"unisex"}` (no login)
  - `conftest.sign_up(client, email=..., name=..., gender="women")`

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_auth.py`; also add `"gender": "women"` to the two existing `/auth/register` JSON bodies at lines 19 and 35 so they still test what they meant to):

```python
def test_gender_is_required_and_editable(client):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "secret-pass",
                                            "name": "X"})
    assert r.status_code == 422                                   # no gender
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "secret-pass",
                                            "name": "X", "gender": "other"})
    assert r.status_code == 422
    headers = sign_up(client, gender="men")
    me = client.get("/me", headers=headers).json()
    assert me["gender"] == "men" and me["needs_gender"] is False
    assert client.put("/me", json={"gender": "women"}, headers=headers).json()["gender"] == "women"
    assert client.put("/me", json={"gender": "x"}, headers=headers).status_code == 422


def test_old_accounts_are_asked_once(client):
    headers = sign_up(client)
    client.app.state.db.users.update_many({}, {"$unset": {"profile.gender": ""}})   # an account from before
    me = client.get("/me", headers=headers).json()
    assert me["gender"] is None and me["needs_gender"] is True
    r = client.get("/outfits/suggest", headers=headers)
    assert r.status_code == 409 and r.json()["detail"] == "gender_required"
    client.put("/me", json={"gender": "women"}, headers=headers)
    assert client.get("/outfits/suggest", headers=headers).status_code == 200


def test_sub_category_gender_table_is_public(client):
    table = client.get("/vocab/sub-category-gender").json()
    assert table["skirt"] == "women" and table["tie"] == "men" and table["jeans"] == "unisex"
```

(`/outfits/suggest` is switched to `gendered_user` in Task 5; until then that one assertion fails — that is expected, the test is completed by Task 5.)

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_auth.py -q`
Expected: FAIL (register without gender answers 201; `/vocab/...` 404).

- [ ] **Step 3: Schemas** in `backend/app/schemas.py`:

```python
Gender = Literal["men", "women"]


class Register(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=60)
    gender: Gender                       # required: shops, look-alikes and rules follow it


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    min_coverage: int | None = Field(None, ge=1, le=5)   # modesty level, 1-5
    language: str | None = None
    gender: Gender | None = None
```

- [ ] **Step 4: Auth** in `backend/app/routers/auth.py`:

```python
def profile_out(user):
    profile = {"gender": None, **user["profile"]}
    return {"id": str(user["_id"]), "email": user["email"], "role": user.get("role", "user"),
            "demo": bool(user.get("demo")), **profile,
            "needs_gender": profile["gender"] is None}   # accounts from before: asked once
```

and in `register` the profile becomes
`{"name": body.name, "gender": body.gender, "min_coverage": None, "language": "en"}`. Update the module docstring: "(name, gender, modesty level, language)".

- [ ] **Step 5: Security helpers** (append to `backend/app/security.py`):

```python
def user_gender(user):
    """men / women, or None for an account created before the question existed."""
    return (user.get("profile") or {}).get("gender") or None


def gendered_user(user=Depends(current_user)):
    """Endpoints whose answer depends on the gender (outfit rules, shops, look-alikes, chat).
    An older account without one gets 409 until the app has asked it (PUT /me)."""
    if user_gender(user) is None:
        raise HTTPException(409, "gender_required")
    return user
```

- [ ] **Step 6: Vocabulary endpoint** `backend/app/routers/vocab.py`:

```python
"""Team vocabulary the app needs that is not translated text (that lives in
frontend/src/i18n/vocab.ts): which pieces are men's, women's or unisex."""

from fastapi import APIRouter, Request

from .. import ml  # noqa: F401  (puts src/ on the import path)
import genders

router = APIRouter(tags=["vocab"])


@router.get("/vocab/sub-category-gender")
def sub_category_gender(request: Request):
    """{sub_category: men / women / unisex} from mappings/gender_sub_categories.csv
    (the label pickers show the user's pieces first)."""
    return genders.load_table(request.app.state.settings.mappings_dir)
```

In `backend/app/main.py` import `vocab` with the other routers and add `vocab.router` to the `for r in (...)` tuple.

- [ ] **Step 7: Test helper and demo seed.** `backend/tests/conftest.py`:

```python
def sign_up(client, email="amira@example.com", name="Amira", gender="women"):
    r = client.post("/auth/register", json={"email": email, "password": "secret-pass", "name": name,
                                            "gender": gender})
```

`backend/app/seed_demo.py`: `token(client, email, password, name, gender)` sends `"gender": gender` on register, and after the `update_many(... demo ...)` line also sets it on existing demo accounts:

```python
    # the demo wardrobe is PolyVore pieces (mostly women's): REVIEW if the seed pieces change
    db.users.update_many({"email": {"$in": [DEMO_EMAIL, ADMIN_EMAIL]}, "profile.gender": None},
                         {"$set": {"profile.gender": "women"}})
```

with the two calls `token(client, DEMO_EMAIL, ..., 'Amira', 'women')` and `token(client, ADMIN_EMAIL, ..., "Admin", "women")`.

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/test_auth.py -q`
Expected: all pass except the 409 assertion in `test_old_accounts_are_asked_once` (finished in Task 5).

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/auth.py backend/app/security.py backend/app/routers/vocab.py backend/app/main.py backend/app/seed_demo.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "Gender: required on sign-up, editable in the profile, asked once for older accounts"
```

---

### Task 5: The user's rules and catalogue filter in every route and agent

**Files:**
- Modify: `backend/app/routers/outfits.py` (rules_of, gendered_user, /similar filter)
- Modify: `backend/app/wardrobe.py:66-81` (`outfit_out(..., rules=None)`)
- Modify: `backend/app/routers/insights.py`, `backend/app/routers/tryon.py`, `backend/app/routers/chat.py` (POST /chat)
- Modify: `backend/app/agents/stylist.py`, `explainer.py`, `analyst.py`, `seller.py`, `shopping.py`
- Test: `backend/tests/test_gender_routes.py`

**Interfaces:**
- Consumes: `compatibility.rules_for` (Task 2), `Catalog.search/search_shop(genders=)` (Task 3), `security.user_gender`, `security.gendered_user` (Task 4), `genders.shown`
- Produces: `routers.outfits.rules_of(user) -> Rules`; `outfit_out(result, docs_by_id, explain=False, rules=None)`; `/similar?gender=all`

- [ ] **Step 1: Write the failing tests** `backend/tests/test_gender_routes.py`:

```python
"""Gender in the routes: the user's rules and a {gender, unisex} filter on everything
from outside the wardrobe; the wardrobe itself is never filtered."""

import sys

from app.config import SRC_DIRS
from tests.conftest import BLACK, BLUE, GREEN, RED, sign_up, upload

sys.path[:0] = [str(d) for d in SRC_DIRS]
import compatibility as C  # noqa: E402


def test_similar_filters_the_catalogue_unless_all(client):
    headers = sign_up(client, gender="men")
    item = upload(client, headers, RED)
    assert client.get(f"/similar?item_id={item['id']}", headers=headers).status_code == 200
    assert client.app.state.catalog.last_genders == {"men", "unisex"}
    client.get(f"/similar?item_id={item['id']}&gender=all", headers=headers)
    assert client.app.state.catalog.last_genders is None


def test_wardrobe_is_never_filtered(client):
    headers = sign_up(client, gender="men")
    dress = upload(client, headers, GREEN)                 # a "women's" piece in a man's wardrobe
    assert dress["sub_category"] == "dress"
    assert len(client.get("/items", headers=headers).json()) == 1
    for rgb in (RED, BLUE, BLACK):
        upload(client, headers, rgb)
    r = client.get("/outfits/suggest", headers=headers)
    assert r.status_code == 200
    scored = client.post("/outfits/score", json={"item_ids": [dress["id"]]}, headers=headers)
    assert scored.status_code == 200                       # a man's dress still counts as his
    assert dress["id"] in {i["id"] for i in scored.json()["items"]}


def test_outfit_routes_use_the_users_rules(client, monkeypatch):
    seen = []
    real = C.score_outfit
    monkeypatch.setattr(C, "score_outfit",
                        lambda items, rules=C.RULES, **kw: seen.append(rules.gender) or real(items, rules, **kw))
    headers = sign_up(client, gender="men")
    ids = [upload(client, headers, rgb)["id"] for rgb in (RED, BLUE, BLACK)]
    assert client.post("/outfits/score", json={"item_ids": ids}, headers=headers).status_code == 200
    assert seen and set(seen) == {"men"}


def test_limits_follow_the_gender(client):
    headers = sign_up(client, gender="women")
    limits = client.get("/outfits/limits", headers=headers).json()["max_items"]
    assert limits == {c: int(n) for c, n in C.rules_for("women").max_items.items()}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_gender_routes.py -q`
Expected: FAIL (`last_genders` is `None`/"not called", rules gender is `None`).

- [ ] **Step 3: `outfit_out` takes the rules** (`backend/app/wardrobe.py`):

```python
def outfit_out(result, docs_by_id, explain=False, rules=None):
    """... (docstring unchanged) rules = the user's compatibility.Rules (default: neutral)."""
    ...
    if explain:
        import compatibility
        import explain_outfit
        rules = rules or compatibility.RULES
        out["contributions"] = explain_outfit.contributions(result, rules.weights)
        out["explanations"] = (explain_outfit.strengths(result.get("items", []), result["parts"], rules)
                               + result.get("problems", []))
    return out
```

- [ ] **Step 4: `routers/outfits.py`.** Import `gendered_user, user_gender` from `..security` and `genders`; add next to `profile()`:

```python
def rules_of(user):
    """The team's rules for this user's gender (src/phase4/compatibility.rules_for)."""
    return compatibility.rules_for(user_gender(user))
```

Then, in this file:
- every `Depends(current_user)` becomes `Depends(gendered_user)` **except** `catalog_image` (an image fetch must never 409);
- in each route, `rules = rules_of(user)` once, and pass `rules=rules` to every `compatibility.*` call (`clashes`, `score_outfit`, `filter_items`, `suggest_outfits`, `complete_outfit`, `buy_advice`, `user_style_profile`) and every `explain_outfit.*` call that takes it (`swaps`, `strengths`, `pair_map`, `buy_explanation`), and `rules=rules` to every `outfit_out(..., explain=True)`; `/outfits/limits` returns `rules.max_items`;
- `/similar` gets `gender: Literal["mine", "all"] = "mine"` and:

```python
    shown = None if gender == "all" else genders.shown(user_gender(user))
    catalog = request.app.state.catalog.search(query, k=k, category=doc["category"], genders=shown)
    shop = request.app.state.catalog.search_shop(query, k=k, category=doc["category"], genders=shown)
    ...
    concepts = request.app.state.analyzer.concept_vectors(user_gender(user))
```

(the listings line is changed in Task 6.)

- [ ] **Step 5: Other routes.** `routers/insights.py`: `Depends(gendered_user)`, `rules = rules_of(user)` (import from `.outfits`), `rules.group`, `rules.settings["good_outfit"]`, `wardrobe_insights(..., rules=rules)`. `routers/tryon.py`: `POST /tryon` uses `gendered_user` and `compatibility.clashes(..., rules=rules_of(user))`. `routers/chat.py`: the `POST /chat` route uses `gendered_user` (history / delete stay on `current_user`).

- [ ] **Step 6: Agents** (they receive `user`; add `rules = rules_of(user)` at the top of each `tools(request, user)` and pass it):
- `stylist.py`: `suggest_outfits(..., rules=rules)`, `clashes(items, rules)`, `score_outfit(..., rules=rules, ...)`, `complete_outfit(..., rules=rules)`.
- `explainer.py`: `clashes(items, rules)`, `score_outfit(items, rules, style_profile=...)`, `contributions(result, rules.weights)`, `strengths(items, result["parts"], rules)`, `filter_items(..., prof, rules)`, `swaps(items, pool, rules, style_profile=...)`, `pair_map(items, rules)`, `buy_advice(..., rules=rules)`, `buy_explanation(advice, rules)`, `rules.settings["similar_item"]`, `how_scoring_works` uses `rules.settings` / `rules.weights`; `explain_similarity` tool uses `request.app.state.analyzer.concept_vectors(user_gender(user))`.
- `analyst.py`: `wardrobe_insights(..., rules=rules)`, `near_twins(..., rules)`.
- `seller.py`: `wardrobe_insights(..., rules=rules)`, `near_twins(items, rules)`.
- `shopping.py`: `buy_advice(..., rules=rules)`; `find_similar`: `search_shop(..., genders=genders.shown(user_gender(user)))`.

- [ ] **Step 7: Run all tests**

Run: `python -m pytest -q`
Expected: all pass, including `test_old_accounts_are_asked_once` from Task 4. (`test_chat_dataset.py` builds tools with `{"profile": {}}`: `rules_of` gives neutral rules for it — fine.)

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/outfits.py backend/app/wardrobe.py backend/app/routers/insights.py backend/app/routers/tryon.py backend/app/routers/chat.py backend/app/agents/ backend/tests/test_gender_routes.py
git commit -m "Gender: outfit rules, look-alikes and chat tools follow the user's gender"
```

---

### Task 6: Gender on listings (shops + friperie sellers)

**Files:**
- Modify: `backend/app/listings.py` (`save_listing`, `listing_query`, `listing_out`, `ListingIndex.search`, new `backfill_gender`)
- Modify: `backend/app/main.py` (backfill at start-up)
- Modify: `backend/app/routers/listings.py` (GET /listings filter + `gender=all`, sell = seller's gender, gendered_user)
- Modify: `backend/app/routers/outfits.py` (`/similar` listings row)
- Modify: `backend/app/agents/shopping.py` (`search_listings`, `find_similar`)
- Test: `backend/tests/test_listings.py`

**Interfaces:**
- Consumes: `genders.normalise`, `genders.item_gender`, `genders.shown`, `genders.load_table`, `security.gendered_user`, `security.user_gender`
- Produces:
  - `listing_query(..., genders=None)`; `ListingIndex.search(db, vector, k=6, category=None, exclude_seller=None, genders=None)`
  - `backfill_gender(db) -> int` (listings updated)
  - `listing_out` includes `gender`
  - `GET /listings?gender=all`

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_listings.py`; reuse that file's existing helpers for inserting listings — if it inserts raw documents, follow the same pattern as below):

```python
def insert(db, **fields):
    """A minimal active shop listing."""
    doc = {"source_id": "shop", "external_id": fields.get("title", "x"), "status": "active",
           "in_stock": True, "category": "top", "sub_category": "t-shirt", "colour": "black",
           "created_at": datetime.now(timezone.utc), "vector": None, **fields}
    return db.listings.insert_one(doc).inserted_id


def test_listings_show_the_users_gender_plus_unisex(client):
    headers = sign_up(client, gender="men")
    db = client.app.state.db
    insert(db, title="m", gender="Men")
    insert(db, title="w", gender="women")
    insert(db, title="skirt", gender="", sub_category="skirt", category="bottom")
    insert(db, title="tee", gender="")
    from app.listings import backfill_gender
    assert backfill_gender(db) == 3            # "Men" normalised, two filled from the table
    titles = {x["title"] for x in client.get("/listings", headers=headers).json()["items"]}
    assert titles == {"m", "tee"}
    every = client.get("/listings?gender=all", headers=headers).json()["items"]
    assert {x["title"] for x in every} == {"m", "w", "skirt", "tee"}
    assert {x["gender"] for x in every} == {"men", "women", "unisex"}


def test_a_sellers_listing_takes_the_sellers_gender(client):
    headers = sign_up(client, gender="men")
    r = client.post("/listings/sell", files={"photo": photo(RED)},
                    data={"price_tnd": "20", "city": "Tunis", "contact": "x"}, headers=headers)
    assert r.status_code == 201
    assert client.app.state.db.listings.find_one({"source_id": "sellers"})["gender"] == "men"
```

(add `from datetime import datetime, timezone` and `photo`, `RED` imports from `tests.conftest` if the file doesn't have them yet.)

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_listings.py -q -k "gender"`
Expected: FAIL (`ImportError: cannot import name 'backfill_gender'`).

- [ ] **Step 3: `backend/app/listings.py`.** Import `genders` (after the existing `from . import ml` / src-path import used in this file; if the file has none, add `from . import ml  # noqa: F401` then `import genders`). In `save_listing`'s `doc`, replace `"gender": raw.gender,` with `"gender": genders.normalise(raw.gender),`, and where the analysed labels are written into the doc (the branch that sets `category` / `sub_category` from `labels`), fill the gender when the shop gave none:

```python
        if not doc["gender"]:     # the shop did not say: decided by the team's table
            doc["gender"] = genders.item_gender({"sub_category": doc.get("sub_category")
                                                 or labels.get("sub_category", "")})
```

`listing_query` gets `genders=None` (docstring: "genders: the item genders to show, None = all"):

```python
    if genders:
        query["gender"] = {"$in": sorted(genders)}
```

`listing_out` adds `"gender": doc.get("gender", ""),`. `ListingIndex.search` gets `genders=None`:

```python
            if genders and doc.get("gender") not in genders:
                continue
```

New function (below `mark_missing_gone`):

```python
def backfill_gender(db):
    """Give every listing men / women / unisex (older listings, or a shop's own spelling
    such as "Men"), so the app can filter with a plain $in. Safe to run at every start."""
    table, changed = genders.load_table(), 0
    for doc in db.listings.find({"gender": {"$nin": list(genders.VALUES)}},
                                {"gender": 1, "sub_category": 1}):
        value = genders.item_gender(doc, table)
        changed += db.listings.update_one({"_id": doc["_id"]}, {"$set": {"gender": value}}).modified_count
    return changed
```

In `backend/app/main.py`, inside `lifespan` after `app.state.listing_index = ListingIndex()`: `backfill_gender(app.state.db)` (import it from `.listings`).

- [ ] **Step 4: `backend/app/routers/listings.py`.** Import `gendered_user, user_gender` and `genders`. `list_listings`: `user=Depends(gendered_user)`, new param `gender: Literal["mine", "all"] = "mine"`, and

```python
    shown = None if gender == "all" else genders.shown(user_gender(user))
    query = listing_query(category, sub_category, colour, size, source, max_price, in_stock, genders=shown)
```

`sell`: `user=Depends(gendered_user)` and in the doc `"gender": user_gender(user),` (a seller lists for their own side; REVIEW note in LISTINGS.md). `listing_candidate` (POST `/listings/{id}/candidate`): `gendered_user`.

- [ ] **Step 5: `/similar` listings row and the chat tools.** `routers/outfits.py` `/similar`:

```python
    listings = request.app.state.listing_index.search(
        request.app.state.db, query, k=k + 1, category=doc["category"], genders=shown)
```

`agents/shopping.py`: at the top of `tools`, `shown = genders.shown(user_gender(user))`; `search_listings` → `listing_query(..., max_price=max_price or None, genders=shown)`; `find_similar` → `listing_index.search(db, query, k=k, category=doc["category"], genders=shown)` (and `search_shop(..., genders=shown)` from Task 5).

- [ ] **Step 6: Run all tests**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/listings.py backend/app/main.py backend/app/routers/listings.py backend/app/routers/outfits.py backend/app/agents/shopping.py backend/tests/test_listings.py
git commit -m "Gender: shop and friperie listings carry a gender and are filtered by it"
```

---

### Task 7: Chat dataset builder gives its users a gender

**Files:**
- Modify: `src/phase4/build_chat_dataset.py:431-438`
- Test: `backend/tests/test_chat_dataset.py`

**Interfaces:**
- Consumes: `genders.GENDERS`
- Produces: builder users have `profile["gender"]` in `GENDERS`

`Conversation.__init__` (`build_chat_dataset.py:428-438`) builds `self.user` and already knows `self.dress_wearer` (the random wardrobe has dresses). The gender must agree with it.

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_chat_dataset.py`; `random` and `B` are already imported there):

```python
def test_builder_user_gender_agrees_with_the_wardrobe():
    import genders
    rng = random.Random(0)
    assert {B.user_gender(rng, True) for _ in range(20)} == {"women"}
    assert {B.user_gender(rng, False) for _ in range(50)} == set(genders.GENDERS)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_chat_dataset.py -q -k gender`
Expected: FAIL (`AttributeError: module 'build_chat_dataset' has no attribute 'user_gender'`).

- [ ] **Step 3: Implement.** Add `import genders` with the other project imports, a module-level helper above `class Conversation`:

```python
def user_gender(rng, dress_wearer):
    """The random user's gender (the tools filter shops and look-alikes by it): a wardrobe
    with dresses is a woman's; otherwise either."""
    return "women" if dress_wearer else rng.choice(genders.GENDERS)
```

and at line 438:

```python
        self.user["profile"] = {"language": self.profile_language, "min_coverage": self.min_coverage,
                                "gender": user_gender(rng, self.dress_wearer)}

- [ ] **Step 4: Run the file's tests**

Run: `python -m pytest tests/test_chat_dataset.py -q` → Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/phase4/build_chat_dataset.py backend/tests/test_chat_dataset.py
git commit -m "Gender: chat dataset users have a gender (no rebuild needed now)"
```

---

### Task 8: Frontend — sign-up, profile, one-time question, pickers, Show all

**Files:**
- Modify: `frontend/src/api/types.ts` (`User`, `ListingFilters`, `Gender`)
- Modify: `frontend/src/api/client.ts` (`register`, `updateMe`, `similar`, `subCategoryGender`)
- Modify: `frontend/src/auth.tsx` (`register(..., gender)`, `updateProfile` patch type)
- Create: `frontend/src/ui/GenderChoice.tsx` (choice + one-question page + `useSubGender`)
- Modify: `frontend/src/pages/AuthPage.tsx`, `frontend/src/pages/ProfilePage.tsx`, `frontend/src/App.tsx` (`Gate`)
- Modify: `frontend/src/ui/Field.tsx` (sub_category options: mine first, "More…")
- Modify: `frontend/src/pages/ShopPage.tsx`, `frontend/src/pages/SimilarPage.tsx` (Show all)
- Modify: `frontend/src/i18n/strings.ts` (en / fr / ar)

**Interfaces:**
- Consumes: `/auth/register` `gender`, `/me` `gender` + `needs_gender`, `GET /vocab/sub-category-gender`, `/listings?gender=all`, `/similar?gender=all`
- Produces: `Gender = 'men' | 'women'`; `GenderChoice({ value, onChange })`; `GenderAsk()`; `useSubGender(): Record<string, 'men'|'women'|'unisex'> | null`; `ScopeLine({ all, onToggle })`

- [ ] **Step 1: Types and client.** `types.ts`:

```ts
export type Gender = 'men' | 'women'

export interface User {
  // ...existing fields
  gender: Gender | null
  needs_gender: boolean        // account from before the question: asked once
}

export interface ListingFilters {
  // ...existing fields
  gender?: 'all'               // unset = my gender + unisex
}
```

`client.ts`:

```ts
  register: (email: string, password: string, name: string, gender: Gender) =>
    request<{ token: string; user: User }>('/auth/register', json('POST', { email, password, name, gender })),
  updateMe: (patch: Partial<Pick<User, 'name' | 'min_coverage' | 'language' | 'gender'>>) =>
    request<User>('/me', json('PUT', patch)),
  similar: (ref: { itemId?: string; candidateId?: string }, k = 6, all = false) => {
    const q = new URLSearchParams({ k: String(k) })
    if (ref.itemId) q.set('item_id', ref.itemId)
    if (ref.candidateId) q.set('candidate_id', ref.candidateId)
    if (all) q.set('gender', 'all')
    return request<Similar>(`/similar?${q}`)
  },
  subCategoryGender: () => request<Record<string, 'men' | 'women' | 'unisex'>>('/vocab/sub-category-gender'),
```

(keep `updateMe`'s existing method/path if it differs; only the patch type changes. Add `Gender` to the type import.)

- [ ] **Step 2: Strings** — add to `en`, `fr`, `ar` in `i18n/strings.ts` (same keys in all three):

```ts
  // en
  gender: 'Gender',
  genderWomen: 'Female',
  genderMen: 'Male',
  genderHelp: 'Shops, look-alikes and the outfit rules follow this. Your own wardrobe is never filtered.',
  genderRequired: 'Choose female or male.',
  genderAskTitle: 'One question before you continue',
  moreTypes: 'More…',
  showingWomen: "Showing women's + unisex",
  showingMen: "Showing men's + unisex",
  showingAll: 'Showing everything',
  showAll: 'Show all',
  showMine: 'Only mine',
  // fr
  gender: 'Genre',
  genderWomen: 'Femme',
  genderMen: 'Homme',
  genderHelp: 'Les boutiques, les ressemblances et les règles des tenues en dépendent. Ta garde-robe n’est jamais filtrée.',
  genderRequired: 'Choisis femme ou homme.',
  genderAskTitle: 'Une question avant de continuer',
  moreTypes: 'Plus…',
  showingWomen: 'Femme + unisexe',
  showingMen: 'Homme + unisexe',
  showingAll: 'Tout est affiché',
  showAll: 'Tout afficher',
  showMine: 'Seulement les miens',
  // ar
  gender: 'الجنس',
  genderWomen: 'أنثى',
  genderMen: 'ذكر',
  genderHelp: 'المتاجر والقطع المشابهة وقواعد التنسيق تتبع هذا الاختيار. خزانتك لا تُصفّى أبدًا.',
  genderRequired: 'اختر أنثى أو ذكر.',
  genderAskTitle: 'سؤال واحد قبل المتابعة',
  moreTypes: 'المزيد…',
  showingWomen: 'المعروض: نسائي + للجنسين',
  showingMen: 'المعروض: رجالي + للجنسين',
  showingAll: 'كل شيء معروض',
  showAll: 'عرض الكل',
  showMine: 'الخاص بي فقط',
```

(Arabic here is the app's Modern Standard Arabic UI text, not Darija.)

- [ ] **Step 3: `frontend/src/ui/GenderChoice.tsx`:**

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Gender } from '../api/types'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { Wordmark } from '../shell'
import { Chip } from './controls'
import { ErrorNote } from './states'

/** Female / male, as two chips (sign-up, profile, the one-time question). */
export function GenderChoice({ value, onChange }: { value: Gender | null; onChange: (g: Gender) => void }) {
  const { t } = useI18n()
  return (
    <div role="radiogroup" aria-label={t('gender')} className="flex flex-wrap gap-2">
      <Chip selected={value === 'women'} onClick={() => onChange('women')}>{t('genderWomen')}</Chip>
      <Chip selected={value === 'men'} onClick={() => onChange('men')}>{t('genderMen')}</Chip>
    </div>
  )
}

/** Accounts created before the question: asked once, the app opens after the answer. */
export function GenderAsk() {
  const { t } = useI18n()
  const { updateProfile } = useAuth()
  const [error, setError] = useState<unknown>(null)
  const choose = async (gender: Gender) => {
    setError(null)
    try { await updateProfile({ gender }) } catch (e) { setError(e) }
  }
  return (
    <div className="mx-auto flex min-h-dvh max-w-[440px] flex-col justify-center gap-5 px-4">
      <Wordmark />
      <div className="ticket flex flex-col gap-3 px-5 py-5">
        <h1 className="text-[20px] font-semibold text-carbon">{t('genderAskTitle')}</h1>
        <p className="text-[14px] text-carbon-soft">{t('genderHelp')}</p>
        <GenderChoice value={null} onChange={(g) => void choose(g)} />
      </div>
      {error ? <ErrorNote error={error} /> : null}
    </div>
  )
}

let subGender: Promise<Record<string, 'men' | 'women' | 'unisex'>> | null = null

/** The team's table of men's / women's / unisex pieces (loaded once per session). */
// eslint-disable-next-line react-refresh/only-export-components
export function useSubGender() {
  const [table, setTable] = useState<Record<string, 'men' | 'women' | 'unisex'> | null>(null)
  useEffect(() => {
    subGender ??= api.subCategoryGender()
    subGender.then(setTable).catch(() => { subGender = null })
  }, [])
  return table
}

/** "Showing men's + unisex · Show all" above shop / look-alike results. */
export function ScopeLine({ all, onToggle }: { all: boolean; onToggle: () => void }) {
  const { t } = useI18n()
  const { user } = useAuth()
  const mine = user?.gender === 'men' ? t('showingMen') : t('showingWomen')
  return (
    <p className="flex flex-wrap items-center gap-2 text-[13px] text-carbon-soft">
      <span>{all ? t('showingAll') : mine}</span>
      <button type="button" onClick={onToggle} className="text-ink underline decoration-1 underline-offset-4 hover:decoration-2">
        {all ? t('showMine') : t('showAll')}
      </button>
    </p>
  )
}
```

- [ ] **Step 4: Auth context + sign-up + profile + gate.**
- `auth.tsx`: `register: (email, password, name, gender: Gender) => Promise<void>`; pass `gender` to `api.register`; `updateProfile` patch type adds `'gender'`.
- `AuthPage.tsx`: `const [gender, setGender] = useState<Gender | null>(null)`; in sign-up mode, under the name field:

```tsx
          {signup && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-medium text-carbon">{t('gender')}</span>
              <GenderChoice value={gender} onChange={setGender} />
              <p className="text-[12px] text-carbon-soft">{t('genderHelp')}</p>
            </div>
          )}
```

and in `submit`, before `setBusy(true)`: `if (signup && !gender) { setError(t('genderRequired')); return }`, then `await register(email, password, String(form.get('name')), gender!)`.
- `ProfilePage.tsx`: a new fieldset after the name form, same shape as the language one:

```tsx
        <fieldset className="ticket min-w-0 px-4 py-4">
          <legend className="sr-only">{t('gender')}</legend>
          <h2 className="text-[16px] font-semibold text-carbon">{t('gender')}</h2>
          <p className="mb-3 mt-1 max-w-[52ch] text-[14px] text-carbon-soft">{t('genderHelp')}</p>
          <GenderChoice value={user.gender} onChange={(g) => void save({ gender: g })} />
        </fieldset>
```

- `App.tsx` `Gate`: after `if (!user) return <Navigate ... />`, add `if (user.needs_gender) return <GenderAsk />`.

- [ ] **Step 5: Pickers** in `ui/Field.tsx`: import `useAuth` and `useSubGender`; inside `FieldRow` add `const { user } = useAuth()`, `const subGender = useSubGender()`, `const [more, setMore] = useState(false)`, and compute the options:

```tsx
  const all = options(field, item)
  // pieces of the user's gender (and unisex) first; the others stay one tap away
  const mineFirst = field === 'sub_category' && subGender && user?.gender
  const mine = mineFirst ? all.filter((v) => (subGender[v] ?? 'unisex') !== (user!.gender === 'men' ? 'women' : 'men')) : all
  const others = mineFirst ? all.filter((v) => !mine.includes(v)) : []
  const shownOptions = more ? [...mine, ...others] : [...mine, ...others.filter((v) => values.includes(v))]
```

render `shownOptions.map(...)` instead of `options(field, item).map(...)`, and after the chips:

```tsx
          {!more && others.some((v) => !values.includes(v)) && (
            <Chip selected={false} onClick={() => setMore(true)}>{t('moreTypes')}</Chip>
          )}
```

(The current value is always shown even when it is the other gender's piece.) Do the same in the Sell form only if it has its own sub_category picker — check `SellPage.tsx`; if it reuses `FieldRow`, nothing more to do.

- [ ] **Step 6: Show all.** `ShopPage.tsx`: below the filter rows,

```tsx
        <ScopeLine all={filters.gender === 'all'} onToggle={() => set({ gender: filters.gender === 'all' ? undefined : 'all' })} />
```

`SimilarPage.tsx`: `const [all, setAll] = useState(false)`, `useLoad(() => api.similar({ itemId, candidateId }, 6, all), [itemId, candidateId, all])`, and `<ScopeLine all={all} onToggle={() => setAll(!all)} />` at the top of the results (before the wardrobe section; the wardrobe list is unaffected by it).

- [ ] **Step 7: Build**

Run (from `frontend/`): `npm run build`
Expected: no TypeScript errors.

- [ ] **Step 8: Browser check** (restart the Vite dev server first: new .tsx file). Backend running from `backend/` with `uvicorn app.main:create_app --factory --port 8000`. Check with the preview tools:
1. `/signup`: submit without a gender → "Choose female or male."; with Male → lands on Today.
2. Profile shows Gender = Male; switch to Female → saved.
3. In MongoDB unset `profile.gender` for that user, reload → the one-question page; answer → app opens.
4. Wardrobe item → Type field: unisex / own-gender types first, "More…" reveals the rest.
5. Shop: "Showing men's + unisex · Show all" toggles results; Similar: same.
6. `ar` language: the new texts appear right-to-left without overflow at 375 px.
Take a screenshot of steps 1 and 5 for the PR.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "Gender: sign-up and profile choice, one-time question, gendered pickers, Show all"
```

---

### Task 9: Regression check + docs

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md`, `LISTINGS.md`, `docs/superpowers/specs/2026-10-10-gender-based-app-design.md` (status line)

- [ ] **Step 1: Compatibility numbers must not move.** Run (project root, > 10 min → separate process with a log, per CLAUDE.md):

```bash
python src/phase4/evaluate_compatibility.py > logs/evaluate_compatibility_gender.log 2>&1
```

Expected: `reports/phase4/compatibility_evaluation.md` shows PolyVore AUC 66.6% / FITB 42.6%, Fashionpedia 78.7% / 59.5% (`git diff reports/phase4/compatibility_evaluation.md` = only the date, if anything). If the numbers changed, stop: the neutral rules are not identical.

- [ ] **Step 2: Full backend suite**

Run (from `backend/`): `python -m pytest -q` → Expected: all pass.

- [ ] **Step 3: Docs.**
- `CLAUDE.md` unified schema table: add a row `| gender | men, women, unisex (users: men / women) |`. In Phase 4, add item 8 **Gender (done)**: required at sign-up (`/auth/register` `gender`, older accounts answer 409 `gender_required` until asked once), `src/phase4/genders.py` + `mappings/gender_sub_categories.csv` (REVIEW), optional `gender` column in the rule CSVs (gendered row overrides neutral; `compatibility.rules_for`), catalogue / H&M / listings / chat tools filtered to `{gender, unisex}` (`?gender=all` on `/listings` and `/similar`), the wardrobe never filtered, `backfill_gender` at start-up, `GET /vocab/sub-category-gender`, chat model unchanged.
- `AGENTS.md`: one line: the tools apply the user's gender (rules + `{gender, unisex}` filter) server-side; prompts unchanged.
- `LISTINGS.md`: `gender` field (shop label normalised, else the table; sellers = their own gender, REVIEW).
- Spec status line: "Status: implemented."

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md AGENTS.md LISTINGS.md docs/superpowers/specs/2026-10-10-gender-based-app-design.md reports/phase4/compatibility_evaluation.md
git commit -m "Gender: docs, and the compatibility evaluation re-run (numbers unchanged)"
```
