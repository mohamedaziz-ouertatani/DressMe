"""
Test-set evaluation of the EfficientNet classifier, side by side with the
FashionCLIP linear probe on exactly the same test pictures, and the choice of
which model the app uses for each field ("whichever is better", team decision
2026-10-02).

Scores: accuracy per head and per dataset (95% Wilson interval), plus
balanced accuracy (the mean of the per-class accuracies, so small classes
count as much as big ones). sub_category is scored as the app shows it:
restricted to the children of the predicted category.

Output:
    reports/phase4/classifier_evaluation.md
    reports/phase4/figures/classifier/category_confusion.png
    reports/phase4/classifier_choice.json            which model per field (read by the API)
    models/checkpoints/fashionclip_probe.pt   the probes, in case the API needs them

Run from the project root (after train_classifier.py and embed_fashionclip.py):
    python src/phase4/evaluate_classifier.py
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
import plot_style
from classifier import CATEGORIES, CHECKPOINT, HEADS, decode, load_classifier, predict_tensors
from evaluate_colour_labels import wilson
from evaluate_embeddings import NAMES, X, Probe, load_vectors, sample_per_class
from item_images import ROOT, picture_key
from train_classifier import batches, load_table

REPORT = ROOT / "reports" / "phase4" / "classifier_evaluation.md"
CHOICE = ROOT / "reports" / "phase4" / "classifier_choice.json"
PROBES = ROOT / "models" / "checkpoints" / "fashionclip_probe.pt"
FIG_DIR = ROOT / "reports" / "phase4" / "figures" / "classifier"


def acc_text(ok):
    lo, hi = wilson(ok.sum(), len(ok))
    return f"{100 * ok.mean():.1f}% ({100 * lo:.0f}–{100 * hi:.0f})"


def balanced(truth, pred):
    """Mean of the per-class accuracies (classes with at least 5 test items)."""
    t = pd.DataFrame({"t": truth, "ok": truth == pred}).groupby("t")["ok"].agg(["mean", "size"])
    return 100 * t.loc[t["size"] >= 5, "mean"].mean()


def efficientnet_predictions(test):
    model, device = load_classifier()
    answers = []
    for x, _ in batches(test, device, train=False, batch=128):   # same order as `test`
        answers += decode(predict_tensors(x, model, device))
    return pd.DataFrame(answers)


def probe_predictions(test):
    """Train one FashionCLIP probe per head (train split), predict the test pictures."""
    emb, vecs = load_vectors()
    emb["key"] = picture_key(emb)
    row_of = emb.drop_duplicates("key").set_index("key")["row"]
    has_vec = test["key"].isin(row_of.index).to_numpy()
    preds, states = {}, {}
    for head in HEADS:
        tr = emb[(emb["split"] == "train") & (emb[head] != "")]
        tr = sample_per_class(tr, head)
        probe = Probe().fit(X(vecs, tr["row"].to_numpy()), tr[head].to_numpy())
        out = np.full(len(test), "", dtype=object)
        out[has_vec] = probe.predict(X(vecs, row_of.loc[test.loc[has_vec, "key"]].to_numpy()))
        preds[head], states[head] = out, probe.state()
    PROBES.parent.mkdir(parents=True, exist_ok=True)
    torch.save(states, PROBES)
    return pd.DataFrame(preds), has_vec


def confusion_figure(truth, pred):
    m = pd.crosstab(pd.Categorical(truth, CATEGORIES), pd.Categorical(pred, CATEGORIES),
                    normalize="index", dropna=False) * 100
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.imshow(m.to_numpy(), cmap=plot_style.CMAP, vmin=0, vmax=100)
    ax.set_xticks(range(len(CATEGORIES)), CATEGORIES, rotation=45, ha="right")
    ax.set_yticks(range(len(CATEGORIES)), CATEGORIES)
    for i in range(len(CATEGORIES)):
        for j in range(len(CATEGORIES)):
            v = m.iat[i, j]
            if v >= 1:
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if v > 60 else "black")
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title("EfficientNet: category confusion on test (% of each true class)")
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "category_confusion.png", dpi=120)
    plt.close(fig)


def main():
    plot_style.apply()
    test = load_table()
    test = test[test["split"] == "test"].reset_index(drop=True)
    print(f"{len(test):,} test pictures", flush=True)
    eff = efficientnet_predictions(test)
    print("EfficientNet done", flush=True)
    clip, has_vec = probe_predictions(test)
    print("FashionCLIP probes done", flush=True)

    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    report = ["# EfficientNet classifier: evaluation\n",
              f"EfficientNet-B0 (ImageNet weights, fine-tuned), best val epoch {ck['epoch']}. "
              f"Scores on the {len(test):,} **test** pictures (duplicate copies left out). "
              "Both models are scored on exactly the same pictures: those that have a "
              f"FashionCLIP vector ({has_vec.sum():,}; Fashionpedia crops under 32 px have none). "
              "sub_category is restricted to the children of the predicted category for "
              "EfficientNet, as the app shows it.\n"]
    choice = {}
    for head in HEADS:
        m = has_vec & (test[head] != "").to_numpy()
        t = test.loc[m]
        truth = t[head].to_numpy()
        e_pred, c_pred = eff.loc[m, head].to_numpy(), clip.loc[m, head].to_numpy()
        report += [f"\n## {head}\n", "| dataset | test items | EfficientNet | FashionCLIP probe |",
                   "|---|---:|---:|---:|"]
        for ds, name in NAMES.items():
            d = (t["dataset"] == ds).to_numpy()
            if d.sum():
                report.append(f"| {name} | {d.sum():,} | {acc_text(e_pred[d] == truth[d])} | "
                              f"{acc_text(c_pred[d] == truth[d])} |")
        e_acc, c_acc = (e_pred == truth).mean(), (c_pred == truth).mean()
        report.append(f"| **all** | {len(t):,} | **{acc_text(e_pred == truth)}** | "
                      f"**{acc_text(c_pred == truth)}** |")
        report.append(f"| balanced accuracy | | {balanced(truth, e_pred):.1f}% | "
                      f"{balanced(truth, c_pred):.1f}% |")
        winner = "efficientnet" if e_acc >= c_acc else "fashionclip_probe"
        choice[head] = {"model": winner, "efficientnet": round(float(e_acc), 4),
                        "fashionclip_probe": round(float(c_acc), 4), "test_items": int(len(t))}
        report.append(f"\nUsed by the app: **{winner}**.")
        if head == "category":
            confusion_figure(truth, e_pred)
            report.append("\n![category confusion](figures/classifier/category_confusion.png)")
            small = pd.Series(truth).value_counts()
            small = small[small < 100]
            if len(small):
                report.append("\nSmall classes (too few test items to trust the percentage): "
                              + ", ".join(f"{c} {(e_pred[truth == c] == c).sum()}/{n} right"
                                          for c, n in small.items()) + ".")
        print(f"{head}: EfficientNet {100 * e_acc:.1f}%, FashionCLIP {100 * c_acc:.1f}%", flush=True)

    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Saved {REPORT} and {CHOICE}")


if __name__ == "__main__":
    main()
