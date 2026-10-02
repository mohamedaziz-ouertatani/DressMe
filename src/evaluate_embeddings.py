"""
How much do the FashionCLIP vectors already know? Four checks, all measured
on the TEST split (pictures never used for training), duplicates left out:

1. Zero-shot: compare each picture with texts such as "a photo of a dress".
   No training at all: the "free" baseline.
2. Linear probe: a logistic regression (on the GPU) trained on the vectors of the train
   split (category, sub_category, pattern). This is the score the EfficientNet
   classifier (Phase 4, sub-project 2) has to beat.
3. Colour: a logistic regression on the vectors, trained on Fashion Product's
   real colours, checked on the 395 hand-labelled PolyVore / Fashionpedia
   items and compared with the current gradient-boosting colour model
   (estimate_colours.py) at the same coverage.
4. Retrieval: for Fashionpedia street crops, the nearest product shots
   ("find it in a shop"), as a picture grid plus a category-agreement score.

Accuracies come with a 95% confidence interval (Wilson).
To keep RAM low, the probes train on at most TRAIN_PER_CLASS pictures per class.

Output:
    reports/embeddings_evaluation.md
    reports/figures/embeddings/*.png

Run from the project root (after src/embed_fashionclip.py):
    python src/evaluate_embeddings.py
"""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

import plot_style
from evaluate_colour_labels import wilson
from fashionclip import DATA, ROOT, embed_texts, load_item_image, load_model
from similarity import EMB_DIR, SimilarityIndex

REPORT = ROOT / "reports" / "embeddings_evaluation.md"
FIG_DIR = ROOT / "reports" / "figures" / "embeddings"
HAND_LABELS = DATA / "interim" / "colour_labelling" / "colour_labels.csv"
ESTIMATES = DATA / "processed" / "colour_estimates.csv"
TRAIN_PER_CLASS = 1500
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SEED = 0
NAMES = {"fashion_product": "Fashion Product", "polyvore": "PolyVore", "fashionpedia": "Fashionpedia"}
CLOTHES = {"top", "bottom", "dress", "outerwear", "traditional", "swimwear"}
METALS = ["gold", "silver"]

# texts used for zero-shot: one short description per category
CATEGORY_PROMPTS = {
    "top": "a photo of a top, t-shirt, shirt or sweater",
    "bottom": "a photo of trousers, jeans, a skirt or shorts",
    "dress": "a photo of a dress or jumpsuit",
    "outerwear": "a photo of a jacket, coat or blazer",
    "shoes": "a photo of shoes",
    "bag": "a photo of a bag",
    "accessory": "a photo of an accessory: jewellery, a watch, glasses, a hat, a belt or a scarf",
    "traditional": "a photo of a traditional kaftan or jebba",
    "swimwear": "a photo of swimwear",
}


def acc_text(ok):
    """'84.2% (83.1–85.3)' for a boolean array of right / wrong answers."""
    lo, hi = wilson(ok.sum(), len(ok))
    return f"{100 * ok.mean():.1f}% ({100 * lo:.0f}–{100 * hi:.0f})"


def per_dataset(df, ok, title):
    """Markdown table: accuracy per dataset."""
    lines = [f"\n**{title}**\n", "| dataset | test items | accuracy (95% CI) |", "|---|---:|---:|"]
    for ds, name in NAMES.items():
        m = (df["dataset"] == ds).to_numpy()
        if m.sum():
            lines.append(f"| {name} | {m.sum():,} | {acc_text(ok[m])} |")
    lines.append(f"| **all** | {len(ok):,} | {acc_text(ok)} |")
    return lines


def sample_per_class(df, col):
    """At most TRAIN_PER_CLASS rows of each class (keeps RAM and time low)."""
    # shuffle, then keep the first TRAIN_PER_CLASS rows of each class
    return df.sample(frac=1, random_state=SEED).groupby(col).head(TRAIN_PER_CLASS)


def load_vectors():
    """dressme.csv rows that have a vector, without duplicate copies."""
    ids = pd.read_csv(EMB_DIR / "fashionclip_ids.csv", dtype=str)
    vecs = np.load(EMB_DIR / "fashionclip.npy", mmap_mode="r")
    meta = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                       usecols=["id", "dataset", "category", "sub_category", "pattern",
                                "primary_colour", "colour_source", "duplicate", "split"])
    df = ids.reset_index().rename(columns={"index": "row"}).merge(meta, on="id")
    df = df[df["duplicate"] != "True"].reset_index(drop=True)
    return df, vecs


def X(vecs, rows):
    return np.asarray(vecs[np.sort(rows)], dtype=np.float32)[np.argsort(np.argsort(rows))]


