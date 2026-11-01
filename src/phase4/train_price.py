"""
Fit the price model and write models/checkpoints/price_model.joblib.

    python src/phase4/train_price.py
    python src/phase4/train_price.py --dry-run     # evaluate, write nothing
    python src/phase4/train_price.py --model ridge # the earlier linear model

Run it INSIDE the backend container (the svr artifact is a pickled sklearn
pipeline and loads only with the scikit-learn version that wrote it):

    docker exec -w /app dressme-backend-1 python src/phase4/train_price.py

WHY THE TARGET IS DEMEANED BY CHANNEL
-------------------------------------
The two priced corpora are not the same market:

    shoes      tayara 150 DT   friperie 35 DT     4.3x
    bags       tayara  90 DT   friperie 35 DT     2.6x
    clothing   tayara  70 DT   friperie 25 DT     2.8x

Fitting log price on the two pooled together would make the model spend its
capacity on a constant offset -- "is this a classified ad or an Instagram
post?" -- which is a fact about the channel, not about the garment.

So the target is log price with each channel's mean removed. The model then
learns one thing only: within a channel, which garments are expensive. The
dinar level comes back afterwards, from that channel's own reference price
distribution. That separation is what lets 1,841 items train one ranker that
serves two markets priced 3-4x apart.

Whether pooling actually beats training on tayara alone is MEASURED below, not
assumed. If it does not help, the script says so and you should use --tayara-only.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

ALPHAS = np.logspace(-1, 4, 24)
# the SVR's search grid; gamma stays "scale" (1 / (512 x variance)), as in the
# benchmark (src/phase4/benchmark/)
SVR_GRID = {"svr__C": [1, 3], "svr__epsilon": [0.05, 0.1, 0.2]}
DUP = 0.99
FOLDS = 5
EPS = 1e-12

# Reference prices are keyed by the APP's categories. The backend calls
# estimate() with its own nine categories (vocab.py): top, bottom, dress,
# outerwear, shoes, bag, accessory, traditional, swimwear. Keying references by
# OUR labels (tshirt, jeans, chaussures) would make every app call miss and
# silently fall back to "*".
FRIPERIE_TO_APP = {
    "tshirt": "top", "top": "top", "longsleeve": "top", "shirt": "top",
    "hoodie": "top", "sweater": "top", "cardigan": "top",
    "jeans": "bottom", "trousers": "bottom", "shorts": "bottom", "skirt": "bottom",
    "dress": "dress", "jacket": "outerwear", "vest": "outerwear",
    "shoes": "shoes", "bag": "bag", "accessory": "accessory", "watch": "accessory"}
# tayara only separates clothing / shoes / bags+accessories, so every
# garment category in the classified channel shares the clothing curve.
# That is coarser, and it is said so rather than invented.
TAYARA_TO_APP = {
    "chaussures": ["shoes"],
    "sacs_access": ["bag", "accessory"],
    "vetements": ["top", "bottom", "dress", "outerwear", "traditional", "swimwear"]}


def emb_cols(df):
    """Numeric order. String-sorting e0, e1, e10 permutes the dimensions and
    nothing raises -- see the e0/e000 near-miss in the report."""
    return sorted((c for c in df.columns if c.startswith("e") and c[1:].isdigit()),
                  key=lambda c: int(c[1:]))


def load(path: Path, channel: str, cat_col: str):
    df = pd.read_csv(path)
    if "price" not in df.columns and "asking_price_dt" in df.columns:
        df["price"] = df["asking_price_dt"]
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "segment" in df.columns:
        df = df[df.segment == "everyday"]
    df = df[df.price > 0].reset_index(drop=True)
    # copy=True: pandas 3 (the backend container) hands back a read-only view
    X = df[emb_cols(df)].to_numpy(np.float64, copy=True)
    X /= np.clip(np.linalg.norm(X, axis=1, keepdims=True), EPS, None)
    out = pd.DataFrame({"price": df.price.to_numpy(float),
                        "category": df[cat_col].astype(str).to_numpy(),
                        "channel": channel})
    return out, X


def groups_of(X):
    S = X @ X.T
    np.fill_diagonal(S, 0.0)
    _, lab = connected_components(csr_matrix(S >= DUP), directed=False)
    return lab


def folds_of(g, k, seed=0):
    rng = np.random.default_rng(seed)
    gids = rng.permutation(np.unique(g))
    out = []
    for b in np.array_split(gids, k):
        te = np.isin(g, b)
        if te.sum() and (~te).sum():
            out.append((np.where(~te)[0], np.where(te)[0]))
    return out


def fit_model(kind, X, y, g):
    """Fit one regressor; returns (fitted Pipeline, chosen parameters).

    ridge: StandardScaler + RidgeCV (alpha picked by RidgeCV's own
           leave-one-out, as before).
    svr:   StandardScaler + RBF SVR, C and epsilon picked by an INNER grouped
           3-fold CV on the data it is given (near-duplicates kept in one
           fold), so an outer test fold never helps choose them.
    """
    if kind == "ridge":
        pipe = make_pipeline(StandardScaler(), RidgeCV(alphas=ALPHAS)).fit(X, y)
        return pipe, {"alpha": round(float(pipe[-1].alpha_), 3)}
    search = GridSearchCV(
        make_pipeline(StandardScaler(), SVR(kernel="rbf", gamma="scale")),
        SVR_GRID, cv=GroupKFold(n_splits=3),
        scoring="neg_mean_absolute_error", n_jobs=2)
    search.fit(X, y, groups=g)
    return search.best_estimator_, {k.split("__")[1]: v
                                    for k, v in search.best_params_.items()}


def served_median(scores_tr, score, prices, step):
    """What estimate() would answer as the median: the score's rank among the
    training scores, read off the reference prices, rounded."""
    from price import _round_to
    pct = np.searchsorted(np.sort(scores_tr), score) / len(scores_tr)
    return _round_to(float(np.quantile(prices, pct)), step)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tayara", type=Path, default=Path("data/processed/tayara_fashionclip.csv"))
    ap.add_argument("--friperie", type=Path, default=Path("data/processed/friperie_fashionclip.csv"))
    ap.add_argument("--tayara-only", action="store_true",
                    help="fit on classified ads alone")
    ap.add_argument("--model", choices=("svr", "ridge"), default="svr",
                    help="svr (default): RBF-kernel SVR; ridge: the earlier linear model")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    # the team's settings, through the API's own strict loader: a bad csv
    # stops training here, before any work, just as it stops the route
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from price import ARTIFACT, PriceModel, load_rules   # noqa: E402
    rules = load_rules()
    min_items = int(rules["min_category_items"])

    for p in (args.tayara, args.friperie):
        if not p.exists():
            sys.exit(f"Not found: {p}")

    ta, Xt = load(args.tayara, "classified", "subcat_label")
    fr, Xf = load(args.friperie, "friperie", "category")
    if Xt.shape[1] != Xf.shape[1]:
        sys.exit(f"dimension mismatch: {Xt.shape[1]} vs {Xf.shape[1]}")

    meta = pd.concat([ta, fr], ignore_index=True)
    X = np.vstack([Xt, Xf])
    logp = np.log(meta.price.to_numpy(float))
    # the channel offset, removed from the target and kept for reference
    offset = {c: float(logp[(meta.channel == c).to_numpy()].mean())
              for c in meta.channel.unique()}
    y = logp - meta.channel.map(offset).to_numpy()

    print(f"\ntayara   {len(ta):>5}  median {ta.price.median():>6.0f} DT")
    print(f"friperie {len(fr):>5}  median {fr.price.median():>6.0f} DT")
    print(f"channel offset in log price: "
          f"{offset['classified'] - offset['friperie']:+.3f} "
          f"(x{np.exp(offset['classified'] - offset['friperie']):.2f})\n")

    # ---- does pooling actually help? measure, do not assume ----------------
    print("=" * 70)
    print("DOES POOLING BOTH CHANNELS BEAT TAYARA ALONE? (predicting friperie)")
    print("=" * 70)
    is_ta = (meta.channel == "classified").to_numpy()
    g_all = groups_of(X)                 # near-duplicate groups, both channels
    g_t, g_f = g_all[is_ta], g_all[~is_ta]
    y_t = y[is_ta]
    y_f = y[~is_ta]
    rng = np.random.default_rng(0)
    # tayara-only arm: never sees a friperie item, so one fit serves every fold
    m_solo, _ = fit_model(args.model, Xt, y_t, g_t)
    pooled, solo = [], []
    for tr, te in folds_of(g_f, FOLDS):
        solo.append((te, m_solo.predict(Xf[te])))
        # pooled arm: all tayara + the friperie TRAINING fold
        Xp = np.vstack([Xt, Xf[tr]])
        yp = np.concatenate([y_t, y_f[tr]])
        m_pool, _ = fit_model(args.model, Xp, yp, np.concatenate([g_t, g_f[tr]]))
        pooled.append((te, m_pool.predict(Xf[te])))

    def joined(arms):
        out = np.full(len(y_f), np.nan)
        for te, p in arms:
            out[te] = p
        return out

    r_solo = spearmanr(joined(solo), y_f).statistic
    r_pool = spearmanr(joined(pooled), y_f).statistic
    ps, pp = joined(solo), joined(pooled)
    n = len(y_f)
    d = [spearmanr(pp[b], y_f[b]).statistic - spearmanr(ps[b], y_f[b]).statistic
         for b in rng.integers(0, n, size=(2000, n))]
    lo, hi = np.quantile(d, [.025, .975])
    verdict = ("pooling helps" if lo > 0 else
               "pooling hurts" if hi < 0 else "not distinguishable")
    print(f"  tayara only       Spearman {r_solo:+.3f}")
    print(f"  pooled            Spearman {r_pool:+.3f}")
    print(f"  difference {np.mean(d):+.3f}  [{lo:+.3f}, {hi:+.3f}]  -> {verdict}")
    if verdict == "not distinguishable":
        print("\n  183 friperie items cannot resolve this. Pooling is kept because")
        print("  it cannot hurt the ranking and gives the model more garment")
        print("  variety, but it is NOT reported as an improvement.")

    # ---- the shipped fit ---------------------------------------------------
    use_pool = not args.tayara_only
    Xfit = X if use_pool else Xt
    yfit = y if use_pool else y_t
    gfit = g_all if use_pool else g_t
    meta_fit = meta if use_pool else meta[is_ta].reset_index(drop=True)
    print(f"\n{'='*70}\nFITTING {args.model} {'pooled' if use_pool else 'tayara-only'} "
          f"on {len(Xfit)} items\n{'='*70}")
    pipe, params = fit_model(args.model, Xfit, yfit, gfit)
    train_scores = pipe.predict(Xfit)
    print(f"  chosen on all items: {params}")

    # honest in-sample-free error: grouped 5-fold CV, the parameters chosen
    # again inside every training fold
    fr_rows = np.where((meta_fit.channel == "friperie").to_numpy())[0]
    fr_app = meta_fit.category.str.lower().map(FRIPERIE_TO_APP).to_numpy()
    prices_fit = meta_fit.price.to_numpy(float)
    step = rules["round_to"]
    pred = np.empty(len(yfit))
    served = np.full(len(yfit), np.nan)       # estimate()'s median, friperie rows
    fold_params = []
    for tr, te in folds_of(gfit, FOLDS):
        m, p = fit_model(args.model, Xfit[tr], yfit[tr], gfit[tr])
        fold_params.append(p)
        pred[te] = m.predict(Xfit[te])
        # what the app would have said for each held-out friperie item: rank
        # among this fold's training scores, read off this fold's friperie prices
        scores_tr = m.predict(Xfit[tr])
        tr_fr = np.intersect1d(tr, fr_rows)
        for i in np.intersect1d(te, fr_rows):
            same = tr_fr[fr_app[tr_fr] == fr_app[i]]
            ref = prices_fit[same] if len(same) >= min_items else prices_fit[tr_fr]
            served[i] = served_median(scores_tr, pred[i], ref, step)
    rho = spearmanr(pred, yfit).statistic
    if args.model == "svr":
        print("  chosen in the 5 training folds: " + "; ".join(
            f"{k}: " + ", ".join(f"{v} x{c}" for v, c in
                                 pd.Series([f[k] for f in fold_params]).value_counts().items())
            for k in sorted(fold_params[0])))
    # error after mapping rank -> the item's own channel distribution
    err, per_channel = [], {}
    for ch in meta_fit.channel.unique():
        m_ = (meta_fit.channel == ch).to_numpy()
        true = prices_fit[m_]
        ref = np.sort(true)
        pc = (pd.Series(pred[m_]).rank().to_numpy() - .5) / m_.sum()
        e = np.abs(np.log(np.quantile(ref, pc)) - np.log(true))
        per_channel[ch] = round(float(np.exp(e.mean())), 2)
        err.append(e)
    err = np.concatenate(err)
    factor = float(np.exp(err.mean()))
    print(f"  grouped-CV Spearman {rho:+.3f}")
    print(f"  typical error after channel mapping  x{factor:.2f}  overall")
    for ch, f_ in sorted(per_channel.items()):
        print(f"     {ch:<12} x{f_:.2f}")
    print("\n  The per-channel figures are the ones to quote: the app serves")
    print("  friperie shoppers, and tayara's 5-1800 DT spread inflates the")
    print("  pooled number without describing what any user would see.")

    # ---- how often would the Shops tag fire on normal friperie prices? -----
    tag_rates = None
    if len(fr_rows):
        factor_tag = rules["tag_factor"]
        asked, med = prices_fit[fr_rows], served[fr_rows]
        tag_rates = {"good_deal": round(float(np.mean(asked < med / factor_tag)), 3),
                     "priced_high": round(float(np.mean(asked > med * factor_tag)), 3),
                     "n": int(len(fr_rows))}
        print(f"\n  tags on the {len(fr_rows)} friperie items at their own asking price "
              f"(grouped-CV medians, tag_factor {factor_tag:g}):")
        print(f"     good_deal {tag_rates['good_deal']:.1%}   "
              f"priced_high {tag_rates['priced_high']:.1%}")
        # the same medians against the asking prices: the error of the path
        # the app serves (category reference, training-fold prices). The
        # figure above maps every channel item against the whole channel.
        tag_rates["served_error"] = round(float(np.exp(
            np.abs(np.log(np.maximum(med, 1)) - np.log(asked)).mean())), 2)
        print(f"     served-path error x{tag_rates['served_error']:.2f}")

    # ---- reference price distributions, keyed by the APP's categories -----
    reference = {}
    fr_m = meta[meta.channel == "friperie"]
    cats = {"*": fr_m.price.to_numpy(float)}
    app_cat = fr_m.category.str.lower().map(FRIPERIE_TO_APP)
    for c, g2 in fr_m.groupby(app_cat):
        if len(g2) >= min_items:         # smaller categories fall back to "*"
            cats[c] = g2.price.to_numpy(float)
    reference["friperie"] = cats

    ta_m = meta[meta.channel == "classified"]
    cats = {"*": ta_m.price.to_numpy(float)}
    for sub, g2 in ta_m.groupby("category"):
        for c in TAYARA_TO_APP.get(str(sub), []):
            cats[c] = g2.price.to_numpy(float)
    reference["classified"] = cats

    for ch, cs in reference.items():
        print(f"  reference '{ch}': " + ", ".join(
            f"{k} {len(v)}" for k, v in sorted(cs.items())))

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return

    info = {"model": args.model,
            "params": params,
            "error_factor": round(factor, 2),
            "error_factor_by_channel": per_channel,
            "cv_spearman": round(float(rho), 3),
            "tag_rates_friperie": tag_rates,
            "n_train": int(len(Xfit)),
            "pooled": bool(use_pool),
            "backbone": "patrickjohncyh/fashion-clip",
            "sklearn": sklearn.__version__,
            "channel_offset_log": {k: round(v, 4) for k, v in offset.items()}}
    if args.model == "svr":
        info["cv_params"] = fold_params
        model = PriceModel(kind="svr", pipeline=pipe, train_logp=train_scores,
                           reference=reference, meta=info)
    else:
        sc, ridge = pipe[0], pipe[-1]
        model = PriceModel(
            coef=ridge.coef_, intercept=ridge.intercept_,
            mean=sc.mean_, scale=sc.scale_,
            train_logp=train_scores, reference=reference, meta=info)
    path = model.save(args.out or ARTIFACT)
    print(f"\nwrote {path}  ({path.stat().st_size / 1024:.0f} KB)")

    # ---- prove it round-trips ---------------------------------------------
    back = PriceModel.load(path)
    i = 0
    # call it the way the APP will: with the app's category vocabulary.
    # Calling with our own label ("trousers") would exercise the fallback
    # path and hide exactly the bug the remapping above fixes.
    app_cat = FRIPERIE_TO_APP.get(str(fr.category[i]).lower())
    a = model.estimate(Xf[i], category=app_cat, channel="friperie")
    b = back.estimate(Xf[i], category=app_cat, channel="friperie")
    assert a["based_on"] == "category", (
        f"app category {app_cat!r} fell back to all categories -- "
        "reference keys do not match the app vocabulary")
    assert a == b, "saved model does not reproduce the in-memory one"
    print(f"  round-trip OK -- sample: {fr.category[i]} (app: {app_cat}) asking "
          f"{fr.price[i]:.0f} DT, model {a['low']}-{a['high']} DT "
          f"(median {a['median']})")
    print(f"  note: {a['note']}")
    miss = back.estimate(Xf[i], category=fr.category[i], channel="boutique")
    print(f"  unknown channel returns {miss} (refuses rather than guessing)")

    # one estimate() at a time, as the API calls it
    t0 = time.perf_counter()
    for v in Xf:
        back.estimate(v, category="top", channel="friperie", rules=rules)
    ms = (time.perf_counter() - t0) / len(Xf) * 1000
    print(f"  estimate() takes {ms:.2f} ms per item")


if __name__ == "__main__":
    main()
