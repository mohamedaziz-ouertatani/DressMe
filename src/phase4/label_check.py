"""'Check the label': does the photo and the price support the brand the ad claims?

This is NOT a counterfeit detector, and it must never say "fake".
No public dataset contains confirmed counterfeits photographed like second-hand
ads (we audited ~30 sources), so a fake/genuine classifier could be neither
trained nor tested. What we CAN measure:

  * brand from the photo: a linear probe on frozen FashionCLIP, 15 brands,
    grouped 5-fold CV: 70% top-1, 89% top-3 (chance 34%, garment type alone 40%)
  * price: a brand normally ADDS ~26%; asking under half the estimate is unusual

When both disagree with the claim, the app asks for a close-up of the label.
On 562 branded Tayara ads that happens for 7 (1.2%). Whether those are fakes is
unknown: there is no ground truth. The prompt is a request, not an accusation.

    lc = make_label_check()
    lc.check(vector, title="Basket Adidas Original", description="...",
             asking_price=70, estimate_median=141)
"""
from __future__ import annotations
import csv
from pathlib import Path
import numpy as np

try:
    from item_images import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parents[2]

from brand_text import claimed_brand, claims_original

RULES_CSV = ROOT / "mappings" / "label_check.csv"
ARTIFACT = ROOT / "models" / "checkpoints" / "brand_probe.joblib"


def load_rules(path: Path = RULES_CSV) -> dict:
    with open(path, newline='', encoding='utf-8') as f:
        return {r['setting']: float(r['value']) for r in csv.DictReader(f)}


def _unit(v):
    v = np.asarray(v, np.float32).ravel()
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-6 else v


class LabelCheck:
    def __init__(self, coef, intercept, classes, meta=None, rules=None):
        self.coef = np.asarray(coef, np.float32)          # (n_brands, 512)
        self.intercept = np.asarray(intercept, np.float32)
        self.classes = [str(c) for c in classes]
        self.meta = meta or {}
        self.rules = rules or load_rules()

    def brand_probs(self, vector) -> dict:
        z = self.coef @ _unit(vector) + self.intercept
        p = np.exp(z - z.max()); p /= p.sum()
        return dict(sorted(zip(self.classes, p.tolist()), key=lambda kv: -kv[1]))

    def check(self, vector, title: str, description: str = '',
              asking_price: float | None = None, estimate_median: float | None = None) -> dict:
        brand = claimed_brand(title, description)
        out = {"claimed_brand": brand, "claims_original": claims_original(title, description),
               "photo_brands": None, "photo_supports_claim": None,
               "price_ratio": None, "unusually_cheap": None,
               "action": None, "message": None}
        if brand is None:
            return out
        k = int(self.rules['photo_top_k'])
        if brand in self.classes:
            probs = self.brand_probs(vector)
            top = list(probs)[:k]
            out["photo_brands"] = [{"brand": b, "p": round(probs[b], 3)} for b in top]
            out["photo_supports_claim"] = brand in top
        if asking_price and estimate_median:
            r = float(asking_price) / float(estimate_median)
            out["price_ratio"] = round(r, 2)
            out["unusually_cheap"] = r < self.rules['price_ratio_low']
        photo_off = out["photo_supports_claim"] is False
        cheap = out["unusually_cheap"] is True
        fire = (photo_off and cheap) if self.rules['require_both'] >= 1 else (photo_off or cheap)
        if fire:
            out["action"] = "ask_label_photo"
            out["message"] = (f"This ad names {brand.title()}. A photo that shows the label "
                              f"or logo clearly helps buyers trust it.")
        return out

    def save(self, path: Path = ARTIFACT):
        import joblib
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"coef": self.coef, "intercept": self.intercept,
                     "classes": self.classes, "meta": self.meta}, path)
        return path

    @classmethod
    def load(cls, path: Path = ARTIFACT, rules=None):
        import joblib
        if not Path(path).exists():
            raise FileNotFoundError(f"{path} not found -- run src/phase4/train_label_check.py first")
        d = joblib.load(path)
        return cls(d["coef"], d["intercept"], d["classes"], d.get("meta"), rules)


def make_label_check(settings=None):
    """None when the artifact is absent, so the route can answer 503."""
    try:
        return LabelCheck.load()
    except (FileNotFoundError, KeyError, ValueError):
        return None