# ------------------------------------------------------------------ 1. zero-shot
def zero_shot(test, Xt, model, processor, device):
    report = ["\n## 1. Zero-shot (no training)\n",
              "Each picture is given the label whose text it is most similar to."]
    cats = list(CATEGORY_PROMPTS)
    T = embed_texts(list(CATEGORY_PROMPTS.values()), model, processor, device).astype(np.float32)
    pred = np.array(cats)[(Xt @ T.T).argmax(1)]
    report += per_dataset(test, pred == test["category"].to_numpy(), "category (9 classes)")

    vocab = pd.read_csv(ROOT / "mappings" / "sub_category_vocabulary.csv")["sub_category"].tolist()
    T = embed_texts([f"a photo of a {s.replace('-', ' ')}" for s in vocab],
                    model, processor, device).astype(np.float32)
    m = (test["sub_category"] != "").to_numpy()
    pred = np.array(vocab)[(Xt[m] @ T.T).argmax(1)]
    report += per_dataset(test[m], pred == test.loc[m, "sub_category"].to_numpy(),
                          f"sub_category ({len(vocab)} classes, items that have one)")
    return report


# ---------------------------------------------------------------- 2. linear probe
class Probe:
    """Logistic regression (a linear layer + softmax) trained on the GPU.

    It does the same job as sklearn's LogisticRegression, which was far too
    slow on this machine (25 s for 3,000 vectors). The vectors are
    standardised first, and a small weight decay keeps the model simple.
    """

    def fit(self, X, y, epochs=300):
        self.classes_, y_idx = np.unique(np.asarray(y), return_inverse=True)
        self.mean, self.std = X.mean(0), X.std(0) + 1e-6
        Xt = torch.tensor((X - self.mean) / self.std, device=DEVICE)
        yt = torch.tensor(y_idx, device=DEVICE)
        torch.manual_seed(SEED)
        self.layer = torch.nn.Linear(X.shape[1], len(self.classes_)).to(DEVICE)
        opt = torch.optim.Adam(self.layer.parameters(), lr=0.01, weight_decay=1e-4)
        for _ in range(epochs):              # full batch: all pictures at once
            opt.zero_grad()
            torch.nn.functional.cross_entropy(self.layer(Xt), yt).backward()
            opt.step()
        return self

    @torch.no_grad()
    def predict_proba(self, X):
        Xt = torch.tensor((X - self.mean) / self.std, device=DEVICE)
        return torch.softmax(self.layer(Xt), 1).cpu().numpy()

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]


def probe(df, vecs, col, title):
    """Logistic regression on train vectors, accuracy on test vectors."""
    d = df[df[col] != ""]
    train = sample_per_class(d[d["split"] == "train"], col)
    test = d[d["split"] == "test"].reset_index(drop=True)
    clf = Probe()
    clf.fit(X(vecs, train["row"].to_numpy()), train[col])
    pred = clf.predict(X(vecs, test["row"].to_numpy()))
    lines = per_dataset(test, pred == test[col].to_numpy(),
                        f"{title} ({d[col].nunique()} classes, trained on {len(train):,} pictures)")
    return lines, test, pred


def worst_classes(test, pred, col, n=6):
    ok = pd.Series(pred == test[col].to_numpy()).groupby(test[col].to_numpy())
    t = pd.DataFrame({"items": ok.size(), "accuracy": ok.mean() * 100})
    t = t[t["items"] >= 20].sort_values("accuracy").head(n)
    return ["", f"Hardest {col} classes (at least 20 test items): "
            + ", ".join(f"{c} {r.accuracy:.0f}% ({int(r['items'])})" for c, r in t.iterrows()) + "."]


# ------------------------------------------------------------------- 3. colour
def colour(df, vecs):
    report = ["\n## 3. Colour from the vectors vs the current colour model\n"]
    fp = df[(df["dataset"] == "fashion_product") & (df["primary_colour"] != "")]
    train = sample_per_class(fp[fp["split"] == "train"], "primary_colour")
    clf = Probe()
    clf.fit(X(vecs, train["row"].to_numpy()), train["primary_colour"])
    classes = np.array(clf.classes_)

    def predict(rows, categories):
        p = clf.predict_proba(X(vecs, rows))
        clothes = np.isin(categories, list(CLOTHES))
        p[np.ix_(clothes, np.isin(classes, METALS))] = 0     # same metal rule as estimate_colours.py
        return classes[p.argmax(1)], p.max(1) / p.sum(1)

    fpt = fp[fp["split"] != "train"]
    pred, _ = predict(fpt["row"].to_numpy(), fpt["category"].to_numpy())
    report.append(f"On unseen Fashion Product images (val + test, real labels): "
                  f"{acc_text(pred == fpt['primary_colour'].to_numpy())} "
                  "(the gradient-boosting model: 64.5% before its confidence cut).\n")

    hand = pd.read_csv(HAND_LABELS, dtype=str, keep_default_na=False)
    hand = hand[~hand["true_colour"].isin(["", "unsure"])]
    est = pd.read_csv(ESTIMATES, dtype=str, keep_default_na=False)[["id", "predicted_colour", "colour_confidence"]]
    hand = hand.merge(est, on="id").merge(df[["id", "row"]], on="id")
    pred, conf = predict(hand["row"].to_numpy(), hand["category"].to_numpy())
    hand["clip_colour"], hand["clip_conf"] = pred, conf
    hand["gb_conf"] = hand["colour_confidence"].astype(float)

    report += ["Hand-labelled items. *Kept* = items that get a colour; the vector model keeps the "
               "same number of items as the current model (its most confident ones), so the "
               "accuracies are compared at equal coverage.\n",
               "| dataset | items | kept | current model | vector model |", "|---|---:|---:|---:|---:|"]
    for ds in ["polyvore", "fashionpedia"]:
        h = hand[hand["dataset"] == ds]
        for cut in [0.0, 0.7]:
            gb_keep = (h["gb_conf"] >= cut).to_numpy()
            n = gb_keep.sum()
            clip_keep = np.zeros(len(h), bool)
            clip_keep[np.argsort(-h["clip_conf"].to_numpy())[:n]] = True
            gb_ok = (h["predicted_colour"] == h["true_colour"]).to_numpy()[gb_keep]
            clip_ok = (h["clip_colour"] == h["true_colour"]).to_numpy()[clip_keep]
            label = "all items" if cut == 0 else f"current cut {cut}"
            report.append(f"| {NAMES[ds]} ({label}) | {len(h)} | {n} | {acc_text(gb_ok)} | "
                          f"{acc_text(clip_ok)} |")
    wrong = hand[hand["clip_colour"] != hand["true_colour"]]
    top = (wrong["true_colour"] + " → " + wrong["clip_colour"]).value_counts().head(6)
    report += ["", "Most frequent mistakes of the vector model: "
               + ", ".join(f"{k} ({v})" for k, v in top.items()) + "."]
    return report


