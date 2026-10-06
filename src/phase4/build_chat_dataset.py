"""
Synthetic conversations to fine-tune the local chat model (LLM.md).

Each conversation is what the real /chat would see: the production system
prompt and tool descriptions (imported from backend/app/routers/chat.py, so they
can never drift apart), a user question in English, French or Tunisian Arabic,
the tool calls the assistant should make, the REAL tool answers, and a short
final answer that only talks about what the tools returned.

How the tool answers are real: every conversation gets a random wardrobe (same
fields as the app's items, with FashionCLIP-like vectors), and the backend's own
tool functions run on it through a tiny fake database. So scores, verdicts and
reasons all come from src/phase4/compatibility.py with the team's weights.

What the model learns from it:
  - which tool to call, with which arguments (season / occasion / n / category);
  - two steps for "does A go with B?": list_wardrobe for the ids, then score_outfit;
  - never invent clothes (questions about items the user doesn't own);
  - answer in the user's language (also when they write in Arabizi), short;
  - no tool for greetings, thanks or off-topic questions.

The sentences come from src/phase4/chat_phrases.py (team-editable). In the train split
the last phrasing of every list with 3+ phrasings is held out, so val / test
also measure questions the model has never seen.

Run from the project root (needs the backend requirements, no GPU, ~1 min):
    python src/phase4/build_chat_dataset.py
Output: data/processed/chat_sft/{train,val,test}.jsonl, one conversation per line:
    {"id", "scenario", "language" (of the last question), "answer_languages" (one per
     plain answer), "tools": [...], "messages": [...]}
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

import chat_phrases as P                                  # noqa: E402
from app.chat_engine import tool_schema                    # noqa: E402
from app.routers.chat import SYSTEM, tools_for             # noqa: E402
from app.vocab import SUB_PARENT                           # noqa: E402

OUT_DIR = ROOT / "data" / "processed" / "chat_sft"
SIZES = {"train": 3000, "val": 200, "test": 300}
SEEDS = {"train": 1, "val": 2, "test": 3}
KAGGLE_DATASET = "mohameddazizz/dressme-chat-sft"

SCENARIO_WEIGHTS = {"list": 14, "suggest": 28, "score": 20, "not_owned": 6, "buy": 16,
                    "follow_up": 8, "chit_chat": 8}
LANGUAGE_WEIGHTS = {"fr": 45, "ar": 35, "en": 20}          # the app's profile language
OTHER_LANGUAGE = 0.12      # the user writes in another language than their profile
ARABIZI = 0.5              # Darija questions typed in Latin letters
EARLIER_EXCHANGE = 0.25    # a greeting exchange before the question

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


def weighted(rng, weights):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


# ------------------------------------------------------------------ random wardrobes
class Collection:
    """Just enough of a MongoDB collection for the chat tools."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, query):
        return [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]

    def find_one(self, query, sort=None):
        found = self.find(query)
        return found[-1] if found else None


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

    def item(self, user_id, dress_wearer, category=None, style=None):
        rng = self.rng
        weights = dict(CATEGORY_WEIGHTS)
        if not dress_wearer:
            weights.pop("dress")
        category = category or weighted(rng, weights)
        subs = [s for s in self.subs[category] if dress_wearer or s not in DRESS_WEARER_ONLY]
        sub = rng.choice(subs or self.subs[category])
        colours = dict(COLOUR_WEIGHTS, **({"gold": 4, "silver": 4} if category in METAL_FOR else {}))
        colour = "" if rng.random() < UNSURE_COLOUR else weighted(rng, colours)
        clothes = category in ("top", "bottom", "dress", "outerwear", "traditional", "swimwear")
        pattern = weighted(rng, PATTERN_WEIGHTS) if clothes else "solid"
        doc = {"_id": "%024x" % rng.getrandbits(96), "user_id": user_id,
               "category": category, "sub_category": sub, "colour": colour, "pattern": pattern,
               "coverage": rng.choice([None, None, 2, 3, 4, 5]),
               "season": rng.sample(["summer", "winter", "mid-season"], rng.randint(1, 2))
               if rng.random() < 0.4 else [],
               "usage": rng.sample(["casual", "formal", "sport", "wedding", "eid", "work"],
                                   rng.randint(1, 3)) if rng.random() < 0.4 else [],
               "predicted": {"pattern": {"value": pattern, "conf": round(rng.uniform(0.6, 1), 2)}},
               "corrected": [],
               "vector": self.vector(rng.randrange(N_STYLES) if style is None else style).tobytes()}
        return doc

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


