"""Train the brand-from-photo probe and save models/checkpoints/brand_probe.joblib.

    python src/phase4/train_label_check.py --emb data/ta_fc.csv --text data/tayara_text.csv

--emb : item_id + 512 FashionCLIP columns (e000..e511), one row per ad
--text: item_id, title, description
"""
import argparse, re, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
sys.path.insert(0, str(Path(__file__).parent))
from brand_text import claimed_brand
from label_check import LabelCheck, load_rules

ap = argparse.ArgumentParser(); ap.add_argument('--emb', required=True); ap.add_argument('--text', required=True)
ap.add_argument('--out', default=None)
ap.add_argument('--segment', default='everyday', help="keep only this segment (the report used 'everyday'); '' keeps all")
a = ap.parse_args()
e = pd.read_csv(a.emb); t = pd.read_csv(a.text)
if a.segment and 'segment' in e.columns:
    e = e[e.segment == a.segment]
d = e.merge(t[['item_id', 'title', 'description']], on='item_id').copy()
cols = [c for c in e.columns if re.fullmatch(r'e\d{3}', c)]
X = d[cols].values.astype(np.float32); X /= np.linalg.norm(X, axis=1, keepdims=True)
d['brand'] = [claimed_brand(ti, de) for ti, de in zip(d.title, d.description)]
rules = load_rules()
vc = d.brand.value_counts(); keep = vc[vc >= rules['min_brand_ads']].index
m = d.brand.isin(keep).values
clf = LogisticRegression(C=10, max_iter=5000, class_weight='balanced').fit(X[m], d.brand[m])
lc = LabelCheck(clf.coef_, clf.intercept_, clf.classes_, rules=rules,
                meta={"n_ads": int(m.sum()), "brands": {b: int(vc[b]) for b in clf.classes_},
                      "grouped_cv_top1": 0.70, "grouped_cv_top3": 0.89, "chance": 0.34})
p = lc.save(Path(a.out) if a.out else LabelCheck.load.__defaults__[0])
print(f'trained on {m.sum()} ads, {len(clf.classes_)} brands -> {p}')
