"""A condition HINT from the photo, learned from real ads.

The earlier YOLO detector was trained on synthetic stains and fell to chance on
real photos (AUC 0.53). This one is trained on real Tayara photos, labelled
with the condition the seller wrote in the ad.

Grouped 5-fold CV, C tuned inside the training folds:
  new vs used (like-new left out)      AUC 0.69  [0.65, 0.76]
  new/like-new vs good/used/defect     AUC 0.63  [0.60, 0.71]
  works inside a category (shoes 0.67, bags 0.66, dresses 0.72), not only
  between them; t-shirts and 'other' are at chance.
  lowest 10% of scores: 33% worn, against 15% overall (x2.3)

So it is a hint, not a grade: it can ask the seller to double-check the
condition, it cannot set it. Stains and tears are NOT detected: only 10 real
ads mention one, too few to train or test.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np

try:
    from item_images import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parents[2]

from label_check import load_rules, _unit

ARTIFACT = ROOT / "models" / "checkpoints" / "condition_hint.joblib"


class ConditionHint:
    def __init__(self, coef, intercept, train_scores, meta=None, rules=None):
        self.coef = np.asarray(coef, np.float32).ravel()
        self.intercept = float(intercept)
        self.train_scores = np.sort(np.asarray(train_scores, np.float32))
        self.meta = meta or {}
        self.rules = rules or load_rules()

    def score(self, vector) -> float:
        return float(1 / (1 + np.exp(-(self.coef @ _unit(vector) + self.intercept))))

    def hint(self, vector) -> dict:
        s = self.score(vector)
        pct = float(np.searchsorted(self.train_scores, s) / len(self.train_scores))
        worn = pct < self.rules['worn_hint_pct']
        return {"looks_new_score": round(s, 3), "percentile": round(pct, 3),
                "action": "confirm_condition" if worn else None,
                "message": ("The photo suggests this piece may have been worn. "
                            "Please check the condition you selected.") if worn else None}

    def save(self, path: Path = ARTIFACT):
        import joblib
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"coef": self.coef, "intercept": self.intercept,
                     "train_scores": self.train_scores, "meta": self.meta}, path)
        return path

    @classmethod
    def load(cls, path: Path = ARTIFACT, rules=None):
        import joblib
        if not Path(path).exists():
            raise FileNotFoundError(f"{path} not found -- run src/phase4/train_condition_hint.py first")
        d = joblib.load(path)
        return cls(d["coef"], d["intercept"], d["train_scores"], d.get("meta"), rules)


def make_condition_hint(settings=None):
    try:
        return ConditionHint.load()
    except (FileNotFoundError, KeyError, ValueError):
        return None
