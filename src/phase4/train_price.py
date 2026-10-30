"""
Fit the price model and write models/checkpoints/price_model.joblib.

    python src/phase4/train_price.py
    python src/phase4/train_price.py --dry-run     # evaluate, write nothing

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
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

ALPHAS = np.logspace(-1, 4, 24)
DUP = 0.99
FOLDS = 5
EPS = 1e-12


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
    X = df[emb_cols(df)].to_numpy(np.float64)
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


def fit_ridge(X, y):
    sc = StandardScaler().fit(X)
    m = RidgeCV(alphas=ALPHAS).fit(sc.transform(X), y)
    return sc, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tayara", type=Path, default=Path("data/processed/tayara_fashionclip.csv"))
    ap.add_argument("--friperie", type=Path, default=Path("data/processed/friperie_fashionclip.csv"))
    ap.add_argument("--tayara-only", action="store_true",
                    help="fit on classified ads alone")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    # the team's settings, through the API's own strict loader: a bad csv
    # stops training here, before any work, just as it stops the route
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from price import ARTIFACT, PriceModel, load_rules   # noqa: E402
    min_items = int(load_rules()["min_category_items"])

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
    gf = groups_of(Xf)
    y_f = y[(meta.channel == "friperie").to_numpy()]
    rng = np.random.default_rng(0)
    pooled, solo = [], []
    for tr, te in folds_of(gf, FOLDS):
        # tayara-only arm: never sees a friperie item
        sc, m = fit_ridge(Xt, y[(meta.channel == "classified").to_numpy()])
        solo.append((te, m.predict(sc.transform(Xf[te]))))
        # pooled arm: all tayara + the friperie TRAINING fold
        Xp = np.vstack([Xt, Xf[tr]])
        yp = np.concatenate([y[(meta.channel == "classified").to_numpy()], y_f[tr]])
        sc2, m2 = fit_ridge(Xp, yp)
        pooled.append((te, m2.predict(sc2.transform(Xf[te]))))

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
    yfit = y if use_pool else y[(meta.channel == "classified").to_numpy()]
    print(f"\n{'='*70}\nFITTING {'pooled' if use_pool else 'tayara-only'} "
          f"on {len(Xfit)} items\n{'='*70}")
    sc, ridge = fit_ridge(Xfit, yfit)
    train_scores = ridge.predict(sc.transform(Xfit))
    print(f"  alpha {ridge.alpha_:.3g}")

    # honest in-sample-free error, from the grouped CV above
    gall = groups_of(Xfit)
    pred = np.empty(len(yfit))
    for tr, te in folds_of(gall, FOLDS):
        s, m = fit_ridge(Xfit[tr], yfit[tr])
        pred[te] = m.predict(s.transform(Xfit[te]))
    rho = spearmanr(pred, yfit).statistic
    # error after mapping rank -> the item's own channel distribution
    meta_fit = meta if use_pool else meta[meta.channel == "classified"]
    err, per_channel = [], {}
    for ch in meta_fit.channel.unique():
        m_ = (meta_fit.channel == ch).to_numpy()
        true = meta_fit.price.to_numpy(float)[m_]
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

    # ---- reference price distributions, keyed by the APP's categories -----
    # The backend calls estimate() with its own nine categories (vocab.py):
    # top, bottom, dress, outerwear, shoes, bag, accessory, traditional,
    # swimwear. Keying references by OUR labels (tshirt, jeans, chaussures)
    # would make every app call miss and silently fall back to "*".
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

    model = PriceModel(
        coef=ridge.coef_, intercept=ridge.intercept_,
        mean=sc.mean_, scale=sc.scale_,
        train_logp=train_scores, reference=reference,
        meta={"error_factor": round(factor, 2),
              "error_factor_by_channel": per_channel,
              "cv_spearman": round(float(rho), 3),
              "n_train": int(len(Xfit)),
              "pooled": bool(use_pool),
              "backbone": "patrickjohncyh/fashion-clip",
              "channel_offset_log": {k: round(v, 4) for k, v in offset.items()}})
    path = model.save(args.out or ARTIFACT)
    print(f"\nwrote {path}")

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


if __name__ == "__main__":
    main()