def reason_text(reason, lang):
    """A reason of src/phase4/compatibility.py (English) in the answer's language."""
    if lang == "en":
        return reason
    for pattern, fr, ar in P.REASONS:
        m = re.fullmatch(pattern, reason)
        if m:
            groups = [", ".join(reason_word(t, lang) for t in g.split(", ")) for g in m.groups()]
            return (fr if lang == "fr" else ar).format(*groups)
    return reason


def capital(text):
    return text[:1].upper() + text[1:]


# ------------------------------------------------------------------ conversations
def scenario(fn):
    """Records which scenario really ran (one may fall back to another)."""
    def run(self):
        self.kind = fn.__name__.removeprefix("scenario_")
        return fn(self)
    return run


class Conversation:
    """One synthetic chat: picks the words, runs the real tools, writes messages."""

    def __init__(self, rng, maker, split):
        self.rng, self.split = rng, split
        self.user = {"_id": "u%023x" % rng.getrandbits(92), "profile": {}}
        self.docs, self.dress_wearer = maker.wardrobe(self.user["_id"])
        self.maker = maker
        self.candidates = []
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
            db=SimpleNamespace(items=Collection(self.docs), candidates=Collection(self.candidates)))))
        self.tools = tools_for(request, self.user)
        self.profile_language = weighted(rng, LANGUAGE_WEIGHTS)
        self.min_coverage = rng.choice([None, None, None, 3, 4, 5])
        self.user["profile"] = {"language": self.profile_language, "min_coverage": self.min_coverage}
        self.messages = []
        self.answer_languages = []                     # language of each plain answer, in order
        self.new_turn()

    def new_turn(self):
        """Language of the next question: usually the profile's, sometimes another."""
        lang = self.profile_language
        if self.rng.random() < OTHER_LANGUAGE:
            lang = self.rng.choice([x for x in LANGUAGE_WEIGHTS if x != lang])
        self.lang = lang                               # language of the answer
        self.ask_lang = "arabizi" if lang == "ar" and self.rng.random() < ARABIZI else lang

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
        result = self.tools[name](**args)
        self.messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": name, "arguments": args}}]})
        self.messages.append({"role": "tool", "name": name,
                              "content": json.dumps(result, ensure_ascii=False)})
        return result

    def system(self):
        return SYSTEM.format(language=self.profile_language, min_coverage=self.min_coverage or "")

    def items_text(self, items, form="your"):
        lang = self.lang
        return join([item_text(i, lang, form if lang != "ar" else "bare") for i in items], lang)

    def reasons_text(self, reasons, limit=2):
        return join([reason_text(r, self.lang) for r in reasons[:limit]], self.lang)

    # -------------------------------------------------------------- scenarios
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
        shown = outfits[:args.get("n", 1)]
        text = self.outfit_sentences(shown, first, **slots)
        text.append(self.pick(P.SAY_ASK_MORE[self.lang]))
        self.say(" ".join(text))

    def unique_items(self):
        """Items a user can name without ambiguity (one per sub_category + colour)."""
        count = Counter((d["sub_category"], d["colour"]) for d in self.docs)
        return [d for d in self.docs if count[(d["sub_category"], d["colour"])] == 1]

    def name_for_question(self, item):
        if self.ask_lang == "ar" or self.ask_lang == "arabizi":
            return item_text(item, "ar", "the")
        return item_text(item, self.ask_lang, "my")

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
        if self.ask_lang == "arabizi":           # no Arabizi item names: ask in Arabic script
            self.ask_lang = "ar"
        self.ask(P.ASK_SCORE, a=self.name_for_question(pair[0]), b=self.name_for_question(pair[1]))
        self.call("list_wardrobe")
        result = self.call("score_outfit", item_ids=[d["_id"] for d in pair])
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

    @scenario
    def scenario_not_owned(self):
        """The user names a piece they don't have: never pretend it exists."""
        owned = {(d["sub_category"], d["colour"]) for d in self.docs}
        cat = self.rng.choice(["top", "bottom", "shoes", "outerwear"])
        for _ in range(50):
            fake = self.maker.item(self.user["_id"], self.dress_wearer, cat)
            if fake["colour"] and (fake["sub_category"], fake["colour"]) not in owned:
                break
        else:
            return self.scenario_list()
        real = self.unique_items()
        other = self.rng.choice(real) if real else None
        if other is None or other["category"] == cat:
            return self.scenario_list()
        if self.ask_lang == "arabizi":
            self.ask_lang = "ar"
        pair = [fake, other] if self.rng.random() < 0.5 else [other, fake]
        self.ask(P.ASK_SCORE, a=self.name_for_question(pair[0]), b=self.name_for_question(pair[1]))
        items = self.call("list_wardrobe")
        lang = self.lang
        same = [i for i in items if i["category"] == cat]
        words = P.CATEGORY_WORDS[cat][lang]
        alternatives = (P.SAY_ALTERNATIVES[lang].format(cat=words, items=join(
            [item_text(i, lang) for i in same], lang)) if same
            else P.SAY_NO_ALTERNATIVE[lang].format(cat=words))
        missing = indefinite(fake, lang)
        self.say(P.SAY_NOT_OWNED[lang].format(missing=missing, alternatives=alternatives))

    @scenario
    def scenario_buy(self):
        if self.rng.random() < 0.85:
            if self.docs and self.rng.random() < 0.15:          # a near twin of something owned
                twin = self.rng.choice(self.docs)
                cand = dict(self.maker.item(self.user["_id"], self.dress_wearer, twin["category"]),
                            sub_category=twin["sub_category"], colour=twin["colour"])
                v = np.frombuffer(twin["vector"], np.float16).astype(np.float32)
                v = v + self.maker.nprng.normal(size=VECTOR_DIM) * 0.15 / np.sqrt(VECTOR_DIM)
                cand["vector"] = (v / np.linalg.norm(v)).astype(np.float16).tobytes()
            else:
                cand = self.maker.item(self.user["_id"], self.dress_wearer)
            cand["created_at"] = datetime.now(timezone.utc) - timedelta(minutes=5)
            self.candidates.append(cand)
        self.ask(P.ASK_BUY)
        advice = self.call("buy_advice_last_scan")
        lang = self.lang
        if "error" in advice:
            return self.say(P.SAY_BUY_NO_SCAN[lang])
        cand = self.candidates[-1]
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
        more = self.call("suggest_outfits", n=5)
        rest = more[1:3]
        if not rest:
            return self.say(P.SAY_NO_MORE[self.lang])
        self.say(" ".join(self.outfit_sentences(rest, P.SAY_ANOTHER)))

    @scenario
    def scenario_chit_chat(self):
        kind = self.rng.choice(["hello", "thanks", "off_topic"])
        if kind == "hello":
            self.ask(P.ASK_HELLO)
            self.say(P.SAY_HELLO[self.lang])
        elif kind == "thanks":
            self.ask(P.ASK_THANKS)
            self.say(self.pick(P.SAY_THANKS[self.lang]))
        else:
            self.ask(P.ASK_OFF_TOPIC)
            self.say(P.SAY_OFF_TOPIC[self.lang])

    def build(self, scenario):
        if self.rng.random() < EARLIER_EXCHANGE and scenario != "chit_chat":
            self.ask(P.ASK_HELLO)                      # earlier text-only exchange
            self.say(P.SAY_HELLO[self.lang])
            self.new_turn()
        getattr(self, "scenario_" + scenario)()
        return [{"role": "system", "content": self.system()}] + self.messages


