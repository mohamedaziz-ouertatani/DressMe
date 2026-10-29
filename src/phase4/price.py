"""
A price for a second-hand garment, from its FashionCLIP vector.

`resale.py` prices a garment from look-alike LISTINGS: the 25th-75th percentile
of what similar things are currently advertised at. That needs no training and
was the right call when there was no priced data. There is now: 1,658 tayara
classified ads and 183 friperie garments, collected and hand-checked.

On the same embeddings and the same folds, a trained model ranks better than
the percentile rule (0.585 against 0.507 on tayara; the error reduction has a
confidence interval clear of zero). On the 183-item friperie set the gap is
large but the interval straddles zero, so there it is recorded as underpowered
rather than as a win.

WHAT THE MODEL DOES, AND WHAT IT DOES NOT
-----------------------------------------
It RANKS well and MIS-LEVELS. A ridge trained on classified ads keeps about
half its ranking power on Instagram friperie (Spearman 0.33 against 0.58
in-market) but its dinar values are wrong, because the two channels are not the
same market:

    shoes      tayara 150 DT   friperie 35 DT     4.3x
    bags       tayara  90 DT   friperie 35 DT     2.6x
    clothing   tayara  70 DT   friperie 25 DT     2.8x

So the estimate is produced in two steps: the model gives a RANK, and that rank
is mapped onto the price distribution of the channel being priced for. That is
what takes typical error from x2.37 to x1.56. It also means the model cannot
price for a channel it has no reference distribution for, and `estimate()`
says so rather than guessing.

Typical error is still **x1.56**. This is a hint worth a look, not a valuation.
`estimate()` always returns a band, never a bare number, for that reason.

    rules = load_rules()
    model = PriceModel.load()
    model.estimate(vector, category="shoes", channel="friperie", rules=rules)
    # {'low': 25, 'median': 35, 'high': 48, 'channel': 'friperie', ...}

Every tunable number is in mappings/price_model.csv, not here.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

try:                                    # the API puts src/phase4 on the path
    from item_images import ROOT
except ImportError:                     # standalone use
    ROOT = Path(__file__).resolve().parents[2]

RULES_CSV = ROOT / "mappings" / "price_model.csv"
ARTIFACT = ROOT / "models" / "checkpoints" / "price_model.joblib"

SETTINGS = ("band_low_pct", "band_high_pct", "min_category_items",
            "examples", "round_to")
CHANNELS = ("friperie", "classified")


# --------------------------------------------------------------------- rules
def load_rules(path: Path = RULES_CSV) -> dict:
    """The team's settings. Anything unknown or missing stops with an error.

    Same contract as resale.load_rules: a typo in the csv must fail loudly at
    start-up, not silently fall back to a default nobody chose.
    """
    settings: dict[str, float] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            kind = row["kind"].strip()
            name = row["name"].strip()
            value = row["value"].strip()
            if kind != "setting":
                raise ValueError(f"{path.name} line {line}: unknown kind {kind!r}")
            if name not in SETTINGS:
                raise ValueError(f"{path.name} line {line}: unknown setting {name!r}")
            settings[name] = float(value)
    missing = [s for s in SETTINGS if s not in settings]
    if missing:
        raise ValueError(f"{path.name}: missing setting(s) {missing}")
    if not 0 <= settings["band_low_pct"] < settings["band_high_pct"] <= 100:
        raise ValueError(f"{path.name}: band_low_pct must be below band_high_pct, "
                         "both within 0-100")
    return settings


# --------------------------------------------------------------------- model
class PriceModel:
    """A ridge over FashionCLIP vectors, plus one reference price distribution
    per channel and category.

    The ridge supplies the ORDER; the reference distribution supplies the
    DINARS. Keeping them separate is what lets one trained model serve two
    channels that price 3-4x apart, and what makes it refuse a channel it has
    never seen rather than quietly answering in the wrong currency of value.
    """

    def __init__(self, coef, intercept, mean, scale, train_logp, reference,
                 meta=None):
        self.coef = np.asarray(coef, np.float32)
        self.intercept = float(intercept)
        self.mean = np.asarray(mean, np.float32)
        self.scale = np.asarray(scale, np.float32)
        # the training predictions, sorted -- turns a raw score into a rank
        self.train_logp = np.sort(np.asarray(train_logp, np.float32))
        # {channel: {category_or_"*": sorted array of observed prices}}
        self.reference = {c: {k: np.sort(np.asarray(v, np.float32))
                              for k, v in cats.items()}
                          for c, cats in reference.items()}
        self.meta = meta or {}

    # ---------------------------------------------------------------- scoring
    def _raw(self, vector) -> float:
        v = np.asarray(vector, np.float32).ravel()
        if v.shape[0] != self.coef.shape[0]:
            raise ValueError(f"expected a {self.coef.shape[0]}-d vector, "
                             f"got {v.shape[0]}")
        n = float(np.linalg.norm(v))
        if n > 1e-6:
            v = v / n          # the backend stores unit-length vectors
        z = (v - self.mean) / np.where(self.scale == 0, 1.0, self.scale)
        return float(z @ self.coef + self.intercept)

    def percentile_of(self, vector) -> float:
        """Where this garment sits among the training items, 0-1."""
        raw = self._raw(vector)
        return float(np.searchsorted(self.train_logp, raw) / len(self.train_logp))

    # --------------------------------------------------------------- estimate
    def estimate(self, vector, category=None, channel="friperie", rules=None):
        """A price band in TND, or None when this cannot be answered honestly.

        Returns None (never a guess) when the channel has no reference
        distribution. A caller that gets None should fall back to
        resale.price_range or say nothing -- not invent a number.
        """
        rules = rules or load_rules()
        if channel not in self.reference:
            return None

        prices = self._reference_for(channel, category,
                                     int(rules["min_category_items"]))
        if prices is None or len(prices) < 4:
            return None

        pct = self.percentile_of(vector)
        half = (rules["band_high_pct"] - rules["band_low_pct"]) / 200.0
        lo_p = min(max(pct - half, 0.0), 1.0)
        hi_p = min(max(pct + half, 0.0), 1.0)

        step = rules["round_to"]
        def q(p):
            return _round_to(float(np.quantile(prices, p)), step)

        median, low, high = q(pct), q(lo_p), q(hi_p)
        if low > median:
            low = median
        if high < median:
            high = median

        used_fallback = category is not None and \
            category not in self.reference[channel]
        # the error of THIS channel: the overall figure is inflated by the
        # classified ads' 5-1800 DT spread and describes no user's prices
        by_channel = self.meta.get("error_factor_by_channel") or {}
        error_factor = by_channel.get(channel, self.meta.get("error_factor"))
        return {
            "low": low,
            "median": median,
            "high": high,
            "channel": channel,
            "based_on": "category" if not used_fallback and category else "all",
            "count": int(len(prices)),
            "percentile": round(pct, 3),
            "typical_error_factor": error_factor,
            "note": _note(channel, used_fallback),
        }

    def _reference_for(self, channel, category, min_items):
        cats = self.reference[channel]
        if category and category in cats and len(cats[category]) >= min_items:
            return cats[category]
        return cats.get("*")

    # ------------------------------------------------------------- persistence
    def save(self, path: Path = ARTIFACT):
        import joblib
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"coef": self.coef, "intercept": self.intercept,
                     "mean": self.mean, "scale": self.scale,
                     "train_logp": self.train_logp,
                     "reference": {c: {k: v for k, v in cats.items()}
                                   for c, cats in self.reference.items()},
                     "meta": self.meta}, path)
        return path

    @classmethod
    def load(cls, path: Path = ARTIFACT):
        import joblib
        if not Path(path).exists():
            raise FileNotFoundError(
                f"{path} not found -- run src/phase4/train_price.py first")
        d = joblib.load(path)
        return cls(d["coef"], d["intercept"], d["mean"], d["scale"],
                   d["train_logp"], d["reference"], d.get("meta"))


# ------------------------------------------------------------------- helpers
def _round_to(value: float, step: float) -> int:
    if step <= 0:
        return int(round(value))
    return int(round(value / step) * step)


def _note(channel: str, used_fallback: bool) -> str:
    """The warning that must travel with the number.

    A model trained on classified ads quoting classified-ad prices to someone
    shopping friperie is wrong by a factor of three, and nothing in the output
    would show it. So the channel is always named.
    """
    where = ("friperie and Instagram resale prices" if channel == "friperie"
             else "classified-ad prices")
    note = f"Estimated against {where}."
    if used_fallback:
        note += " Too few items of this category, so all categories were used."
    return note


def make_price_model(settings=None):
    """Return a PriceModel, or None when the artifact is absent.

    Follows the make_tryon / make_weather pattern: an optional engine that
    returns None when it is not available, so the route can answer 503 rather
    than the app failing to start.
    """
    try:
        return PriceModel.load()
    except (FileNotFoundError, KeyError, ValueError):
        return None