# ---------------------------------------------------------------- 4. retrieval
def retrieval(index):
    report = ["\n## 4. Retrieval: street photo → product shots\n"]
    meta = index.meta
    side = np.minimum(pd.to_numeric(meta["bbox_w"], errors="coerce"),
                      pd.to_numeric(meta["bbox_h"], errors="coerce"))
    queries = meta[(meta["dataset"] == "fashionpedia") & (meta["split"] == "test")
                   & meta["category"].isin(["top", "bottom", "dress", "outerwear", "shoes", "bag"])
                   & (side >= 128)]
    sample = queries.sample(300, random_state=SEED)
    agree = []
    for q in sample.itertuples():
        hits = index.search(index.vector(q.id), k=5, datasets=["polyvore", "fashion_product"])
        agree.append((hits["category"] == q.category).mean())
    report.append(f"For {len(sample)} Fashionpedia test crops (clothes, shoes, bags, at least 128 px), "
                  f"**{100 * np.mean(agree):.0f}%** of the 5 nearest product shots have the same "
                  "category as the street item.\n")

    show = sample.head(8)
    fig, axes = plt.subplots(len(show), 6, figsize=(9, 1.7 * len(show)))
    for r, q in enumerate(show.itertuples()):
        hits = index.search(index.vector(q.id), k=5, datasets=["polyvore", "fashion_product"])
        items = [(q._asdict(), f"query: {q.category}")] + \
                [(h, f"{h['category']} {h['score']:.2f}") for h in hits.to_dict("records")]
        for c, (row, title) in enumerate(items):
            ax = axes[r, c]
            ax.imshow(load_item_image(row))
            ax.set_title(title, fontsize=7)
            ax.axis("off")
    fig.suptitle("Fashionpedia street crop (left) and its 5 nearest product shots", fontsize=10)
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "street_to_shop.png", dpi=110)
    plt.close(fig)
    report += ["![street to shop](figures/embeddings/street_to_shop.png)", "",
               "The category shown for a query is Fashionpedia's label; a few crops are noisy "
               "(e.g. a 'shoes' box that mostly shows the trousers above them), which lowers the score."]
    return report


def main():
    plot_style.apply()
    df, vecs = load_vectors()
    test = df[df["split"] == "test"].reset_index(drop=True)
    Xt = X(vecs, test["row"].to_numpy())
    print(f"{len(df):,} unique pictures with a vector, {len(test):,} in test")

    report = ["# FashionCLIP embeddings: evaluation\n",
              f"{len(df):,} unique pictures / crops have a vector (`patrickjohncyh/fashion-clip`, "
              f"512 numbers each). Scores are on the {len(test):,} **test** pictures."]

    model, processor, device = load_model()
    report += zero_shot(test, Xt, model, processor, device)
    del model
    print("zero-shot done")

    report += ["\n## 2. Linear probe (logistic regression on the vectors)\n",
               "The baseline the EfficientNet classifier has to beat."]
    for col, title in [("category", "category"), ("sub_category", "sub_category"),
                       ("pattern", "pattern")]:
        lines, t, pred = probe(df, vecs, col, title)
        report += lines + worst_classes(t, pred, col)
        print(f"probe {col} done")

    report += colour(df, vecs)
    print("colour done")
    report += retrieval(SimilarityIndex.load())
    print("retrieval done")

    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Saved {REPORT}")


if __name__ == "__main__":
    main()
