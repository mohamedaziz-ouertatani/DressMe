"""
Synthetic conversations to fine-tune the local chat model (LLM.md).

Each conversation is what the real /chat sends to one of the five agents
(backend/app/agents/: Stylist, Shopping advisor, Wardrobe analyst, Seller assistant,
Explainer): that agent's system prompt and tools (imported from the backend, so they
can never drift apart), a user question in English, French or Tunisian Arabic, the
tool calls the agent should make, the REAL tool answers, and a short final answer
that only talks about what the tools returned. A few rows teach the agent router
(app/agents/router.py): its prompt, one question, the agent's name.

How the tool answers are real: every conversation gets a random wardrobe (same
fields as the app's items, with FashionCLIP-like vectors, model guesses and their
alternatives), saved in a scratch MongoDB database (dressme_chat_build, dropped at
the end), next to a pool of shop and friperie listings. The backend's own tool
functions run on it unchanged, so scores, verdicts, prices and explanations all
come from src/phase4/compatibility.py, explain_outfit.py and app/resale.py with
the team's settings. Only the H&M catalogue and the weather are small fakes.

What the model learns from it:
  - which agent tool to call, with which arguments;
  - list_wardrobe FIRST whenever a tool needs item ids (never invent an id);
  - get_weather before "what do I wear today?";
  - never invent clothes (questions about items the user doesn't own);
  - answer in the user's language (also when they write in Arabizi), short;
  - no tool for greetings, thanks or off-topic questions; send a question meant
    for another agent to that agent in one sentence.

The sentences come from src/phase4/chat_phrases.py and chat_phrases_agents.py
(team-editable; the Darija of the second file is not reviewed yet). In the train
split the last phrasing of every list with 3+ phrasings is held out, so val / test
also measure questions the model has never seen.

Run from the project root (backend requirements + local MongoDB, no GPU, a few minutes):
    python src/phase4/build_chat_dataset.py
Output: data/processed/chat_sft/{train,val,test}.jsonl, one conversation per line:
    {"id", "scenario", "agent", "language" (of the last question), "answer_languages"
     (one per plain answer), "tools": [...], "messages": [...]}
plus dataset-metadata.json and a copy of src/phase4/finetune_chat.py, so the folder can be
uploaded as a PRIVATE Kaggle dataset and trained there (LLM.md).
"""

import argparse
import json
import random
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
import src_path  # noqa: F401,E402  (finds modules in src/common, src/phase3, src/phase4)

from bson import Binary, ObjectId                          # noqa: E402

import chat_phrases as P                                  # noqa: E402
import chat_phrases_agents as PA                          # noqa: E402
import genders                                            # noqa: E402
from genders import load_table as gender_table            # noqa: E402
from app.agents import AGENTS                              # noqa: E402
from app.agents.router import router_prompt                # noqa: E402
from app.chat_engine import tool_schema                    # noqa: E402
from app.listings import SELLERS, ListingIndex             # noqa: E402
from app.vocab import SUB_PARENT                           # noqa: E402
from app.weather import OpenMeteo                          # noqa: E402

OUT_DIR = ROOT / "data" / "processed" / "chat_sft"
BUILD_DB = "dressme_chat_build"     # scratch database, dropped after each split
SIZES = {"train": 4500, "val": 250, "test": 400}
SEEDS = {"train": 1, "val": 2, "test": 3}
KAGGLE_DATASET = "mohameddazizz/dressme-chat-sft"

# scenario -> (agent that answers it, weight). None: any agent.
SCENARIOS = {
    "list": ("stylist", 6), "suggest": ("stylist", 10), "today": ("stylist", 6),
    "weather": ("stylist", 2), "score": ("stylist", 8), "not_owned": ("stylist", 5),
    "follow_up": ("stylist", 3), "complete": ("stylist", 5),
    "buy": ("shopping", 7), "search": ("shopping", 10), "similar": ("shopping", 6),
    "not_owned_other": (None, 4),        # complete / look-alike / price of a piece they don't own
    "insights": ("analyst", 4), "stats": ("analyst", 3), "twins": ("analyst", 2),
    "what_sell": ("seller", 3), "price": ("seller", 3), "sell": ("seller", 3),
    "my_listings": ("seller", 2),
    "why_score": ("explainer", 4), "what_if": ("explainer", 3), "labels": ("explainer", 3),
    "why_verdict": ("explainer", 2), "how_scoring": ("explainer", 1),
    "why_similar": ("explainer", 4),
    "chit_chat": (None, 9), "handoff": (None, 5), "route": (None, 5),
}
SCENARIO_AGENTS = {"not_owned_other": ["stylist", "shopping", "seller"]}   # for the None rows above
LANGUAGE_WEIGHTS = {"fr": 45, "ar": 35, "en": 20}          # the app's profile language
OTHER_LANGUAGE = 0.12      # the user writes in another language than their profile
ARABIZI = 0.5              # Darija questions typed in Latin letters
EARLIER_EXCHANGE = 0.25    # a greeting exchange before the question
WEATHER_DOWN = 0.1         # get_weather answers an error
NO_ID_WITHOUT_LIST = {"score_outfit", "complete_outfit", "find_similar", "price_hint", "prepare_sell",
                      "explain_outfit", "what_if", "explain_labels", "explain_similarity"}
ID_ARGS = ("item_id", "other_id", "remove_id", "add_id")

CATEGORY_WEIGHTS = {"top": 4, "bottom": 3, "shoes": 2.2, "outerwear": 1.5, "dress": 1.2,
                    "bag": 1, "accessory": 1.2, "traditional": 0.2, "swimwear": 0.2}
# pieces mostly worn by people who wear dresses (keeps wardrobes believable)
DRESS_WEARER_ONLY = {"dress", "jumpsuit", "skirt", "heels", "clutch", "earrings", "flats",
                     "jewellery-set", "tunic", "cape", "kaftan", "hair-accessory", "brooch"}
COLOUR_WEIGHTS = {"black": 25, "white": 12, "navy": 8, "grey": 8, "blue": 10, "beige": 7,
                  "brown": 5, "cream": 3, "khaki": 3, "red": 4, "burgundy": 3, "pink": 3,
                  "green": 3, "olive": 2, "yellow": 2, "orange": 1, "teal": 1, "purple": 2,
                  "multicolour": 2}
METAL_FOR = {"accessory"}                 # gold / silver only for accessories
PATTERN_WEIGHTS = {"solid": 70, "striped": 8, "checked": 7, "floral": 7, "printed": 8}
UNSURE_COLOUR = 0.1        # colour left empty (model confidence below 0.7)
VECTOR_DIM, N_STYLES = 512, 4
LISTINGS = 300             # shop + friperie listings per split
HM_PRODUCTS = 200          # fake H&M catalogue per split
HM_WORDS = ["Slim", "Relaxed", "Oversized", "Regular", "Cropped", "Classic", "Fitted", "Wide"]


def weighted(rng, weights):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def object_id(rng):
    return ObjectId("%024x" % rng.getrandbits(96))


