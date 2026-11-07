import sys, re
from pathlib import Path
import numpy as np, pandas as pd, pytest
ROOT = Path(__file__).resolve().parents[2]
import pytest
if not (ROOT / 'models/checkpoints/brand_probe.joblib').exists() or not (ROOT / 'models/checkpoints/condition_hint.joblib').exists():
    pytest.skip("label check / condition hint models not trained here (git-ignored)", allow_module_level=True)
sys.path.insert(0, str(ROOT / 'src' / 'phase4'))
from label_check import LabelCheck
from condition_hint import ConditionHint
from brand_text import claimed_brand

lc = LabelCheck.load(ROOT / 'models/checkpoints/brand_probe.joblib')
ch = ConditionHint.load(ROOT / 'models/checkpoints/condition_hint.joblib')
rng = np.random.default_rng(0)
V = rng.normal(size=512).astype(np.float32)

def test_claimed_brand():
    assert claimed_brand('Basket Adidas Original') == 'adidas'
    assert claimed_brand('Robe en coton') is None
    assert claimed_brand('NEW BALANCE 574', 'pointure 42') == 'new balance'

def test_no_brand_no_action():
    r = lc.check(V, 'Robe en coton', asking_price=5, estimate_median=100)
    assert r['claimed_brand'] is None and r['action'] is None

def test_never_says_fake():
    for price in (1, 50, 500):
        r = lc.check(V, 'Nike Air Max original', asking_price=price, estimate_median=200)
        assert 'fake' not in str(r).lower() and 'counterfeit' not in str(r).lower()

def test_requires_both_signals():
    probs = lc.brand_probs(V); last = list(probs)[-1]      # a brand the photo does NOT support
    cheap = lc.check(V, f'{last} original', asking_price=10, estimate_median=100)
    fair = lc.check(V, f'{last} original', asking_price=100, estimate_median=100)
    assert cheap['photo_supports_claim'] is False
    assert cheap['action'] == 'ask_label_photo' and fair['action'] is None

def test_probs_sum_to_one():
    assert abs(sum(lc.brand_probs(V).values()) - 1) < 1e-4

def test_condition_hint_range():
    h = ch.hint(V)
    assert 0 <= h['looks_new_score'] <= 1 and 0 <= h['percentile'] <= 1
    assert h['action'] in (None, 'confirm_condition')
