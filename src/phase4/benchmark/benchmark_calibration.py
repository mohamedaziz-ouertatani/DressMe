"""
Does the image model beat a no-image baseline at the DINAR level, on friperie?

Compares, on the same grouped folds (FashionCLIP, pooled training):
  raw ridge            ridge prediction + channel offset
  shipped (rank map)   what price.py serves: rank among training predictions,
                       read off the training-fold price distribution of the
                       channel+category (all of the channel if < 8 items)
  category median      no image: median training price of channel+category
  blend w              w * ridge + (1-w) * category mean (log), w tuned on
                       the training fold only (inner grouped CV)

    python src/phase4/benchmark/benchmark_calibration.py          # ridge
    python src/phase4/benchmark/benchmark_calibration.py svr      # RBF SVR

With "svr" the model is StandardScaler + SVR(C=3, epsilon=0.1, gamma="scale"),
the setting the inner CV of benchmark_models.py picked most often. Output:
reports/phase4/benchmark/calibration_benchmark_<model>.csv
"""
import sys

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from benchmark_models import F2A, OUT, T2G, load

SEEDS = [0, 1, 2, 3, 4]
alphas = np.logspace(-1, 4, 24)
MODEL = (sys.argv[1:] or ['ridge'])[0]
if MODEL not in ('ridge', 'svr'):
    sys.exit('model: ridge or svr')
M = 'SVR' if MODEL == 'svr' else 'ridge'

ta, Xt, _ = load('ta_fc.csv', 'subcat_label')
fr, Xf, _ = load('fr_fc.csv', 'category')
X = np.vstack([Xt, Xf])
price = np.concatenate([ta.price, fr.price])
chan = np.array(['classified'] * len(ta) + ['friperie'] * len(fr))
cat = np.array([T2G.get(c, c) for c in ta.subcat_label.astype(str)] +
               [F2A.get(c, 'other') for c in fr.category.astype(str)])
key = np.char.add(np.char.add(chan, ':'), cat)
logp = np.log(price)
n = len(price)
S = X @ X.T; np.fill_diagonal(S, 0); S[chan[:, None] != chan[None, :]] = 0
_, groups = connected_components(csr_matrix(S >= .99), directed=False)


def regressor():
    if MODEL == 'svr':
        return make_pipeline(StandardScaler(), SVR(kernel='rbf', gamma='scale', C=3, epsilon=0.1))
    return make_pipeline(StandardScaler(), RidgeCV(alphas=alphas))


def fit_predict(tr, te):
    off = {c: logp[tr][chan[tr] == c].mean() for c in np.unique(chan)}
    y = logp - np.array([off[c] for c in chan])
    m = regressor().fit(X[tr], y[tr])
    raw_te = m.predict(X[te]) + np.array([off[c] for c in chan[te]])
    # shipped rank -> quantile mapping
    tr_scores = np.sort(m.predict(X[tr]))
    pct = np.searchsorted(tr_scores, m.predict(X[te])) / len(tr_scores)
    shipped = np.empty(len(te))
    catmed = np.empty(len(te)); catmean = np.empty(len(te))
    for j, i in enumerate(te):
        ref = price[tr][key[tr] == key[i]]
        if len(ref) < 8:
            ref = price[tr][chan[tr] == chan[i]]
        shipped[j] = np.log(np.quantile(ref, pct[j]))
        catmed[j] = np.log(np.median(ref))
        catmean[j] = np.log(ref).mean()
    return raw_te, shipped, catmed, catmean


def blend_weight(tr):
    """Choose w on the training fold only, by inner grouped CV, friperie error."""
    oof = np.zeros((len(tr), 2))
    for itr, ite in GroupKFold(3).split(tr, groups=groups[tr]):
        a, b = tr[itr], tr[ite]
        raw, _, _, cm = fit_predict(a, b)
        oof[ite, 0], oof[ite, 1] = raw, cm
    f = chan[tr] == 'friperie'
    ws = np.linspace(0, 1, 11)
    errs = [np.abs(w * oof[f, 0] + (1 - w) * oof[f, 1] - logp[tr][f]).mean() for w in ws]
    return ws[int(np.argmin(errs))]


RAW, SERVED, BLEND = f'raw {M}', f'{M} served (rank map)', f'blend {M} + category mean (tuned w)'
res = {k: np.zeros((len(SEEDS), n)) for k in [RAW, SERVED,
                                              'category median (no image)',
                                              'category mean (no image)', BLEND]}
wsel = []
for si, seed in enumerate(SEEDS):
    rng = np.random.default_rng(seed)
    gids = rng.permutation(np.unique(groups))
    for b in np.array_split(gids, 5):
        te = np.where(np.isin(groups, b))[0]; tr = np.where(~np.isin(groups, b))[0]
        raw, shp, cmed, cmean = fit_predict(tr, te)
        w = blend_weight(tr); wsel.append(w)
        res[RAW][si, te] = raw
        res[SERVED][si, te] = shp
        res['category median (no image)'][si, te] = cmed
        res['category mean (no image)'][si, te] = cmean
        res[BLEND][si, te] = w * raw + (1 - w) * cmean
    print('seed', seed, 'done', flush=True)

rows = []
rng = np.random.default_rng(1)
for ch in ['friperie', 'classified']:
    m = chan == ch
    base = np.abs(res['category median (no image)'][:, m] - logp[m]).mean(0)
    for k, P in res.items():
        e = np.abs(P[:, m] - logp[m])
        sp = [spearmanr(P[s, m], logp[m]).statistic for s in range(len(SEEDS))]
        d = e.mean(0) - base
        bs = [d[rng.integers(0, m.sum(), m.sum())].mean() for _ in range(2000)]
        rows.append({'channel': ch, 'method': k,
                     'spearman': np.mean(sp), 'spearman_sd': np.std(sp),
                     'typical_error': np.exp(e.mean()),
                     'd_logerr_vs_cat_median': d.mean(),
                     'lo': np.quantile(bs, .025), 'hi': np.quantile(bs, .975)})
out = pd.DataFrame(rows)
OUT.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT / f'calibration_benchmark_{MODEL}.csv', index=False)
pd.set_option('display.width', 200)
print(out.round(3).to_string(index=False))
print('blend weight chosen (inner CV):', pd.Series(wsel).value_counts().to_dict())