# ------------------------------------------------------------------ random wardrobes
class WardrobeMaker:
    def __init__(self, rng):
        self.rng = rng
        nprng = np.random.default_rng(rng.randrange(2**32))
        self.nprng = nprng
        self.common = self._unit(nprng.normal(size=VECTOR_DIM))
        self.styles = [self._unit(nprng.normal(size=VECTOR_DIM)) for _ in range(N_STYLES)]
        self.subs = {}
        for sub, cat in SUB_PARENT.items():
            self.subs.setdefault(cat, []).append(sub)

    @staticmethod
    def _unit(v):
        return v / np.linalg.norm(v)

    def vector(self, style, noise=0.55):
        """Same style ~0.7 similarity, different styles ~0.35, like FashionCLIP."""
        v = 0.6 * self.common + 0.6 * self.styles[style] \
            + self.nprng.normal(size=VECTOR_DIM) * noise / np.sqrt(VECTOR_DIM)
        return self._unit(v).astype(np.float16)

    def guess(self, value, others):
        """The classifier's stored guess for one field: value, confidence, top-3 alternatives."""
        rng = self.rng
        conf = round(rng.uniform(0.35, 0.99), 3)
        rest = rng.sample([o for o in others if o != value], 2)
        second = round(rng.uniform(0, 1 - conf) * 0.8, 3)
        third = round(rng.uniform(0, 1 - conf - second), 3)
        return {"value": value, "conf": conf,
                "alternatives": [{"value": value, "conf": conf}, {"value": rest[0], "conf": second},
                                 {"value": rest[1], "conf": third}]}

    def piece(self, dress_wearer, category=None):
        """category, sub_category, colour, pattern of a random piece."""
        rng = self.rng
        weights = dict(CATEGORY_WEIGHTS)
        if not dress_wearer:
            weights.pop("dress")
        category = category or weighted(rng, weights)
        subs = [s for s in self.subs[category] if dress_wearer or s not in DRESS_WEARER_ONLY]
        sub = rng.choice(subs or self.subs[category])
        colours = dict(COLOUR_WEIGHTS, **({"gold": 4, "silver": 4} if category in METAL_FOR else {}))
        colour = weighted(rng, colours)
        clothes = category in ("top", "bottom", "dress", "outerwear", "traditional", "swimwear")
        pattern = weighted(rng, PATTERN_WEIGHTS) if clothes else "solid"
        return category, sub, colour, pattern

    def item(self, user_id, dress_wearer, category=None, style=None):
        rng = self.rng
        category, sub, colour, pattern = self.piece(dress_wearer, category)
        predicted = {"category": self.guess(category, list(CATEGORY_WEIGHTS)),
                     "sub_category": self.guess(sub, list(SUB_PARENT)),
                     "pattern": self.guess(pattern, list(PATTERN_WEIGHTS)),
                     "colour": self.guess(colour, list(COLOUR_WEIGHTS))}
        if rng.random() < UNSURE_COLOUR:          # below 0.7: the app leaves the colour empty
            predicted["colour"]["conf"] = predicted["colour"]["alternatives"][0]["conf"] = \
                round(rng.uniform(0.35, 0.69), 3)
            colour = ""
        corrected = [f for f in ("colour", "pattern") if rng.random() < 0.08]
        return {"_id": object_id(rng), "user_id": user_id,
                "category": category, "sub_category": sub, "colour": colour, "pattern": pattern,
                "coverage": rng.choice([None, None, 2, 3, 4, 5]),
                "season": rng.sample(["summer", "winter", "mid-season"], rng.randint(1, 2))
                if rng.random() < 0.4 else [],
                "usage": rng.sample(["casual", "formal", "sport", "wedding", "eid", "work"],
                                    rng.randint(1, 3)) if rng.random() < 0.4 else [],
                "predicted": predicted, "corrected": corrected,
                "vector": Binary(self.vector(rng.randrange(N_STYLES) if style is None else style).tobytes()),
                "created_at": datetime.now(timezone.utc)}

    def wardrobe(self, user_id):
        rng = self.rng
        dress_wearer = rng.random() < 0.5
        size = rng.choice([0, 1, 2, 3] + list(range(4, 16)) * 3)
        docs = []
        # most people own at least a top, a bottom and shoes
        if size >= 3 and rng.random() < 0.85:
            for cat in ("top", "bottom", "shoes"):
                docs.append(self.item(user_id, dress_wearer, cat))
        while len(docs) < size:
            docs.append(self.item(user_id, dress_wearer))
        return docs, dress_wearer


# ------------------------------------------------------------------ the shared world
class FakeCatalog:
    """A small made-up H&M catalogue with the same answer as app.ml.Catalog.search_shop."""

    def __init__(self, maker, rng):
        self.maker = maker
        self.rows = []
        for k in range(HM_PRODUCTS):
            category, sub, colour, _ = maker.piece(rng.random() < 0.5)
            self.rows.append({"id": f"hm_{rng.randrange(10**8, 10**9)}",
                              "name": f"{rng.choice(HM_WORDS)} {P.SUB_WORDS[sub][0]}",
                              "shop": "H&M", "department": rng.choice(["Ladieswear", "Menswear", "Divided"]),
                              "category": category, "sub_category": sub, "colour": colour,
                              "vector": maker.vector(rng.randrange(N_STYLES)).astype(np.float32)})

    def mean_vector(self):
        """The "average picture" the concept probes are compared with (app.ml.Catalog)."""
        return self.maker.common.astype(np.float32)

    def search_shop(self, vector, k=6, category=None, genders=None):
        # department -> gender like H&M's own (src/phase3/map_hm.py); Divided = the team's table
        gender = lambda r: {"Ladieswear": "women", "Menswear": "men"}.get(
            r["department"]) or gender_table().get(r["sub_category"], "unisex")
        rows = [r for r in self.rows if (not category or r["category"] == category)
                and (genders is None or gender(r) in genders)]
        rows.sort(key=lambda r: -float(r["vector"] @ vector))
        return [{**{key: v for key, v in r.items() if key != "vector"},
                 "score": round(float(r["vector"] @ vector), 3)} for r in rows[:k]]


class FakeAnalyzer:
    """Only what the Explainer's explain_similarity reads: the team's concepts as vectors in the
    same made-up space as the pictures. Each concept leans to one style, so pieces of the same
    style share concepts, like FashionCLIP's text side would give."""

    def __init__(self, maker, rng):
        import explain_similarity
        self.concepts = {}
        for k, row in enumerate(explain_similarity.load_concepts()):
            v = 0.5 * maker.common + 0.8 * maker.styles[k % N_STYLES]                 + maker.nprng.normal(size=VECTOR_DIM) * 0.6 / np.sqrt(VECTOR_DIM)
            self.concepts[row["concept"]] = (v / np.linalg.norm(v)).astype(np.float32)

    def concept_vectors(self, gender=None):
        """Same vectors for every gender: a gendered wording keeps the concept's name."""
        return self.concepts


class FakeWeather(OpenMeteo):
    """The real weather code (simplify, season rules) on a random Open-Meteo answer."""

    def __init__(self, rng):
        super().__init__(settings=None)
        low = rng.randint(2, 26)
        high = low + rng.randint(4, 10)
        code = rng.choice([0, 1, 2, 3, 45, 61, 63, 95])
        rain = rng.choice([0, 5, 10, 20, 40, 60, 80])
        self.raw = {"current": {"temperature_2m": high - 2, "apparent_temperature": high - 1,
                                "weather_code": code},
                    "daily": {"temperature_2m_min": [low - 1], "temperature_2m_max": [high - 1],
                              "apparent_temperature_min": [low], "apparent_temperature_max": [high],
                              "precipitation_probability_max": [rain], "weather_code": [code]}}

    def fetch(self, lat, lon):
        return self.raw


def listing_title(sub, colour):
    fr, gender = P.SUB_WORDS[sub][1]
    masc, fem = P.COLOUR_WORDS[colour][1]
    return f"{fr} {fem if gender.startswith('f') else masc}"[:1].upper() + \
        f"{fr} {fem if gender.startswith('f') else masc}"[1:]


def make_listings(db, maker, rng, n=LISTINGS):
    """Active, in-stock listings: Tunisian shops (some from an old snapshot) and friperie sellers."""
    docs = []
    for _ in range(n):
        category, sub, colour, pattern = maker.piece(rng.random() < 0.5)
        friperie = rng.random() < 0.45
        doc = {"_id": object_id(rng), "category": category, "sub_category": sub, "colour": colour,
               "pattern": pattern, "title": listing_title(sub, colour), "status": "active", "in_stock": True,
               "vector": Binary(maker.vector(rng.randrange(N_STYLES)).tobytes()),
               "created_at": datetime.now(timezone.utc) - timedelta(minutes=rng.randrange(10000))}
        if friperie:
            doc.update(source_id=SELLERS, seller_id=object_id(rng), city=rng.choice(PA.CITIES),
                       price_tnd=float(rng.randrange(5, 60)))
        else:
            doc.update(source_id=rng.choice(PA.SHOP_SOURCES), brand=rng.choice(["Exist", "Hamadi Abid"]),
                       price_tnd=float(rng.randrange(30, 200)), snapshot=rng.random() < 0.15)
        docs.append(doc)
    db.listings.insert_many(docs)
    return docs