def build_split(split, n, tools_schema):
    rng = random.Random(SEEDS[split])
    maker = WardrobeMaker(rng)
    rows = []
    for k in range(n):
        scenario = weighted(rng, SCENARIO_WEIGHTS)
        conv = Conversation(rng, maker, split)
        messages = conv.build(scenario)
        rows.append({"id": f"{split}_{k:05d}", "scenario": conv.kind, "language": conv.lang,
                     "answer_languages": conv.answer_languages, "tools": tools_schema, "messages": messages})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scale", type=float, default=1.0, help="multiply every split size")
    ap.add_argument("--show", type=int, default=0, help="print this many train conversations")
    args = ap.parse_args()
    tools_schema = [tool_schema(f) for f in tools_for(None, None).values()]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for split, size in SIZES.items():
        rows = build_split(split, max(1, int(size * args.scale)), tools_schema)
        with open(OUT_DIR / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{split}: {len(rows)} conversations, "
              f"scenarios {dict(Counter(r['scenario'] for r in rows))}, "
              f"languages {dict(Counter(r['language'] for r in rows))}")
        if split == "train":
            for r in rows[:args.show]:
                print("-" * 70)
                for m in r["messages"][1:]:
                    body = m["content"] or json.dumps(m.get("tool_calls"), ensure_ascii=False)
                    print(f"[{m['role']}] {body[:300]}")
    (OUT_DIR / "dataset-metadata.json").write_text(json.dumps(
        {"title": "dressme-chat-sft", "id": KAGGLE_DATASET, "licenses": [{"name": "other"}]},
        indent=2))
    shutil.copy(ROOT / "src" / "phase4" / "finetune_chat.py", OUT_DIR)    # the Kaggle notebook runs this copy
    print(f"-> {OUT_DIR}")


if __name__ == "__main__":
    main()
