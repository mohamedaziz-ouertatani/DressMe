"""
Benchmark of price-regression models and their hyperparameters.

Same protocol as the shipped model (src/phase4/train_price.py):
  * features: one 512-d image embedding per garment (FashionCLIP or OpenAI CLIP)
  * target: log asking price, with each channel's mean removed
  * training data: tayara classified ads (1,523) + friperie (183), pooled
  * evaluation: grouped 5-fold CV; near-duplicates (cos >= 0.99 in EITHER
    backbone) are kept in one fold; repeated over several random fold
    assignments (seeds)
  * hyperparameters are tuned INSIDE each training fold (inner grouped CV),
    never on the test fold

Metrics, per channel (friperie is what users see):
  * Spearman between predicted and true log price (ranking)
  * typical error factor = exp(mean |log pred - log true|)
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Lasso, Ridge, RidgeCV
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

warnings.filterwarnings("ignore")
SEEDS = [0, 1, 2]
FOLDS = 5

F2A = {'tshirt': 'top', 'top': 'top', 'longsleeve': 'top', 'hoodie': 'top', 'sweater': 'top',
       'shirt': 'top', 'cardigan': 'top', 'jeans': 'bottom', 'skirt': 'bottom', 'shorts': 'bottom',
       'trousers': 'bottom', 'jacket': 'outerwear', 'vest': 'outerwear', 'dress': 'dress',
       'bag': 'bag', 'shoes': 'shoes', 'accessory': 'accessory', 'watch': 'accessory'}
T2G = {'vetements': 'clothing', 'chaussures': 'shoes', 'sacs_access': 'bags'}


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data' / 'processed'
OUT = ROOT / 'reports' / 'phase4' / 'benchmark'
# short names used by the three scripts -> the files in data/processed/
# (gitignored; the *_openaiclip.csv pair is only needed by benchmark_models.py)
INPUTS = {'ta_fc.csv': DATA / 'tayara_fashionclip.csv',
          'fr_fc.csv': DATA / 'friperie_fashionclip.csv',
          'ta_oc.csv': DATA / 'tayara_openaiclip.csv',
          'fr_oc.csv': DATA / 'friperie_openaiclip.csv'}


def load(path, catcol):
    path = INPUTS.get(path, path)
    if not Path(path).exists():
        sys.exit(f'Not found: {path} (see reports/phase4/benchmark/README.md for the inputs)')
    d = pd.read_csv(path)
    if 'segment' in d:
        d = d[d.segment == 'everyday']
    d['price'] = pd.to_numeric(d['price'], errors='coerce')
    d = d[d.price > 0].reset_index(drop=True)
    E = sorted([c for c in d.columns if c.startswith('e') and c[1:].isdigit()],
               key=lambda c: int(c[1:]))
    X = d[E].to_numpy(np.float64, copy=True)   # pandas 3 returns a read-only view
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    key = d['item_id'] if 'item_id' in d else d.index
    return d, X, key


def main():
    ta_fc, Xt_fc, kt = load('ta_fc.csv', 'subcat_label')
    ta_oc, Xt_oc, kt2 = load('ta_oc.csv', 'subcat_label')
    fr_fc, Xf_fc, kf = load('fr_fc.csv', 'category')
    fr_oc, Xf_oc, kf2 = load('fr_oc.csv', 'category')
    # align the two backbones on the same items
    assert len(ta_fc) == len(ta_oc) and len(fr_fc) == len(fr_oc), "row counts differ"
    if 'item_id' in fr_fc:
        assert (fr_fc.item_id.values == fr_oc.item_id.values).all()
    price = np.concatenate([ta_fc.price, fr_fc.price])
    chan = np.array(['classified'] * len(ta_fc) + ['friperie'] * len(fr_fc))
    cat = np.concatenate([
        ['classified:' + T2G.get(c, c) for c in ta_fc.subcat_label.astype(str)],
        ['friperie:' + F2A.get(c, 'other') for c in fr_fc.category.astype(str)]])
    logp = np.log(price)
    off = {c: logp[chan == c].mean() for c in np.unique(chan)}
    y = logp - np.array([off[c] for c in chan])
    XB = {'fashionclip': np.vstack([Xt_fc, Xf_fc]),
          'openai_clip': np.vstack([Xt_oc, Xf_oc])}

    # near-duplicate groups, union over both backbones and within channel
    n = len(y)
    rows, cols = [], []
    for X in XB.values():
        S = X @ X.T
        np.fill_diagonal(S, 0)
        S[chan[:, None] != chan[None, :]] = 0
        r, c = np.where(S >= 0.99)
        rows += list(r); cols += list(c)
    _, groups = connected_components(
        csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n)), directed=False)
    print(f"items {n} (classified {np.sum(chan=='classified')}, friperie {np.sum(chan=='friperie')}),"
          f" duplicate groups {len(np.unique(groups))}", flush=True)

    def outer_folds(seed):
        rng = np.random.default_rng(seed)
        gids = rng.permutation(np.unique(groups))
        for b in np.array_split(gids, FOLDS):
            te = np.isin(groups, b)
            yield np.where(~te)[0], np.where(te)[0]

    inner = GroupKFold(n_splits=3)

    def tuned(est, grid):
        def fit(Xtr, ytr, gtr):
            gs = GridSearchCV(est, grid, cv=inner, scoring='neg_mean_absolute_error', n_jobs=2)
            gs.fit(Xtr, ytr, groups=gtr)
            return gs.best_estimator_, gs.best_params_
        return fit

    def plain(est_factory):
        def fit(Xtr, ytr, gtr):
            m = est_factory().fit(Xtr, ytr)
            return m, {}
        return fit

    alphas = np.logspace(-1, 4, 24)
    MODELS = {
        # baselines with no image
        'baseline: global mean': None,
        'baseline: category mean (no image)': 'catmean',
        # linear
        'ridge (shipped)': plain(lambda: make_pipeline(StandardScaler(), RidgeCV(alphas=alphas))),
        'lasso': tuned(make_pipeline(StandardScaler(), Lasso(max_iter=5000)),
                       {'lasso__alpha': [0.003, 0.01, 0.03, 0.1]}),
        'PCA + ridge': tuned(make_pipeline(StandardScaler(), PCA(random_state=0), RidgeCV(alphas=alphas)),
                             {'pca__n_components': [16, 64, 128, 256]}),
        'ridge + category one-hot': 'ridge_cat',
        # neighbours (what resale.py does, as a regressor)
        'k-NN (cosine)': tuned(KNeighborsRegressor(metric='cosine', algorithm='brute'),
                               {'n_neighbors': [4, 8, 16, 32, 64], 'weights': ['uniform', 'distance']}),
        # kernel
        'SVR (RBF)': tuned(make_pipeline(StandardScaler(), SVR(kernel='rbf')),
                           {'svr__C': [0.3, 1, 3], 'svr__gamma': ['scale'], 'svr__epsilon': [0.1, 0.3]}),
        # trees
        'random forest': plain(lambda: RandomForestRegressor(
            n_estimators=300, max_features=0.3, min_samples_leaf=3, n_jobs=2, random_state=0)),
        'gradient boosting (LightGBM)': 'lgbm',
        # neural
        'MLP (1x256)': tuned(make_pipeline(StandardScaler(), MLPRegressor(
            hidden_layer_sizes=(256,), early_stopping=True, max_iter=500, random_state=0)),
            {'mlpregressor__alpha': [1e-2, 1e-1, 1.0]}),
    }

    def lgbm_fit(Xtr, ytr, gtr):
        import lightgbm as lgb
        best, bp = None, None
        est = lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, subsample=0.8,
                                subsample_freq=1, colsample_bytree=0.3, verbose=-1, n_jobs=2)
        gs = GridSearchCV(est, {'num_leaves': [7, 15], 'min_child_samples': [10, 30]},
                          cv=inner, scoring='neg_mean_absolute_error', n_jobs=1)
        gs.fit(Xtr, ytr, groups=gtr)
        return gs.best_estimator_, gs.best_params_

    only = sys.argv[1:] or None
    backbones = ['fashionclip', 'openai_clip']
    preds = {}       # (backbone, model) -> array seeds x n
    chosen = {}      # (backbone, model) -> list of best params
    cat_codes = pd.get_dummies(cat).to_numpy(float)
    for bb in backbones:
        X = XB[bb]
        for name, fit in MODELS.items():
            if only and not any(o.lower() in name.lower() for o in only):
                continue
            if bb == 'openai_clip' and name.startswith('baseline'):
                continue
            t0 = time.time()
            P = np.zeros((len(SEEDS), n)); params = []
            for si, seed in enumerate(SEEDS):
                for tr, te in outer_folds(seed):
                    if fit is None:
                        P[si, te] = y[tr].mean()
                    elif fit == 'catmean':
                        m = pd.Series(y[tr]).groupby(cat[tr]).mean()
                        P[si, te] = [m.get(c, y[tr].mean()) for c in cat[te]]
                    elif fit == 'ridge_cat':
                        Z = np.hstack([X, cat_codes])
                        mdl = make_pipeline(StandardScaler(), RidgeCV(alphas=alphas)).fit(Z[tr], y[tr])
                        P[si, te] = mdl.predict(Z[te])
                        params.append({'alpha': float(mdl[-1].alpha_)})
                    elif fit == 'lgbm':
                        mdl, bp = lgbm_fit(X[tr], y[tr], groups[tr])
                        P[si, te] = mdl.predict(X[te]); params.append(bp)
                    else:
                        mdl, bp = fit(X[tr], y[tr], groups[tr])
                        P[si, te] = mdl.predict(X[te])
                        if name.startswith('ridge (shipped)'):
                            bp = {'alpha': float(mdl[-1].alpha_)}
                        params.append(bp)
            preds[(bb, name)] = P
            chosen[(bb, name)] = params
            print(f"  {bb:12} {name:36} {time.time()-t0:6.0f}s", flush=True)

    # ------------------------------------------------------------- report
    rows = []
    ref = preds.get(('fashionclip', 'ridge (shipped)'))
    rng = np.random.default_rng(0)
    for (bb, name), P in preds.items():
        rec = {'backbone': bb, 'model': name}
        for ch in ['friperie', 'classified']:
            m = chan == ch
            sp = [spearmanr(P[s, m], y[m]).statistic for s in range(len(SEEDS))]
            er = [np.exp(np.abs(P[s, m] - y[m]).mean()) for s in range(len(SEEDS))]
            rec[f'{ch}_spearman'] = np.mean(sp)
            rec[f'{ch}_spearman_sd'] = np.std(sp)
            rec[f'{ch}_err'] = np.mean(er)
            # paired difference in |log error| vs shipped ridge, bootstrap over items
            if ref is not None and P is not ref:
                a = np.abs(P[:, m] - y[m]).mean(0)
                b = np.abs(ref[:, m] - y[m]).mean(0)
                d = a - b
                bs = [d[rng.integers(0, m.sum(), m.sum())].mean() for _ in range(2000)]
                rec[f'{ch}_dlogerr_vs_ridge'] = d.mean()
                rec[f'{ch}_dlogerr_lo'], rec[f'{ch}_dlogerr_hi'] = np.quantile(bs, [.025, .975])
        ps = chosen[(bb, name)]
        if ps:
            keys = sorted({k for p in ps for k in p})
            rec['chosen_params'] = '; '.join(
                f"{k}: " + ', '.join(f"{v}x{c}" for v, c in
                                    pd.Series([str(p.get(k)) for p in ps]).value_counts().items())
                for k in keys)
        rows.append(rec)
    out = pd.DataFrame(rows)
    tag = '_'.join(only) if only else 'all'
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / f'model_benchmark_{tag}.csv', index=False)
    pd.set_option('display.width', 250)
    print(out[['backbone', 'model', 'friperie_spearman', 'friperie_err', 'classified_spearman',
               'classified_err']].round(3).to_string(index=False))


if __name__ == '__main__':
    main()