class World:
    """One split's scratch database + the app state the tools read."""

    def __init__(self, db, rng):
        self.db, self.rng = db, rng
        self.maker = WardrobeMaker(rng)
        for name in ("items", "candidates", "listings", "outfit_feedback", "listing_runs"):
            db[name].drop()
        self.listings = make_listings(db, self.maker, rng)
        self.state = SimpleNamespace(
            db=db, catalog=FakeCatalog(self.maker, rng), listing_index=ListingIndex(), weather=None,
            analyzer=FakeAnalyzer(self.maker, rng),
            settings=SimpleNamespace(weather_lat=36.8, weather_lon=10.2, weather_place="Tunis"))

    def request(self):
        """A fresh weather per conversation (the real engine caches 30 min per place)."""
        self.state.weather = FakeWeather(self.rng)
        return SimpleNamespace(app=SimpleNamespace(state=self.state))


# ------------------------------------------------------------------ words
def fr_possessive(word, gender, person):
    """mon / ma / mes (or ton / ta / tes); "ma écharpe" -> "mon écharpe"."""
    first = {"my": ("mon", "ma", "mes"), "your": ("ton", "ta", "tes"),
             "this": ("ce", "cette", "ces")}[person]
    if gender.endswith("p"):
        return first[2]
    if word[0] in "aeéèêiouhy":
        return "cet" if person == "this" else first[0]
    return first[1] if gender == "f" else first[0]


def item_text(item, lang, form="bare"):
    """form: bare ("black jeans"), my / your ("your black jeans"), this ("this black jacket")."""
    en, (fr, fr_gender), (ar, ar_gender) = P.SUB_WORDS[item["sub_category"]]
    colour = item.get("colour") or ""
    if lang == "en":
        text = f"{P.COLOUR_WORDS[colour][0]} {en}" if colour else en
        return text if form == "bare" else f"{form} {text}"
    if lang == "fr":
        text = fr
        if colour:
            masc, fem = P.COLOUR_WORDS[colour][1]
            adj = fem if fr_gender.startswith("f") else masc
            if fr_gender.endswith("p") and adj not in P.FR_INVARIABLE and not adj.endswith("s"):
                adj += "s"
            text = f"{fr} {adj}"
        return text if form == "bare" else f"{fr_possessive(fr, fr_gender, form)} {text}"
    # Darija: "دجين كحل"; definite "الدجين الكحل" / "هالدجين الكحل" for one-word nouns
    adj = P.COLOUR_WORDS[colour][2][1 if ar_gender == "f" else 0] if colour else ""
    if form == "bare" or " " in ar:
        return f"{ar} {adj}".strip()
    article = "هال" if form == "this" else "ال"
    return f"{article}{ar} {'ال' + adj if adj else ''}".strip()


def indefinite(item, lang):
    """"a black skirt" / "une jupe noire" / "جيبة كحلة"."""
    text = item_text(item, lang)
    en, (fr, fr_gender), _ = P.SUB_WORDS[item["sub_category"]]
    if lang == "en":
        plural = en.endswith("s") and not en.endswith("ss")
        return f"{'any' if plural else 'an' if text[0] in 'aeiou' else 'a'} {text}"
    if lang == "fr":
        return f"{'des' if fr_gender.endswith('p') else 'une' if fr_gender == 'f' else 'un'} {text}"
    return text


def join(parts, lang):
    parts = list(parts)
    if len(parts) <= 1:
        return "".join(parts)
    if lang == "ar":
        return "، ".join(parts[:-1]) + " و" + parts[-1]
    return ", ".join(parts[:-1]) + (" and " if lang == "en" else " et ") + parts[-1]


def reason_word(token, lang):
    if token in P.COLOUR_WORDS:
        return P.COLOUR_WORDS[token][1 if lang == "fr" else 2][0]
    if token in P.SUB_WORDS:
        return P.SUB_WORDS[token][1 if lang == "fr" else 2][0]
    return P.REASON_WORDS[lang].get(token, token)


def reason_text(reason, lang, table=P.REASONS):
    """A reason of src/phase4/compatibility.py (or a fact of the Explainer, table=PA.FACTS),
    written in English, in the answer's language."""
    if lang == "en":
        return reason
    for pattern, fr, ar in table:
        m = re.fullmatch(pattern, reason)
        if m:
            groups = [", ".join(reason_word(t, lang) for t in g.split(", ")) for g in m.groups()]
            return (fr if lang == "fr" else ar).format(*groups)
    return reason


def capital(text):
    return text[:1].upper() + text[1:]


def value_word(field, value, lang):
    """A label value (category, type, pattern, colour) in the answer's language."""
    if lang == "en" or not value:
        return value.replace("-", " ")
    if field == "colour":
        return P.COLOUR_WORDS[value][1 if lang == "fr" else 2][0]
    if field == "sub_category":
        return P.SUB_WORDS[value][1 if lang == "fr" else 2][0]
    return P.REASON_WORDS[lang].get(value, value)


# ------------------------------------------------------------------ conversations
def scenario(fn):
    """Records which scenario really ran (one may fall back to another)."""
    def run(self):
        self.kind = fn.__name__.removeprefix("scenario_")
        return fn(self)
    return run


def user_gender(rng, dress_wearer):
    """The random user's gender (the tools filter shops and look-alikes by it): a wardrobe
    with dresses is a woman's; otherwise either."""
    return "women" if dress_wearer else rng.choice(genders.GENDERS)


