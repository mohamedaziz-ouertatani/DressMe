"""Train the condition hint and save models/checkpoints/condition_hint.joblib.

    python src/phase4/train_condition_hint.py --emb data/ta_fc.csv --text data/tayara_text.csv

Positive = seller wrote new-with-tags / new / like-new; negative = good / used / defect.
The percentile reference uses grouped out-of-fold scores, so a new photo is
compared with scores the model produced on ads it had not seen.
"""
import argparse, re, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.linear_model import LogisticRegression
sys.path.insert(0, str(Path(__file__).parent))
from condition_text import grade
from condition_hint import ConditionHint

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
g = [grade(f"{ti} . {de if isinstance(de, str) else ''}") for ti, de in zip(d.title.fillna(''), d.description)]
d['grade'] = g
lab = d.grade.isin(['new_tags', 'new', 'like_new', 'good', 'used', 'defect']).values
y = d.grade.isin(['new_tags', 'new', 'like_new']).values[lab].astype(int); Xl = X[lab]
S = Xl @ Xl.T; np.fill_diagonal(S, 0); _, grp = connected_components(csr_matrix(S >= 0.95), directed=False)
C = 3.0
oof = np.zeros(len(y)); rng = np.random.default_rng(0); ids = rng.permutation(np.unique(grp))
for b in np.array_split(ids, 5):
    te = np.isin(grp, b)
    oof[te] = LogisticRegression(C=C, max_iter=4000, class_weight='balanced').fit(Xl[~te], y[~te]).predict_proba(Xl[te])[:, 1]
clf = LogisticRegression(C=C, max_iter=4000, class_weight='balanced').fit(Xl, y)
ch = ConditionHint(clf.coef_[0], clf.intercept_[0], oof,
                   meta={"n_ads": int(lab.sum()), "positives": int(y.sum()), "C": C,
                         "grouped_cv_auc": 0.63, "grades": d.grade[lab].value_counts().to_dict()})
from sklearn.metrics import roc_auc_score
print(f'labelled ads {lab.sum()} (new/like-new {y.sum()}), this run OOF AUC {roc_auc_score(y, oof):.3f}')
print('->', ch.save(Path(a.out) if a.out else ConditionHint.load.__defaults__[0]))
