"""
A price for a second-hand garment, from its FashionCLIP vector.

`resale.py` prices a garment from look-alike LISTINGS: the 25th-75th percentile
of what similar things are currently advertised at. That needs no training and
was the right call when there was no priced data. There is now: 1,523 everyday
tayara classified ads and 183 friperie garments, collected and hand-checked.

On the same embeddings and the same folds, a trained model ranks better than
the percentile rule (0.585 against 0.507 on tayara; the error reduction has a
confidence interval clear of zero). On the 183-item friperie set the gap is
large but the interval straddles zero, so there it is recorded as underpowered
rather than as a win.

WHAT THE MODEL DOES, AND WHAT IT DOES NOT
-----------------------------------------
It RANKS well and MIS-LEVELS. A model trained on classified ads keeps about
half its ranking power on Instagram friperie (ridge: Spearman 0.33 against 0.58
in-market) but its dinar values are wrong, because the two channels are not the
same market:

    shoes      tayara 150 DT   friperie 35 DT     4.3x
    bags       tayara  90 DT   friperie 35 DT     2.6x
    clothing   tayara  70 DT   friperie 25 DT     2.8x

So the estimate is produced in two steps: the model gives a RANK, and that rank
is mapped onto the price distribution of the channel being priced for. That
mapping is what brings typical error down to x1.42 on friperie (x1.90 on
classified ads). It also means the model cannot price for a channel it has no
reference distribution for, and `estimate()` says so rather than guessing.

THE MODEL: AN RBF-KERNEL SVR (since Nov 2026; a ridge before)
-------------------------------------------------------------
The scorer is StandardScaler + SVR(kernel="rbf", gamma="scale"), C and epsilon
picked by inner grouped CV (src/phase4/train_price.py). In the benchmark
(src/phase4/benchmark/, reports/phase4/benchmark/) it was the only model better
than the ridge on BOTH channels with an interval clear of zero. The gain comes
from the kernel, not from the SVR's robust loss: a kernel ridge gains as much,
and a linear SVR does not. The ridge is still supported: an artifact
without a "kind" (written before the SVR) loads as kind "linear".

Typical error is still **x1.42** on friperie (the error of what estimate()
serves, see train_price.py). This is a hint worth a look, not a valuation.
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

# the garment's condition, which the model cannot see on a photo: the band is
# multiplied by the team's measured factor (condition_<name> in price_model.csv)
CONDITIONS = ("new_tags", "like_new", "good", "stained", "torn")
SETTINGS = ("band_low_pct", "band_high_pct", "min_category_items",
            "examples", "round_to", "tag_factor", "show_priced_high") + \
    tuple(f"condition_{c}" for c in CONDITIONS)
CHANNELS = ("friperie", "classified")
KINDS = ("linear", "svr")


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
    if settings["tag_factor"] <= 1:
        raise ValueError(f"{path.name}: tag_factor must be above 1")
    if settings["show_priced_high"] not in (0, 1):
        raise ValueError(f"{path.name}: show_priced_high must be 0 or 1")
    for c in CONDITIONS:
        if settings[f"condition_{c}"] <= 0:
            raise ValueError(f"{path.name}: condition_{c} must be above 0")
    return settings


# --------------------------------------------------------------------- model
class PriceModel:
    """A regressor over FashionCLIP vectors (kind "linear" = ridge, kind "svr" =
    RBF-kernel SVR), plus one reference price distribution per channel and
    category.

    The regressor supplies the ORDER; the reference distribution supplies the
    DINARS. Keeping them separate is what lets one trained model serve two
    channels that price 3-4x apart, and what makes it refuse a channel it has
    never seen rather than quietly answering in the wrong currency of value.
    """

    def __init__(self, coef=None, intercept=0.0, mean=None, scale=None,
                 train_logp=(), reference=None, meta=None, kind="linear",
                 pipeline=None):
        # kind "linear": a ridge stored as plain numbers (coef / intercept on
        #   standardised inputs). Old artifacts have no "kind" and are this.
        # kind "svr": a fitted sklearn Pipeline (StandardScaler + RBF SVR),
        #   pickled whole, so it needs the same scikit-learn version to load:
        #   train it inside the backend container.
        if kind not in KINDS:
            raise ValueError(f"unknown model kind {kind!r}, expected one of {KINDS}")
        self.kind = kind
        self.pipeline = pipeline
        if kind == "svr":
            if pipeline is None:
                raise ValueError("an svr PriceModel needs its fitted pipeline")
            self.dim = int(pipeline[0].n_features_in_)
        else:
            self.coef = np.asarray(coef, np.float32)
            self.intercept = float(intercept)
            self.mean = np.asarray(mean, np.float32)
            self.scale = np.asarray(scale, np.float32)
            self.dim = int(self.coef.shape[0])
        # the training predictions, sorted -- turns a raw score into a rank
        self.train_logp = np.sort(np.asarray(train_logp, np.float32))
        # {channel: {category_or_"*": sorted array of observed prices}}
        self.reference = {c: {k: np.sort(np.asarray(v, np.float32))
                              for k, v in cats.items()}
                          for c, cats in (reference or {}).items()}
        self.meta = meta or {}

    # ---------------------------------------------------------------- scoring
    def _raw(self, vector) -> float:
        v = np.asarray(vector, np.float32).ravel()
        if v.shape[0] != self.dim:
            raise ValueError(f"expected a {self.dim}-d vector, got {v.shape[0]}")
        n = float(np.linalg.norm(v))
        if n > 1e-6:
            v = v / n          # the backend stores unit-length vectors
        if self.kind == "svr":
            # the pipeline standardises the input itself, as in training
            return float(self.pipeline.predict(v.astype(np.float64)[None, :])[0])
        z =(v - self.mean) / np.where(self.scale == 0, 1.0, self.scale)
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

        # the error of THIS channel: the overall figure is inflated by the
        # classified ads' 5-1800 DT spread and describes no user's prices
        by_channel = self.meta.get("error_factor_by_channel") or {}
        error_factor = by_channel.get(channel, self.meta.get("error_factor"))
        # never claim more precision than the model has: a tight reference
        # distribution can give "40 to 50 TND" (about x1.1) while the model is
        # typically off by x1.5, so the band is at least median / err to median * err
        if error_factor and error_factor > 1:
            low = min(low, _round_to(median / error_factor, step))
            high = max(high, _round_to(median * error_factor, step))

        used_fallback = category is not None and \
            category not in self.reference[channel]
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
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        d = {"kind": self.kind,
             "train_logp": self.train_logp,
             "reference": {c: {k: v for k, v in cats.items()}
                           for c, cats in self.reference.items()},
             "meta": self.meta}
        if self.kind == "svr":
            d["pipeline"] = self.pipeline
        else:
            d.update(coef=self.coef, intercept=self.intercept,
                     mean=self.mean, scale=self.scale)
        joblib.dump(d, path)
        return path

    @classmethod
    def load(cls, path: Path = ARTIFACT):
        import joblib
        if not Path(path).exists():
            raise FileNotFoundError(
                f"{path} not found -- run src/phase4/train_price.py first")
        d = joblib.load(path)
        # an artifact written before the svr kind has no "kind": it is linear
        if d.get("kind", "linear") == "svr":
            return cls(train_logp=d["train_logp"], reference=d["reference"],
                       meta=d.get("meta"), kind="svr", pipeline=d["pipeline"])
        return cls(d["coef"], d["intercept"], d["mean"], d["scale"],
                   d["train_logp"], d["reference"], d.get("meta"))


# ------------------------------------------------------------------- helpers
def _round_to(value: float, step: float) -> int:
    if step <= 0:
        return int(round(value))
    return int(round(value / step) * step)


def with_condition(band: dict, condition: str, rules: dict) -> dict:
    """The band for a piece in this condition: low / median / high multiplied
    by the team's factor, then rounded as estimate() rounds. "good" (x1.00)
    gives the band back unchanged. The model reads the photo only, and it
    does not see damage, so the user says the condition.
    """
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}, expected one of {CONDITIONS}")
    factor = rules[f"condition_{condition}"]
    out = {**band, "condition": condition, "condition_factor": factor}
    for k in ("low", "median", "high"):
        if band.get(k) is not None:
            out[k] = _round_to(band[k] * factor, rules["round_to"])
    return out


def price_tag(price_tnd, band, rules) -> str | None:
    """"good_deal", "priced_high" or None for an asked price against an estimate.

    Measured from the band's MEDIAN by tag_factor, not from the band's edges:
    the edges are only about x1.5 from the median, so on normal friperie prices
    they would tag about 13% as a deal and 26% as high (measured with the
    ridge). x2 tags about 7% as a deal and 4% as high with the SVR (7% and 9%
    with the ridge): grouped-CV estimates on the 183 hand-checked friperie
    items at their own asking prices, mean of 5 fold assignments. "priced_high" is only returned
    when show_priced_high is 1. On since price_hint uses the same model (#68):
    the chat's suggestion and the tag agree. Wording kept soft ('Above the
    usual price'), shown only above x2 the estimate, always with the band.
    Set to 0 to switch off.
    """
    median = (band or {}).get("median")
    if not price_tnd or price_tnd <= 0 or not median or median <= 0:
        return None
    factor = rules["tag_factor"]
    if price_tnd < median / factor:
        return "good_deal"
    if price_tnd > median * factor and rules["show_priced_high"]:
        return "priced_high"
    return None


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