class Conversation:
    """One synthetic chat with one agent: picks the words, runs the real tools, writes messages."""

    def __init__(self, rng, world, split, agent="stylist"):
        self.rng, self.world, self.split = rng, world, split
        self.maker = world.maker
        self.user = {"_id": object_id(rng), "profile": {}}
        self.docs, self.dress_wearer = self.maker.wardrobe(self.user["_id"])
        if self.docs:
            world.db.items.insert_many(self.docs)
        self.request = world.request()
        self.profile_language = weighted(rng, LANGUAGE_WEIGHTS)
        self.min_coverage = rng.choice([None, None, None, 3, 4, 5])
        self.user["profile"] = {"language": self.profile_language, "min_coverage": self.min_coverage,
                                "gender": user_gender(rng, self.dress_wearer)}
        self.use_agent(agent)
        self.messages = []
        self.answer_languages = []                     # language of each plain answer, in order
        self.new_turn()

    def use_agent(self, name):
        self.agent = name
        self.tools = AGENTS[name].tools(self.request, self.user)

    def new_turn(self):
        """Language of the next question: usually the profile's, sometimes another."""
        lang = self.profile_language
        if self.rng.random() < OTHER_LANGUAGE:
            lang = self.rng.choice([x for x in LANGUAGE_WEIGHTS if x != lang])
        self.lang = lang                               # language of the answer
        self.ask_lang = "arabizi" if lang == "ar" and self.rng.random() < ARABIZI else lang

    def no_arabizi(self):
        """Questions that name an item: Arabizi has no item names, ask in Arabic script."""
        if self.ask_lang == "arabizi":
            self.ask_lang = "ar"

    def pick(self, options):
        """A random phrasing; the train split never sees the last of 3+ phrasings."""
        if isinstance(options, str):
            return options
        if self.split == "train" and len(options) >= 3:
            options = options[:-1]
        return self.rng.choice(options)

    def ask(self, table, **slots):
        options = table.get(self.ask_lang) or table[self.lang]
        text = self.pick(options).format(**slots)
        self.messages.append({"role": "user", "content": capital(text)})

    def say(self, text):
        text = re.sub(r"\s+", " ", text).strip()
        self.messages.append({"role": "assistant", "content": capital(text)})
        self.answer_languages.append(self.lang)

    def call(self, name, **args):
        """The assistant calls a tool; the real backend function answers."""
        if name in NO_ID_WITHOUT_LIST and not any(
                c["function"]["name"] == "list_wardrobe" for m in self.messages for c in m.get("tool_calls", [])):
            if args.get("item_ids") or any(args.get(k) not in (None, "", "last_scan") for k in ID_ARGS):
                raise AssertionError(f"{name} with ids before list_wardrobe")
        result = self.tools[name](**args)
        self.messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": name, "arguments": args}}]})
        self.messages.append({"role": "tool", "name": name,
                              "content": json.dumps(result, ensure_ascii=False, default=str)})
        return result

    def system(self):
        return AGENTS[self.agent].prompt(self.user)

    def schemas(self):
        return [tool_schema(f) for f in self.tools.values()]

    # -------------------------------------------------------------- words for answers
    def your(self, item):
        return item_text(item, self.lang, "your" if self.lang != "ar" else "bare")

    def items_text(self, items, form="your"):
        lang = self.lang
        return join([item_text(i, lang, form if lang != "ar" else "bare") for i in items], lang)

    def reasons_text(self, reasons, limit=2, table=P.REASONS):
        return join([reason_text(r, self.lang, table) for r in reasons[:limit]], self.lang)

    def name_for_question(self, item):
        if self.ask_lang == "ar" or self.ask_lang == "arabizi":
            return item_text(item, "ar", "the")
        return item_text(item, self.ask_lang, "my")

    def unique_items(self, categories=None):
        """Items a user can name without ambiguity (one per sub_category + colour)."""
        count = Counter((d["sub_category"], d["colour"]) for d in self.docs)
        return [d for d in self.docs if count[(d["sub_category"], d["colour"])] == 1
                and (categories is None or d["category"] in categories)]

    def listing_text(self, row):
        where = (PA.SAY_FRIPERIE_IN[self.lang].format(city=row["city"]) if row.get("city")
                 else row.get("brand") or row["source_id"])
        return PA.SAY_LISTING[self.lang].format(title=row["title"], price=f"{row['price_tnd']:g}", where=where)

    def add_scan(self, twin_of=None):
        """The user's last scanned photo (a candidate), sometimes a near twin of an owned piece."""
        if twin_of is not None:
            cand = dict(self.maker.item(self.user["_id"], self.dress_wearer, twin_of["category"]),
                        sub_category=twin_of["sub_category"], colour=twin_of["colour"])
            v = np.frombuffer(twin_of["vector"], np.float16).astype(np.float32)
            v = v + self.maker.nprng.normal(size=VECTOR_DIM) * 0.15 / np.sqrt(VECTOR_DIM)
            cand["vector"] = Binary((v / np.linalg.norm(v)).astype(np.float16).tobytes())
        else:
            cand = self.maker.item(self.user["_id"], self.dress_wearer)
        cand["created_at"] = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.world.db.candidates.insert_one(cand)
        return cand

    # -------------------------------------------------------------- Stylist
    def outfit_sentences(self, outfits, first_table, **slots):
        lang, out = self.lang, []
        for k, o in enumerate(outfits):
            table = first_table if k == 0 else P.SAY_ANOTHER
            out.append(self.pick(table[lang]).format(items=self.items_text(o["items"]),
                                                     score=round(o["score"]), **slots))
            if k == 0 and o["reasons"]:
                out.append(P.SAY_NOTE[lang].format(reasons=self.reasons_text(o["reasons"])))
            elif k == 0 and (o["parts"].get("colour") or 0) >= 0.8 and self.rng.random() < 0.5:
                out.append(P.SAY_GOOD_COLOURS[lang])
        return out

    def explain_empty(self, occasion_text=""):
        has_core = any(d["category"] in ("dress", "traditional") for d in self.docs) or (
            any(d["category"] == "top" for d in self.docs)
            and any(d["category"] == "bottom" for d in self.docs))
        why = P.WHY_FILTERED if has_core else P.WHY_NO_CORE
        return P.SAY_SUGGEST_EMPTY[self.lang].format(occasion=occasion_text, why=why[self.lang])

    @scenario
    def scenario_list(self):
        present = sorted({d["category"] for d in self.docs} & set(P.CATEGORY_ASK))
        if self.rng.random() < 0.6:
            self.ask(P.ASK_LIST)
            items = self.call("list_wardrobe")
            if not items:
                return self.say(P.SAY_LIST_EMPTY[self.lang])
            groups = []
            for cat in P.CATEGORY_WORDS:
                inside = [i for i in items if i["category"] == cat]
                if inside:
                    groups.append(f"{P.CATEGORY_WORDS[cat][self.lang]}: "
                                  f"{join([item_text(i, self.lang) for i in inside], self.lang)}")
            return self.say(self.pick(P.SAY_LIST[self.lang]).format(n=len(items), groups="; ".join(groups)))
        # one category (usually one they have, sometimes one they don't)
        cat = self.rng.choice(present) if present and self.rng.random() < 0.8 \
            else self.rng.choice(list(P.CATEGORY_ASK))
        self.ask(P.ASK_LIST_CATEGORY, cat=P.CATEGORY_ASK[cat].get(self.ask_lang, P.CATEGORY_ASK[cat][self.lang]))
        items = self.call("list_wardrobe", category=cat)
        words = P.CATEGORY_WORDS[cat][self.lang]
        if not items:
            return self.say(P.SAY_LIST_CATEGORY_EMPTY[self.lang].format(cat=words))
        self.say(self.pick(P.SAY_LIST_CATEGORY[self.lang]).format(
            cat=words, n=len(items), items=join([item_text(i, self.lang) for i in items], self.lang)))

    @scenario
    def scenario_suggest(self):
        kind = self.rng.choice(["plain", "plain", "occasion", "season", "n"])
        args, first, slots, occasion_text = {}, P.SAY_SUGGEST, {}, ""
        if kind == "occasion":
            occasion = self.rng.choice(list(P.OCCASION_ASK))
            words = P.OCCASION_ASK[occasion]
            self.ask(P.ASK_SUGGEST_OCCASION, occasion=words.get(self.ask_lang, words[self.lang]))
            args = {"occasion": occasion}
            first, slots, occasion_text = P.SAY_SUGGEST_OCCASION, {"Occasion": capital(words[self.lang])}, words[self.lang]
        elif kind == "season":
            season = self.rng.choice(list(P.SEASON_ASK))
            words = P.SEASON_ASK[season]
            self.ask(P.ASK_SUGGEST_SEASON, season=words.get(self.ask_lang, words[self.lang]))
            args = {"season": season}
        elif kind == "n":
            n = self.rng.choice([2, 3, 4, 5])
            self.ask(P.ASK_SUGGEST_N, n=n)
            args = {"n": n}
        else:
            self.ask(P.ASK_SUGGEST)
        outfits = self.call("suggest_outfits", **args)
        if not outfits:
            return self.say(self.explain_empty(occasion_text))
        text = self.outfit_sentences(outfits[:args.get("n", 1)], first, **slots)
        text.append(self.pick(P.SAY_ASK_MORE[self.lang]))
        self.say(" ".join(text))

    def weather_line(self, w):
        lang = self.lang
        place = "تونس" if lang == "ar" else w["place"]
        line = PA.SAY_WEATHER[lang].format(place=place, condition=PA.CONDITION_WORDS[w["condition"]][lang],
                                           low=w["min"], high=w["max"])
        return line + " " + (PA.SAY_RAIN if w["rain_likely"] else PA.SAY_NO_RAIN)[lang]

    @scenario
    def scenario_today(self):
        """'What do I wear today?': the weather first, then an outfit for its season."""
        if self.rng.random() < WEATHER_DOWN:
            self.request.app.state.weather = None          # WEATHER_ENGINE=off / Open-Meteo down
        self.ask(PA.ASK_TODAY)
        w = self.call("get_weather")
        args = {} if "error" in w else {"season": w["season"]}
        outfits = self.call("suggest_outfits", **args)
        text = [PA.SAY_WEATHER_DOWN[self.lang] if "error" in w else self.weather_line(w)]
        if not outfits:
            text.append(self.explain_empty())
        else:
            text += self.outfit_sentences(outfits[:1], P.SAY_SUGGEST)
        self.say(" ".join(text))

    @scenario
    def scenario_weather(self):
        self.ask(PA.ASK_WEATHER)
        w = self.call("get_weather")
        if "error" in w:
            return self.say(PA.SAY_WEATHER_DOWN[self.lang].split(",")[0] + ".")
        self.say(self.weather_line(w))

    @scenario
    def scenario_score(self):
        items = self.unique_items()
        by_cat = {}
        for d in items:
            by_cat.setdefault(d["category"], []).append(d)
        options = []
        if by_cat.get("top") and by_cat.get("bottom"):
            options.append([self.rng.choice(by_cat["top"]), self.rng.choice(by_cat["bottom"])])
        if by_cat.get("dress") and by_cat.get("shoes"):
            options.append([self.rng.choice(by_cat["dress"]), self.rng.choice(by_cat["shoes"])])
        if by_cat.get("bottom") and by_cat.get("shoes"):
            options.append([self.rng.choice(by_cat["bottom"]), self.rng.choice(by_cat["shoes"])])
        if len(by_cat.get("top", [])) >= 2 and self.rng.random() < 0.3:      # two tops: a clash
            options = [self.rng.sample(by_cat["top"], 2)]
        if not options:
            return self.scenario_suggest()
        pair = self.rng.choice(options)
        self.no_arabizi()
        self.ask(P.ASK_SCORE, a=self.name_for_question(pair[0]), b=self.name_for_question(pair[1]))
        self.call("list_wardrobe")
        result = self.call("score_outfit", item_ids=[str(d["_id"]) for d in pair])
        lang = self.lang
        if "error" in result:
            clash = re.sub(r"^.*together: ", "", result["error"]).split("; ")
            return self.say(P.SAY_CLASH[lang].format(items=self.items_text(pair), reasons=self.reasons_text(clash)))
        score = round(result["score"])
        judgement = P.JUDGE_GOOD if score >= 75 else P.JUDGE_OK if score >= 60 else P.JUDGE_BAD
        text = [self.pick(P.SAY_SCORE[lang]).format(items=self.items_text(pair), score=score,
                                                   judgement=judgement[lang])]
        others = [r for r in result["reasons"] if r != "no shoes"]
        if others:
            text.append(P.SAY_NOTE[lang].format(reasons=self.reasons_text(others)))
        if "no shoes" in result["reasons"]:
            text.append(P.SAY_ADD_SHOES[lang])
        self.say(" ".join(text))

    def made_up_piece(self, cat):
        """A piece of this category the user does NOT own (None if none can be made)."""
        owned = {(d["sub_category"], d["colour"]) for d in self.docs}
        for _ in range(50):
            fake = self.maker.item(self.user["_id"], self.dress_wearer, cat)
            if fake["colour"] and (fake["sub_category"], fake["colour"]) not in owned:
                return fake
        return None

    def say_not_owned(self, items, fake):
        """'I can't find X. Your <category>: ...' after list_wardrobe."""
        lang, cat = self.lang, fake["category"]
        same = [i for i in items if i["category"] == cat]
        words = P.CATEGORY_WORDS[cat][lang]
        alternatives = (P.SAY_ALTERNATIVES[lang].format(cat=words, items=join(
            [item_text(i, lang) for i in same], lang)) if same
            else P.SAY_NO_ALTERNATIVE[lang].format(cat=words))
        self.say(P.SAY_NOT_OWNED[lang].format(missing=indefinite(fake, lang), alternatives=alternatives))

    @scenario
    def scenario_not_owned(self):
        """The user names a piece they don't have: never pretend it exists."""
        cat = self.rng.choice(["top", "bottom", "shoes", "outerwear"])
        fake = self.made_up_piece(cat)
        if fake is None:
            return self.scenario_list()
        real = self.unique_items()
        other = self.rng.choice(real) if real else None
        if other is None or other["category"] == cat:
            return self.scenario_list()
        self.no_arabizi()
        pair = [fake, other] if self.rng.random() < 0.5 else [other, fake]
        self.ask(P.ASK_SCORE, a=self.name_for_question(pair[0]), b=self.name_for_question(pair[1]))
        self.say_not_owned(self.call("list_wardrobe"), fake)

    # the question each agent gets about a piece the user does not own
    NOT_OWNED_ASK = {"stylist": PA.ASK_COMPLETE, "shopping": PA.ASK_SIMILAR, "seller": PA.ASK_PRICE}

    @scenario
    def scenario_not_owned_other(self):
        """'What goes with / something like / how much for my X?' when there is no X: list the
        wardrobe, then say so (v2 sent another piece's id instead)."""
        fake = self.made_up_piece(self.rng.choice(["top", "bottom", "shoes", "outerwear"]))
        if fake is None:
            return self.scenario_chit_chat()
        self.no_arabizi()
        self.ask(self.NOT_OWNED_ASK[self.agent], a=self.name_for_question(fake))
        self.say_not_owned(self.call("list_wardrobe"), fake)

    @scenario
    def scenario_follow_up(self):
        """'Another one?' after a suggestion. (The app keeps only the text of earlier
        turns, but every assistant turn here is learned, so the first one keeps its
        tool call: an answer without it would teach the model to invent outfits.)"""
        if len(self.tools["suggest_outfits"]()) < 1:
            return self.scenario_suggest()
        self.ask(P.ASK_SUGGEST)
        outfits = self.call("suggest_outfits")
        self.say(" ".join(self.outfit_sentences(outfits[:1], P.SAY_SUGGEST)))
        self.new_turn()
        self.ask(P.ASK_MORE)
        more = self.call("suggest_outfits", n=3)            # the best one again + 2 new ones
        rest = more[1:3]
        if not rest:
            return self.say(P.SAY_NO_MORE[self.lang])
        self.say(" ".join(self.outfit_sentences(rest, P.SAY_ANOTHER)))

    @scenario
    def scenario_complete(self):
        """'What goes with my black jeans?': list_wardrobe for the id, then complete_outfit."""
        mains = self.unique_items({"top", "bottom", "dress", "outerwear"})
        if not mains:
            return self.scenario_suggest()
        piece = self.rng.choice(mains)
        self.no_arabizi()
        self.ask(PA.ASK_COMPLETE, a=self.name_for_question(piece))
        self.call("list_wardrobe")
        ranked = self.call("complete_outfit", item_ids=[str(piece["_id"])])["completions"]
        lang, a = self.lang, self.your(piece)
        if not ranked:
            return self.say(PA.SAY_COMPLETE_NONE[lang].format(a=a))
        first = ranked[0]
        text = [self.pick(PA.SAY_COMPLETE[lang]).format(a=a, added=self.your(first["added"]),
                                                        score=round(first["score"]))]
        others = [f"{self.your(r['added'])} ({round(r['score'])}/100)" for r in ranked[1:3]]
        if others:
            text.append(PA.SAY_COMPLETE_OTHER[lang].format(others=join(others, lang)))
        self.say(" ".join(text))

    # -------------------------------------------------------------- Shopping advisor
    @scenario
    def scenario_buy(self):
        if self.rng.random() < 0.85:
            twin = self.rng.choice(self.docs) if self.docs and self.rng.random() < 0.15 else None
            cand = self.add_scan(twin)
        self.ask(P.ASK_BUY)
        advice = self.call("buy_advice_last_scan")
        lang = self.lang
        if "error" in advice:
            return self.say(P.SAY_BUY_NO_SCAN[lang])
        verdict = advice["verdict"]
        example = ""
        if advice["best"]:
            others = [i for i in advice["best"][0]["items"] if i["id"] != str(cand["_id"])]
            example = self.items_text(others) if others else ""
        if verdict != "skip" and not example:
            verdict = "skip"
        text = [P.SAY_BUY[verdict][lang].format(item=item_text(cand, lang, "this"),
                                                 n=advice["good_outfits"], example=example)]
        if advice["reasons"]:
            text.append(P.SAY_NOTE[lang].format(reasons=self.reasons_text(advice["reasons"])))
        self.say(" ".join(text))

    @scenario
    def scenario_search(self):
        """'I'm looking for black jeans (under 50 TND)': search_listings with the app's values."""
        if self.rng.random() < 0.5:                      # something in stock
            row = self.rng.choice(self.world.listings)
            want = {"category": row["category"], "sub_category": row["sub_category"], "colour": row["colour"]}
        else:   # any type and colour of the app's vocabulary, evenly: v2 used words that are not
            sub = self.rng.choice(sorted(SUB_PARENT))    # app values (slacks, violet, earring)
            colours = [c for c in COLOUR_WEIGHTS if c != "multicolour"] + (
                ["gold", "silver"] if SUB_PARENT[sub] in METAL_FOR else [])
            want = {"category": SUB_PARENT[sub], "sub_category": sub, "colour": self.rng.choice(colours)}
        self.no_arabizi()
        piece = indefinite(want, self.ask_lang)
        args = {"sub_category": want["sub_category"], "colour": want["colour"]}
        if self.rng.random() < 0.4:
            price = self.rng.choice([20, 30, 50, 80, 100, 150])
            self.ask(PA.ASK_SEARCH_PRICE, piece=piece, price=price)
            args["max_price"] = price
        else:
            self.ask(PA.ASK_SEARCH, piece=piece)
        found = self.call("search_listings", **args)["listings"]
        lang = self.lang
        if not found:
            return self.say(PA.SAY_SEARCH_NONE[lang])
        text = [PA.SAY_SEARCH[lang].format(list=join([self.listing_text(r) for r in found[:3]], lang))]
        if any(r.get("snapshot") for r in found[:3]):
            text.append(PA.SAY_SNAPSHOT[lang])
        self.say(" ".join(text))

    @scenario
    def scenario_similar(self):
        """Look-alikes of one of their pieces (list_wardrobe first) or of the last scan."""
        pieces = self.unique_items({"top", "bottom", "dress", "outerwear", "shoes", "bag"})
        lang = self.lang
        if pieces and self.rng.random() < 0.7:
            piece = self.rng.choice(pieces)
            self.no_arabizi()
            self.ask(PA.ASK_SIMILAR, a=self.name_for_question(piece))
            self.call("list_wardrobe")
            found = self.call("find_similar", item_id=str(piece["_id"]))
        else:
            if self.rng.random() < 0.85:
                self.add_scan()
            self.ask(PA.ASK_SIMILAR_SCAN)
            found = self.call("find_similar")
            if "error" in found:
                return self.say(PA.SAY_NO_SCAN_SIMILAR[lang])
        if not found["shop"] and not found["listings"]:
            return self.say(PA.SAY_SIMILAR_NONE[lang])
        text = []
        if found["listings"]:
            text.append(PA.SAY_SIMILAR_LISTINGS[lang].format(
                listings=join([self.listing_text(r) for r in found["listings"][:2]], lang)))
        if found["shop"]:
            text.append(PA.SAY_SIMILAR[lang].format(shop=join([s["name"] for s in found["shop"][:3]], lang)))
        self.say(" ".join(text))

    # -------------------------------------------------------------- Wardrobe analyst
    @scenario
    def scenario_insights(self):
        self.ask(PA.ASK_INSIGHTS)
        facts = self.call("wardrobe_insights")
        lang = self.lang
        if not self.docs:
            return self.say(P.SAY_LIST_EMPTY[lang])
        text = [PA.SAY_INSIGHTS_OUTFITS[lang].format(good=facts["good_outfits"])]
        if facts["versatile"]:
            text.append(PA.SAY_VERSATILE[lang].format(items=self.items_text(facts["versatile"][:2])))
        if facts["unmatched"]:
            text.append(PA.SAY_UNMATCHED[lang].format(items=self.items_text(facts["unmatched"][:2])))
        missing = [PA.MISSING_WORDS[m][lang] for m in facts["missing"]]
        text.append(PA.SAY_MISSING[lang].format(missing=join(missing, lang)) if missing
                    else PA.SAY_NOTHING_MISSING[lang])
        self.say(" ".join(text))

    @scenario
    def scenario_stats(self):
        self.ask(PA.ASK_STATS)
        stats = self.call("wardrobe_stats")
        lang = self.lang
        if not stats["total"]:
            return self.say(P.SAY_LIST_EMPTY[lang])
        categories = ", ".join(f"{P.CATEGORY_WORDS[c['category']][lang]} {c['count']}" for c in stats["categories"])
        colours = join([value_word("colour", c["colour"], lang) for c in stats["colours"][:3]], lang)
        text = [PA.SAY_STATS[lang].format(total=stats["total"], categories=categories, colours=colours or "-")]
        neutral = sum(c["count"] for c in stats["colours"] if c["neutral"])
        if neutral:
            text.append(PA.SAY_NEUTRAL[lang].format(n=neutral))
        if stats["to_confirm"]["colour"]:
            text.append(PA.SAY_TO_CONFIRM[lang].format(n=stats["to_confirm"]["colour"]))
        self.say(" ".join(text))

    @scenario
    def scenario_twins(self):
        if self.docs and self.rng.random() < 0.5:          # make a real near twin
            twin = self.rng.choice(self.docs)
            copy = dict(self.maker.item(self.user["_id"], self.dress_wearer, twin["category"]),
                        sub_category=twin["sub_category"], colour=twin["colour"], vector=twin["vector"])
            self.world.db.items.insert_one(copy)
            self.docs.append(copy)
        self.ask(PA.ASK_TWINS)
        twins = self.call("find_near_twins")["twins"]
        lang = self.lang
        if not twins:
            return self.say(PA.SAY_NO_TWINS[lang])
        pairs = [self.items_text(t["items"]) for t in twins[:2]]
        self.say(PA.SAY_TWINS[lang].format(pairs="; ".join(pairs)))

    # -------------------------------------------------------------- Seller assistant
    @scenario
    def scenario_what_sell(self):
        self.ask(PA.ASK_WHAT_SELL)
        found = self.call("pieces_to_sell")
        lang = self.lang
        if not self.docs:
            return self.say(P.SAY_LIST_EMPTY[lang])
        text = []
        if found["unmatched"]:
            text.append(PA.SAY_SELL_UNMATCHED[lang].format(items=capital(self.items_text(found["unmatched"][:3]))))
        if found["twins"]:
            text.append(PA.SAY_SELL_TWINS[lang].format(items=self.items_text([t["sell"] for t in found["twins"][:2]])))
        if not text:
            return self.say(PA.SAY_SELL_NOTHING[lang])
        text.append(PA.SAY_SELL_NEXT[lang])
        self.say(" ".join(text))

    def price_question(self, table):
        pieces = self.unique_items({"top", "bottom", "dress", "outerwear", "shoes", "bag"})
        if not pieces:
            return None
        piece = self.rng.choice(pieces)
        self.no_arabizi()
        self.ask(table, a=self.name_for_question(piece))
        self.call("list_wardrobe")
        return piece, self.call("price_hint", item_id=str(piece["_id"]))

    @scenario
    def scenario_price(self):
        asked = self.price_question(PA.ASK_PRICE)
        if asked is None:
            return self.scenario_what_sell()
        piece, hint = asked
        lang, a = self.lang, self.your(piece)
        if "error" in hint:
            return self.say(PA.SAY_PRICE_NONE[lang].format(a=a))
        self.say(PA.SAY_PRICE[lang].format(a=a, low=hint["low"], high=hint["high"], median=hint["median"],
                                            count=hint["count"]))

    @scenario
    def scenario_sell(self):
        """'Help me sell my jacket': a price from look-alikes, then the ready-filled Sell form."""
        asked = self.price_question(PA.ASK_SELL)
        if asked is None:
            return self.scenario_what_sell()
        piece, hint = asked
        lang = self.lang
        if "error" in hint:
            return self.say(PA.SAY_SELL_ASK_PRICE[lang].format(a=self.your(piece)))
        title = capital(item_text(piece, lang))
        self.call("prepare_sell", price_tnd=hint["median"], item_id=str(piece["_id"]), title=title)
        self.say(PA.SAY_SELL_FORM[lang].format(title=title, price=hint["median"]))

    @scenario
    def scenario_my_listings(self):
        mine = []
        for _ in range(self.rng.choice([0, 1, 1, 2, 3])):
            category, sub, colour, _ = self.maker.piece(self.dress_wearer)
            status = self.rng.choice(["pending", "active", "active", "rejected", "gone"])
            mine.append({"_id": object_id(self.rng), "source_id": SELLERS, "seller_id": self.user["_id"],
                         "category": category, "sub_category": sub, "colour": colour,
                         "title": listing_title(sub, colour), "price_tnd": float(self.rng.randrange(5, 60)),
                         "status": status, "in_stock": status == "active", "city": self.rng.choice(PA.CITIES),
                         "review_note": self.rng.choice(PA.REVIEW_NOTES) if status == "rejected" else "",
                         "created_at": datetime.now(timezone.utc) - timedelta(days=self.rng.randrange(20))})
        if mine:
            self.world.db.listings.insert_many(mine)
        self.ask(PA.ASK_MY_LISTINGS)
        rows = self.call("my_listings")["listings"]
        lang = self.lang
        if not rows:
            return self.say(PA.SAY_NO_LISTINGS[lang])
        listed = [PA.SAY_MY_LISTING[lang].format(title=r["title"], price=f"{r['price_tnd']:g}",
                                                 status=PA.STATUS_WORDS[r["status"]][lang]) for r in rows]
        text = [PA.SAY_MY_LISTINGS[lang].format(list="; ".join(listed))]
        notes = [r["review_note"] for r in rows if r["status"] == "rejected" and r["review_note"]]
        if notes:
            text.append(PA.SAY_REJECTED_NOTE[lang].format(note=notes[0]))
        self.say(" ".join(text))

    # -------------------------------------------------------------- Explainer
    def outfit_pair(self):
        """Two pieces the user can name that make an outfit (top + bottom, dress + shoes...)."""
        by_cat = {}
        for d in self.unique_items():
            by_cat.setdefault(d["category"], []).append(d)
        options = [(a, b) for a, b in (("top", "bottom"), ("dress", "shoes"), ("bottom", "shoes"))
                   if by_cat.get(a) and by_cat.get(b)]
        if not options:
            return None, by_cat
        a, b = self.rng.choice(options)
        return [self.rng.choice(by_cat[a]), self.rng.choice(by_cat[b])], by_cat

    @scenario
    def scenario_why_score(self):
        pair, _ = self.outfit_pair()
        if pair is None:
            return self.scenario_how_scoring()
        self.no_arabizi()
        self.ask(PA.ASK_WHY_SCORE, a=self.name_for_question(pair[0]), b=self.name_for_question(pair[1]))
        self.call("list_wardrobe")
        out = self.call("explain_outfit", item_ids=[str(d["_id"]) for d in pair])
        lang = self.lang
        if "error" in out:
            clash = re.sub(r"^.*together: ", "", out["error"]).split("; ")
            return self.say(P.SAY_CLASH[lang].format(items=self.items_text(pair), reasons=self.reasons_text(clash)))
        points = join([f"{PA.PART_WORDS[p][lang]} {round(v['points'])}/{round(v['max'])}"
                       for p, v in out["points"].items() if v["counted"]], lang)
        text = [PA.SAY_WHY_SCORE[lang].format(score=round(out["score"]), points=points)]
        if out["works"]:
            text.append(PA.SAY_WORKS[lang].format(facts=self.reasons_text(out["works"], table=PA.FACTS)))
        if out["problems"]:
            text.append(PA.SAY_PROBLEMS[lang].format(facts=self.reasons_text(out["problems"], table=PA.FACTS)))
        weakest = out["weakest"]
        text.append(PA.SAY_SWAP[lang].format(piece=self.your(weakest["piece"]), swap=self.your(weakest["swap_for"]),
                                             gain=round(weakest["gain"], 1))
                    if isinstance(weakest, dict) else PA.SAY_NO_SWAP[lang])
        self.say(" ".join(text))

    @scenario
    def scenario_what_if(self):
        pair, by_cat = self.outfit_pair()
        if pair is None or len(by_cat.get(pair[1]["category"], [])) < 2:
            return self.scenario_why_score()
        other = self.rng.choice([d for d in by_cat[pair[1]["category"]] if d is not pair[1]])
        self.no_arabizi()
        self.ask(PA.ASK_WHAT_IF, a=self.name_for_question(pair[0]), b=self.name_for_question(pair[1]),
                 c=self.name_for_question(other))
        self.call("list_wardrobe")
        out = self.call("what_if", item_ids=[str(d["_id"]) for d in pair], remove_id=str(pair[1]["_id"]),
                        add_id=str(other["_id"]))
        lang = self.lang
        if "error" in out:
            clash = re.sub(r"^.*together: ", "", out["error"]).split("; ")
            return self.say(P.SAY_CLASH[lang].format(items=self.items_text([pair[0], other]),
                                                     reasons=self.reasons_text(clash)))
        self.say(PA.SAY_WHAT_IF[lang].format(c=self.your(other), b=self.your(pair[1]),
                                             before=round(out["before"]["score"]), after=round(out["after"]["score"]),
                                             change=f"{out['change']:+g}"))

    @scenario
    def scenario_labels(self):
        pieces = self.unique_items()
        if not pieces:
            return self.scenario_how_scoring()
        piece = self.rng.choice(pieces)
        self.no_arabizi()
        self.ask(PA.ASK_LABELS, a=self.name_for_question(piece))
        self.call("list_wardrobe")
        out = self.call("explain_labels", item_id=str(piece["_id"]))
        lang = self.lang
        fields = out["fields"]
        shown = [f for f in ("sub_category", "colour", "pattern") if fields[f].get("model_guess")]
        labels = join([PA.SAY_LABEL[lang].format(field=PA.FIELD_WORDS[f][lang],
                                                 value=value_word(f, fields[f]["model_guess"], lang),
                                                 conf=round(100 * fields[f]["confidence"])) for f in shown], lang)
        text = [PA.SAY_LABELS[lang].format(labels=labels)]
        unsure = [PA.FIELD_WORDS[f][lang] for f in shown if fields[f]["unsure"] and not fields[f]["corrected_by_user"]]
        if unsure:
            text.append(PA.SAY_UNSURE[lang].format(fields=join(unsure, lang)))
        corrected = [PA.FIELD_WORDS[f][lang] for f in shown if fields[f]["corrected_by_user"]]
        if corrected:
            text.append(PA.SAY_CORRECTED[lang].format(fields=join(corrected, lang)))
        if out.get("action"):
            text.append(PA.SAY_OPEN_PANEL[lang])
        self.say(" ".join(text))

    @scenario
    def scenario_why_verdict(self):
        if self.rng.random() < 0.9:
            twin = self.rng.choice(self.docs) if self.docs and self.rng.random() < 0.2 else None
            self.add_scan(twin)
        self.ask(PA.ASK_WHY_VERDICT)
        out = self.call("explain_verdict")
        lang = self.lang
        if "error" in out:
            return self.say(P.SAY_BUY_NO_SCAN[lang])
        path = out["path"]
        text = [PA.SAY_VERDICT[lang].format(verdict=PA.VERDICT_WORDS[out["verdict"]][lang], good=path["good"],
                                            buy_min=path["buy_min"])]
        if out["to_next_verdict"]:
            text.append(PA.SAY_TO_NEXT[lang].format(n=out["to_next_verdict"]))
        if out["twins"]:
            text.append(PA.SAY_VERDICT_TWINS[lang].format(items=self.items_text([t["item"] for t in out["twins"][:1]])))
        self.say(" ".join(text))

    @scenario
    def scenario_how_scoring(self):
        self.ask(PA.ASK_HOW_SCORING)
        out = self.call("how_scoring_works")
        lang, total = self.lang, sum(out["weights"].values())
        weights = join([f"{PA.PART_WORDS[p][lang]} {round(100 * w / total)}%" for p, w in out["weights"].items()],
                       lang)
        self.say(PA.SAY_HOW_SCORING[lang].format(weights=weights, good=round(out["good_outfit"])))

    @scenario
    def scenario_why_similar(self):
        """'Why do my X and my Y look alike?' (or the last scan and my X): explain_similarity."""
        pieces = self.unique_items()
        if len(pieces) < 2:
            return self.scenario_how_scoring()
        lang = self.lang
        by_cat = {}
        for d in pieces:
            by_cat.setdefault(d["category"], []).append(d)
        same = [c for c, ds in by_cat.items() if len(ds) >= 2]
        self.no_arabizi()
        if self.rng.random() < 0.25:                     # the last scan against one of their pieces
            piece = self.rng.choice(pieces)
            self.add_scan(piece if self.rng.random() < 0.5 else None)
            self.ask(PA.ASK_WHY_SIMILAR_SCAN, a=self.name_for_question(piece))
            self.call("list_wardrobe")
            out = self.call("explain_similarity", item_id="last_scan", other_id=str(piece["_id"]))
            names = [PA.SAY_SCAN_PIECE[lang], self.your(piece)]
        else:
            pair = (self.rng.sample(by_cat[self.rng.choice(same)], 2) if same and self.rng.random() < 0.8
                    else self.rng.sample(pieces, 2))
            self.ask(PA.ASK_WHY_SIMILAR, a=self.name_for_question(pair[0]), b=self.name_for_question(pair[1]))
            self.call("list_wardrobe")
            out = self.call("explain_similarity", item_id=str(pair[0]["_id"]), other_id=str(pair[1]["_id"]))
            names = [self.your(pair[0]), self.your(pair[1])]
        text = []
        if "similarity" in out:
            text.append(PA.SAY_SIMILARITY[lang].format(a=capital(names[0]), b=names[1],
                                                       pct=round(100 * out["similarity"])))
            if out.get("near_twin"):
                text.append(PA.SAY_NEAR_TWIN[lang])
        shared = [PA.FIELD_WORDS[x["field"]][lang] for x in out["shared_labels"] if x["field"] != "category"]
        if shared:
            text.append(PA.SAY_SHARED[lang].format(labels=join(shared, lang)))
        differs = [PA.FIELD_WORDS[x["field"]][lang] for x in out["different_labels"]]
        if differs:
            text.append(PA.SAY_DIFFERS[lang].format(labels=join(differs, lang)))
        if out["both_read_as"]:
            text.append(PA.SAY_BOTH_READ[lang].format(
                concepts=join([PA.CONCEPT_WORDS[c][lang] for c in out["both_read_as"]], lang)))
        elif out["contrast"]:
            c = out["contrast"]
            text.append(PA.SAY_CONTRAST[lang].format(a=names[0], b=names[1], ca=PA.CONCEPT_WORDS[c["a"]][lang],
                                                     cb=PA.CONCEPT_WORDS[c["b"]][lang]))
        self.say(" ".join(text))

    # -------------------------------------------------------------- any agent
    @scenario
    def scenario_chit_chat(self):
        kind = self.rng.choice(["hello", "thanks", "off_topic"])
        if kind == "hello":
            self.ask(P.ASK_HELLO)
            self.say(self.hello())
        elif kind == "thanks":
            self.ask(P.ASK_THANKS)
            self.say(self.pick(P.SAY_THANKS[self.lang]))
        else:
            self.ask(P.ASK_OFF_TOPIC)
            self.say(P.SAY_OFF_TOPIC[self.lang])

    def hello(self):
        if self.agent == "stylist":
            return P.SAY_HELLO[self.lang]
        return PA.SAY_HELLO_AGENT[self.agent][self.lang]

    # questions with no slot, by the agent that answers them (for hand-offs)
    HANDOFF_QUESTIONS = {
        "stylist": [PA.ASK_TODAY, P.ASK_SUGGEST], "shopping": [P.ASK_BUY, PA.ASK_SIMILAR_SCAN],
        "analyst": [PA.ASK_INSIGHTS, PA.ASK_STATS, PA.ASK_TWINS], "seller": [PA.ASK_WHAT_SELL, PA.ASK_MY_LISTINGS],
        "explainer": [PA.ASK_WHY_VERDICT, PA.ASK_HOW_SCORING],
    }

    @scenario
    def scenario_handoff(self):
        """A question for another agent reached this one: say who to ask, in one sentence, no tool."""
        target = self.rng.choice([a for a in AGENTS if a != self.agent])
        self.ask(self.rng.choice(self.HANDOFF_QUESTIONS[target]))
        name = PA.AGENT_NAMES[target][self.lang]
        self.say(self.pick(PA.SAY_HANDOFF[self.lang]).format(agent=name, Agent=capital(name)))

    def build(self, scenario):
        if self.rng.random() < EARLIER_EXCHANGE and scenario not in ("chit_chat", "handoff"):
            self.ask(P.ASK_HELLO)                      # earlier text-only exchange
            self.say(self.hello())
            self.new_turn()
        getattr(self, "scenario_" + scenario)()
        return [{"role": "system", "content": self.system()}] + self.messages


def route_row(rng, world, split, k):
    """One router decision: the router's prompt, a question, the agent's name."""
    tool_scenarios = [s for s, (agent, _) in SCENARIOS.items() if agent]
    name = rng.choice(tool_scenarios)
    conv = Conversation(rng, world, split, SCENARIOS[name][0])
    conv.build(name)
    question = next(m["content"] for m in reversed(conv.messages) if m["role"] == "user")
    messages = [{"role": "system", "content": router_prompt()}, {"role": "user", "content": question},
                {"role": "assistant", "content": conv.agent}]
    return {"id": f"{split}_{k:05d}", "scenario": "route", "agent": "router", "language": conv.lang,
            "answer_languages": [], "tools": [], "messages": messages}


def build_split(split, n, db):
    rng = random.Random(SEEDS[split])
    world = World(db, rng)
    weights = {s: w for s, (_, w) in SCENARIOS.items()}
    rows = []
    for k in range(n):
        name = weighted(rng, weights)
        if name == "route":
            rows.append(route_row(rng, world, split, k))
            continue
        agent = SCENARIOS[name][0] or rng.choice(SCENARIO_AGENTS.get(name, list(AGENTS)))
        conv = Conversation(rng, world, split, agent)
        messages = conv.build(name)
        rows.append({"id": f"{split}_{k:05d}", "scenario": conv.kind, "agent": agent, "language": conv.lang,
                     "answer_languages": conv.answer_languages, "tools": conv.schemas(), "messages": messages})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scale", type=float, default=1.0, help="multiply every split size")
    ap.add_argument("--show", type=int, default=0, help="print this many train conversations")
    ap.add_argument("--mongo", default="mongodb://localhost:27017")
    args = ap.parse_args()
    from pymongo import MongoClient
    client = MongoClient(args.mongo)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        for split, size in SIZES.items():
            rows = build_split(split, max(1, int(size * args.scale)), client[BUILD_DB])
            with open(OUT_DIR / f"{split}.jsonl", "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{split}: {len(rows)} conversations, "
                  f"agents {dict(Counter(r['agent'] for r in rows))}, "
                  f"languages {dict(Counter(r['language'] for r in rows))}")
            print(f"  scenarios {dict(sorted(Counter(r['scenario'] for r in rows).items()))}")
            if split == "train":
                for r in rows[:args.show]:
                    print("-" * 70)
                    for m in r["messages"][1:]:
                        body = m["content"] or json.dumps(m.get("tool_calls"), ensure_ascii=False)
                        print(f"[{m['role']}] {body[:300]}")
    finally:
        client.drop_database(BUILD_DB)
    (OUT_DIR / "dataset-metadata.json").write_text(json.dumps(
        {"title": "dressme-chat-sft", "id": KAGGLE_DATASET, "licenses": [{"name": "other"}]},
        indent=2))
    shutil.copy(ROOT / "src" / "phase4" / "finetune_chat.py", OUT_DIR)    # the Kaggle notebook runs this copy
    print(f"-> {OUT_DIR}")


if __name__ == "__main__":
    main()
