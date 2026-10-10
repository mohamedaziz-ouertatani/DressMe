"""
Build the Phase 4 PDF report: reports/phase4/phase4_report.pdf

It sums up the full prototype: FashionCLIP embeddings, the EfficientNet
classifier, the compatibility formula, the FastAPI + MongoDB backend and the
React frontend, then what was built on top of them: shop and friperie listings,
five AI chat agents, the local chat model and the explainability (XAI) layer.
Numbers come from the evaluation reports and files in reports/ and mappings/
(no data/ needed), so it runs on any checkout.

Run:   python src/phase4/build_phase4_report.py
"""

import csv
import json
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import CondPageBreak, PageBreak, Paragraph, SimpleDocTemplate, Spacer

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
# same styles and helpers as the Phase 3 report, so both look alike
from build_phase3_report import (BODY, H1, H2, H3, ROOT, WIDTH, bullets, fig,
                                 inline_code, p, table)
from plot_style import DARK, GOLD, RUST

OUT = ROOT / "reports" / "phase4" / "phase4_report.pdf"
REPORTS = ROOT / "reports" / "phase4"
FIG = REPORTS / "figures"
FIG4 = FIG / "summary"
MAPPINGS = ROOT / "mappings"
MODEL_NAMES = {"qwen3:4b-instruct": "qwen3:4b-instruct (base)", "dressme-chat": "dressme-chat (v1)",
               "dressme-chat-v2": "dressme-chat-v2", "dressme-chat-v3": "dressme-chat-v3",
               "dressme-chat-v4": "dressme-chat-v4"}

SECTIONS = ["context", "architecture", "embeddings", "classifier", "compatibility",
            "backend", "listings", "agents", "chat", "xai", "frontend", "testing", "local",
            "decisions", "limits", "next"]


def sec(key):
    return SECTIONS.index(key) + 1


def h1(key, title):
    # new page if fewer than 5 cm are left, so a section never starts at the bottom
    return [CondPageBreak(5 * cm), Paragraph(f"{sec(key)}. {title}", H1)]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, "DressMe · Phase 4 — Full prototype")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def count_tests():
    """Backend tests: (fast tests with fakes, tests that need the real models)."""
    files = list((ROOT / "backend" / "tests").glob("test_*.py"))
    n = {f.name: f.read_text(encoding="utf-8").count("\ndef test_") for f in files}
    slow = n.pop("test_real_models.py", 0)
    return sum(n.values()), slow


def read_settings():
    with open(MAPPINGS / "compatibility_weights.csv", encoding="utf-8", newline="") as f:
        return {r["name"]: r for r in csv.DictReader(f)}


def read_chat_eval():
    """Results of src/phase4/evaluate_chat.py ({} if it has not been run)."""
    path = REPORTS / "chat_evaluation.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# ------------------------------------------------------------------ charts
def save(fig_, name):
    path = FIG4 / name
    fig_.tight_layout()
    fig_.savefig(path, dpi=200)
    plt.close(fig_)
    return path


def chart_models(choice):
    """EfficientNet vs FashionCLIP probe, test accuracy per field."""
    fields = list(choice)
    eff = [choice[f]["efficientnet"] * 100 for f in fields]
    probe = [choice[f]["fashionclip_probe"] * 100 for f in fields]
    x = range(len(fields))
    fig_, ax = plt.subplots(figsize=(6.5, 3))
    ax.bar([i - 0.2 for i in x], probe, 0.4, label="FashionCLIP linear probe", color=GOLD)
    ax.bar([i + 0.2 for i in x], eff, 0.4, label="EfficientNet-B0", color=RUST)
    for i in x:
        ax.text(i - 0.2, probe[i] + 1, f"{probe[i]:.1f}", ha="center", fontsize=8)
        ax.text(i + 0.2, eff[i] + 1, f"{eff[i]:.1f}", ha="center", fontsize=8)
    ax.set_xticks(list(x), [f"{f}\n({choice[f]['test_items']:,} test items)" for f in fields])
    ax.set_ylabel("test accuracy (%)")
    ax.set_ylim(50, 105)
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    ax.set_title("Classifier vs embedding baseline")
    return save(fig_, "classifier_vs_probe.png")


def chart_training(log):
    fig_, ax = plt.subplots(figsize=(6.5, 2.8))
    for col, label, c in [("val_category", "category", RUST),
                          ("val_sub_category", "sub_category", GOLD),
                          ("val_pattern", "pattern", DARK)]:
        ax.plot(log["epoch"], log[col] * 100, marker="o", label=label, color=c)
    ax.set_xlabel("epoch")
    ax.set_ylabel("val accuracy (%)")
    ax.set_xticks(log["epoch"])
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("EfficientNet-B0 training (validation split)")
    return save(fig_, "classifier_training.png")


def chart_compatibility():
    """AUC per part, from reports/phase4/compatibility_evaluation.md."""
    rows = {"team weights": (66.6, 78.7), "style alone": (72.9, 84.6),
            "colour alone": (52.0, 51.2), "pattern alone": (50.3, 50.0),
            "structure alone": (50.0, 50.0)}
    names = list(rows)
    x = range(len(names))
    fig_, ax = plt.subplots(figsize=(6.5, 3))
    ax.bar([i - 0.2 for i in x], [rows[n][0] for n in names], 0.4, label="PolyVore", color=GOLD)
    ax.bar([i + 0.2 for i in x], [rows[n][1] for n in names], 0.4, label="Fashionpedia",
           color=RUST)
    ax.axhline(50, color="grey", lw=0.8, ls="--")
    ax.text(len(names) - 0.5, 51, "chance", fontsize=7, color="grey", ha="right")
    ax.set_xticks(list(x), names, fontsize=8)
    ax.set_ylabel("swap-test AUC (%)")
    ax.set_ylim(40, 90)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Compatibility: which part carries the signal")
    return save(fig_, "compatibility_auc.png")


def chart_chat(chat_eval):
    """The chat models on the same test decisions (reports/phase4/chat_evaluation.json)."""
    metrics = [("tool_decision", "tool\ndecision"), ("tool_name", "tool\nname"),
               ("arguments", "arguments"), ("language", "language"), ("route", "router")]
    models = list(chat_eval)
    palette = [GOLD, DARK, RUST]
    width = 0.8 / len(models)
    fig_, ax = plt.subplots(figsize=(6.5, 3))
    for k, m in enumerate(models):
        values = [chat_eval[m]["summary"].get(key) or 0 for key, _ in metrics]
        xs = [i + (k - (len(models) - 1) / 2) * width for i in range(len(metrics))]
        ax.bar(xs, values, width, label=MODEL_NAMES.get(m, m), color=palette[k % len(palette)])
    ax.set_xticks(range(len(metrics)), [label for _, label in metrics], fontsize=8)
    ax.set_ylabel("test accuracy (%)")
    ax.set_ylim(0, 105)
    ax.legend(frameon=False, fontsize=7, ncol=len(models), loc="lower center",
              bbox_to_anchor=(0.5, 1.0))
    ax.set_title("Chat models on the same test conversations", pad=22)
    return save(fig_, "chat_models.png")


def chart_unsure():
    """Accuracy of the answers shown as sure vs 'not sure, check'
    (reports/phase4/explanations_evaluation.md, 29,633 test pictures)."""
    rows = {"category": (96.9, 49.6), "sub_category": (88.9, 35.5), "pattern": (91.1, 45.9)}
    names = list(rows)
    x = range(len(names))
    fig_, ax = plt.subplots(figsize=(6.5, 2.8))
    ax.bar([i - 0.2 for i in x], [rows[n][0] for n in names], 0.4, label="shown as sure",
           color=DARK)
    ax.bar([i + 0.2 for i in x], [rows[n][1] for n in names], 0.4,
           label="flagged \"not sure, check\"", color=RUST)
    for i, n in enumerate(names):
        ax.text(i - 0.2, rows[n][0] + 1.5, f"{rows[n][0]:.0f}", ha="center", fontsize=8)
        ax.text(i + 0.2, rows[n][1] + 1.5, f"{rows[n][1]:.0f}", ha="center", fontsize=8)
    ax.set_xticks(list(x), names)
    ax.set_ylabel("accuracy (%)")
    ax.set_ylim(0, 110)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title("Is the \"not sure\" flag honest?", pad=22)
    return save(fig_, "unsure_flag.png")


# ------------------------------------------------------------------ report
def build():
    FIG4.mkdir(parents=True, exist_ok=True)
    choice = json.loads((REPORTS / "classifier_choice.json").read_text())
    log = pd.read_csv(REPORTS / "classifier_training_log.csv")
    settings = read_settings()
    w = {k: float(settings[f"weight_{k}"]["value"])
         for k in ["style", "colour", "pattern", "structure"]}
    pct = {f: choice[f]["efficientnet"] * 100 for f in choice}
    probe = {f: choice[f]["fashionclip_probe"] * 100 for f in choice}
    train_min = log["minutes"].sum()
    n_fast, n_slow = count_tests()
    chat_eval = read_chat_eval()
    # the app's model: the newest fine-tuned one in the evaluation
    served = next((m for m in ("dressme-chat-v4", "dressme-chat-v3", "dressme-chat-v2")
                   if m in chat_eval), None)
    v2 = chat_eval[served]["summary"] if served else None
    base = chat_eval.get("qwen3:4b-instruct", {}).get("summary")

    story = []

    # --- cover / summary
    story += [Spacer(1, 3 * cm),
              Paragraph("DressMe", ParagraphStyle("T", parent=H1, fontSize=30, leading=36)),
              Paragraph("Phase 4 — Full prototype", ParagraphStyle("S", parent=H2, fontSize=15)),
              Spacer(1, 0.4 * cm),
              p("AI personal fashion assistant · ESPRIT, Advanced Data Science project "
                f"(team of 6) · Report generated {date.today().isoformat()}"),
              Spacer(1, 1.2 * cm),
              Paragraph("Executive summary", H2)]
    chat_line = "."
    if v2 and base:
        chat_line = (f". On the test chats it picks the right tool {v2['tool_name']}% of the time "
                     f"with the right arguments {v2['arguments']}% (base model: "
                     f"{base['tool_name']}% / {base['arguments']}%).")
    story += bullets([
        "Phase 4 turns the Phase 3 dataset (<i>dressme.csv</i>, 3 public sources, unified "
        "schema) into a working app, built as <b>five sub-projects</b>: FashionCLIP embeddings, "
        "an EfficientNet classifier, a compatibility formula, a FastAPI + MongoDB backend and a "
        "React frontend. All five are done, and four layers were built on top of them: "
        "listings, AI agents, a local chat model and explainability.",
        "<b>FashionCLIP</b> gives a 512-number vector for 282,135 pictures / crops. A linear "
        f"probe on these vectors reaches {probe['category']:.1f}% category and "
        f"{probe['sub_category']:.1f}% sub_category: the bar the classifier had to beat.",
        f"<b>EfficientNet-B0</b> (three heads) beats it on every field: category "
        f"<b>{pct['category']:.1f}%</b>, sub_category <b>{pct['sub_category']:.1f}%</b>, "
        f"pattern <b>{pct['pattern']:.1f}%</b> on the test split. The app uses it for all three.",
        "The <b>compatibility formula</b> (style + colour + pattern + structure, weights set by "
        "the team) scores outfits 0-100 with reasons. Swap-test AUC: 66.6% PolyVore, 78.7% "
        "Fashionpedia. Style carries almost all the measurable signal.",
        "<b>Listings:</b> clothes for sale now, from two Tunisian shops read politely (Exist, "
        "Hamadi Abid), a frozen snapshot of the Inditex shops (which block automated access) "
        "and friperie sellers who post in the app after an admin approves them.",
        "<b>Five AI agents</b> answer in the chat, each with its own prompt and tools on the "
        "user's real data: Stylist, Shopping advisor, Wardrobe analyst, Seller assistant and "
        "Explainer. A router picks one per message.",
        "<b>Local chat model:</b> Qwen3-4B fine-tuned with QLoRA on synthetic chats in French, "
        "English and Tunisian Darija runs offline with no daily quota" + chat_line,
        "<b>Explainability (XAI):</b> every label, outfit score and buy verdict can say why "
        "(heatmaps, confidence and a \"not sure, check\" flag, points per part, the weakest "
        "piece and its best swap). Sub-projects 1-2 of 4 are done, 3 (similarity + chat traces) "
        "is in progress.",
        "<b>Real-life features:</b> background removal on every upload, today's weather to "
        "choose the season, beach outfits, an Insights page, and a virtual try-on through "
        "hosted models with a 2D fallback.",
        f"<b>Quality:</b> {n_fast} backend tests with fakes, plus {n_slow} real-model tests; "
        "a browser walkthrough of every screen before the jury demo (<i>DEMO.md</i>).",
    ])
    story.append(PageBreak())

    # --- 1. context
    story += h1("context", "Context and goals")
    story += [p("Target users are young Tunisians on a limited budget who buy mostly "
                "second-hand (friperie): items are often unlabelled and can rarely be returned, "
                "so every purchase is a small gamble. The Phase 1 survey (57 responses) set the "
                "priorities: 42% want \"should I buy this?\" advice, 56% shop second-hand, black "
                "dominates 84% of wardrobes."),
              Spacer(1, 4),
              p("Phase 4 goal: a full prototype that (1) digitises a wardrobe from photos, "
                "(2) answers buy / think / skip from one photo in the shop, (3) suggests and "
                "scores outfits filtered by modesty, season and occasion, (4) finds look-alikes "
                "and pieces for sale, (5) offers a chat assistant that only talks about clothes "
                "the user owns, and (6) can explain each of its answers."),
              Spacer(1, 6),
              table([["Sub-project", "Output", "Status"],
                     ["4.1 Embeddings", "FashionCLIP vectors + similarity index", "done"],
                     ["4.2 Classifier", "EfficientNet-B0: category, sub_category, pattern",
                      "done"],
                     ["4.3 Compatibility", "weighted formula, 0-100 score with reasons", "done"],
                     ["4.4 Backend", "FastAPI + MongoDB, weather, virtual try-on", "done"],
                     ["4.5 Frontend", "React + Tailwind app and admin dashboard", "done"],
                     ["Listings", "Tunisian shops, frozen snapshot, friperie sellers", "done"],
                     ["AI agents", "five chat agents with tools + a router", "done"],
                     ["Local chat model", "Qwen3-4B + QLoRA, served by Ollama (v4)", "done"],
                     ["XAI 1-2", "item labels; outfit scores and buy verdicts", "done"],
                     ["XAI 3-4", "similarity + chat traces; XAI report, Admin > Explainability", "done"]],
                    widths=[3.5 * cm, WIDTH - 5.5 * cm, 2 * cm])]

    # --- 2. architecture
    story += h1("architecture", "Architecture")
    story += [inline_code("""
  React app (frontend/)  --/api-->  FastAPI (backend/app)  ----->  MongoDB
                                         |              users, items, candidates, chat,
                                         |              listings, events, feedback
            upload: EXIF rotation -> app/background.py (rembg U2-Net + cloth-seg) -> on white
                                         |
                    app/ml.py  Analyzer: EfficientNet + colour model + FashionCLIP
                               Catalog:  SimilarityIndex (PolyVore, Fashion Product, H&M)
                                         |
                    src/phase4/compatibility.py + explain*.py  (rules in mappings/*.csv)
                                         |
       /chat: router -> one of 5 agents -> tools on the user's data
              engine: Gemini API  or  Ollama (local dressme-chat-v4)
                                         |
       collect_listings.py (nightly, separate process): connectors -> analysed listings
       Open-Meteo (weather)    Hugging Face Spaces (virtual try-on)
"""),
              p("Models train on the local GPU (RTX 2050, 4 GB), except the chat model "
                "(free Kaggle T4). The backend reuses the <i>src/</i> code directly, so the "
                "evaluated models are exactly those the app runs. Team-set rules (weights, colour "
                "harmony, pattern mixing, outfit structure, weather seasons, XAI cuts, resale "
                "prices, router keywords) live in CSV files, never in code.")]

    # --- 3. embeddings
    story += h1("embeddings", "FashionCLIP embeddings")
    story += bullets([
        "<i>src/phase4/embed_fashionclip.py</i>: one 512-d unit vector (float16) per picture, i.e. "
        "per <i>image_group</i> for product shots and per item crop (≥ 32 px) for Fashionpedia. "
        "282,135 vectors; resumable, one shard per dataset.",
        "<i>src/phase4/similarity.py</i> (<i>SimilarityIndex</i>): nearest-neighbour search, reused by "
        "the API for look-alikes, the H&amp;M shop and the listings.",
        "<i>src/phase4/evaluate_embeddings.py</i> → <i>reports/phase4/embeddings_evaluation.md</i>.",
    ])
    story += [Paragraph("Results on the 29,633 test pictures", H3),
              table([["Task", "Fashion Product", "PolyVore", "Fashionpedia", "All"],
                     ["Zero-shot category", "83.6%", "80.8%", "62.2%", "72.2%"],
                     ["Zero-shot sub_category", "70.7%", "71.5%", "50.4%", "60.4%"],
                     ["Linear probe category", "96.3%", "94.8%", "80.8%", "<b>88.3%</b>"],
                     ["Linear probe sub_category", "88.1%", "93.6%", "69.1%", "<b>79.7%</b>"],
                     ["Linear probe pattern", "72.4%", "—", "74.4%", "<b>74.2%</b>"]],
                    widths=[5 * cm] + [(WIDTH - 5 * cm) / 4] * 4),
              Spacer(1, 6)]
    story += bullets([
        "<b>Colour:</b> on hand-labelled items the vectors do worse than the Phase 3 "
        "gradient-boosting model (PolyVore 63.1% vs 76.7%, Fashionpedia 42.4% vs 65.9% at "
        "the 0.7 cut), so the gradient-boosting colour model stays.",
        "<b>Street → shop retrieval:</b> for 300 Fashionpedia crops, 65% of the 5 nearest "
        "product shots share the street item's category.",
        "The probes are trained on the GPU (<i>Probe</i> class): sklearn's logistic "
        "regression was far too slow on this machine.",
    ])
    story.append(fig(FIG / "embeddings" / "street_to_shop.png",
                     caption="Street photo crops (left) and their nearest product shots.",
                     max_h=8 * cm))

    # --- 4. classifier
    story += h1("classifier", "EfficientNet classifier")
    story += bullets([
        "EfficientNet-B0 with ImageNet weights and <b>three heads</b> (category, sub_category, "
        "pattern). Each picture only trains the heads it has a label for; classes are weighted "
        "1/sqrt(freq).",
        "<i>src/phase4/build_image_cache.py</i> packs every picture, letterboxed to a 224 px white "
        "square, into one file: opening 282k small files on Windows ran at ~300 img/s.",
        "<i>gpu_batch</i> decodes JPEGs and augments on the GPU (no hue change, so colours "
        f"stay true). Training: {len(log)} epochs, ~{train_min / len(log):.0f} min each "
        f"(~{train_min:.0f} min total) at ~200 img/s, resumable.",
        "<i>predict</i> keeps the sub_category inside the predicted category, and also returns "
        f"the top 3 answers per field for the explanations (section {sec('xai')}).",
    ])
    story.append(fig(chart_training(log), caption="Validation accuracy per epoch "
                     "(reports/phase4/classifier_training_log.csv); the best epoch is the last one.",
                     max_h=6 * cm))
    story.append(fig(chart_models(choice), caption="Same 29,633 test pictures for both "
                     "models. Team rule: the app uses whichever is better per field.",
                     max_h=7 * cm))
    story += [table([["Field", "Fashion Product", "PolyVore", "Fashionpedia", "All",
                      "Balanced"],
                     ["category", "98.6%", "97.7%", "93.2%", "<b>95.7%</b>", "80.9%"],
                     ["sub_category", "89.2%", "94.3%", "81.2%", "<b>86.4%</b>", "79.8%"],
                     ["pattern", "82.9%", "—", "87.1%", "<b>86.8%</b>", "77.0%"]],
                    widths=[3 * cm] + [(WIDTH - 3 * cm) / 5] * 5),
              Spacer(1, 6),
              p("The biggest gain is on Fashionpedia street photos (category 93.2% vs 80.8%, "
                "sub_category 81.2% vs 69.1%): fine-tuning learns to read crops of worn clothes. "
                "<b>Traditional</b> (3/7 right, mostly read as dress) and <b>swimwear</b> (1/5) "
                "are too small to learn, which explains the lower balanced accuracy.")]
    story.append(fig(FIG / "classifier" / "category_confusion.png",
                     caption="Category confusion matrix on the test split.", max_h=9 * cm))

    # --- 5. compatibility
    story += h1("compatibility", "Compatibility formula")
    story += [p("<i>src/phase4/compatibility.py</i>: score = weighted sum of four parts from 0 to 1, "
                "shown as 0-100 with reasons. A part that cannot be computed (e.g. no colour "
                "known) is left out and the other weights are rescaled."),
              Spacer(1, 4),
              table([["Part", "Weight", "How it is computed"],
                     ["style", f"{w['style']:.2f}", "mean FashionCLIP similarity between items, "
                      f"rescaled {settings['style_low']['value']} → 0, "
                      f"{settings['style_high']['value']} → 1"],
                     ["colour", f"{w['colour']:.2f}", "colour-group pair table "
                      "(colour_harmony.csv) + penalty above "
                      f"{settings['max_bold_colours']['value']} bold colours"],
                     ["pattern", f"{w['pattern']:.2f}", "worst clothing pattern pair "
                      "(pattern_mixing.csv); predictions under "
                      f"{settings['min_pattern_conf']['value']} confidence ignored"],
                     ["structure", f"{w['structure']:.2f}", "top + bottom or a full piece, plus "
                      "shoes, per-category limits (outfit_structure.csv) and the worst "
                      "sub_category pair, e.g. blazer + track pants (sub_category_pairing.csv)"]],
                    widths=[2.3 * cm, 1.6 * cm, WIDTH - 3.9 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "<b>Functions:</b> <i>filter_items</i> (profile: min_coverage, season, occasion; "
        "unknown fields pass), <i>suggest_outfits</i>, <i>complete_outfit</i>, <i>buy_advice</i> "
        "and <i>wardrobe_insights</i> (good outfits, most versatile and unmatched pieces, what "
        "is missing, near-twins).",
        "<b>Seasons:</b> an item without its own season gets a default one "
        "(<i>item_seasons.csv</i>: shorts in summer, coats not in summer), applied softly to "
        "tops, bottoms and shoes so an outfit is still found. <b>Beach:</b> outfits built "
        "around a swimsuit, without shoes, always as summer; swimwear is left out of "
        "everyday outfits.",
        "<b>Hard rule</b> (<i>clashes</i>): an outfit never holds the same sub_category twice "
        "(two pairs of jeans) or more items of a category than <i>outfit_structure.csv</i> "
        "allows. <i>complete_outfit</i> never proposes a clash, and scoring one answers 422.",
        f"<b>Should I buy this?</b> Counts the good outfits (score ≥ "
        f"{settings['good_outfit']['value']}) where the new item beats every owned item of its "
        f"category: ≥ {settings['buy_min_outfits']['value']} → buy, ≥ "
        f"{settings['think_min_outfits']['value']} → think, else skip. It also flags near-twins "
        f"already in the wardrobe (similarity ≥ {settings['similar_item']['value']}).",
        "<b>Weights and rules are set by the team</b>; the data only measures them. They are "
        "still marked REVIEW until the team tunes them, and admins can edit them live from "
        "the dashboard.",
    ])
    story += [Paragraph("Evaluation", H3),
              p("AUC = how often a real outfit beats the same outfit with one item swapped for "
                "a random item of the same category (50% = chance). FITB = finding the hidden "
                "item among 4 of the same category (25% = chance)."),
              Spacer(1, 4),
              table([["Weights", "PolyVore AUC", "PolyVore FITB", "Fashionpedia AUC",
                      "Fashionpedia FITB"],
                     ["<b>team weights</b>", "<b>66.6%</b>", "<b>42.6%</b>", "<b>78.7%</b>",
                      "<b>59.5%</b>"],
                     ["style alone", "72.9%", "49.7%", "84.6%", "70.0%"],
                     ["colour alone", "52.0%", "28.5%", "51.2%", "27.2%"],
                     ["pattern alone", "50.3%", "25.5%", "50.0%", "25.1%"],
                     ["structure alone", "50.0%", "25.0%", "50.0%", "25.0%"],
                     ["learned reference", "72.7%", "49.2%", "84.6%", "70.1%"]],
                    widths=[4 * cm] + [(WIDTH - 4 * cm) / 4] * 4),
              Spacer(1, 6),
              p("904 clean PolyVore test outfits and 2,710 Fashionpedia test photos. A model "
                "fitted on the data puts ~0.95 on style and ~0.05 on colour. Colour, pattern "
                "and structure add no signal in the swap test: structure cannot by design "
                "(the swap keeps the category), and real outfits are not chosen for colour rules "
                "alone. They are kept because they give the user readable reasons and enforce "
                "wearable outfits; the trade-off is a team decision.")]
    story.append(fig(chart_compatibility(), caption="Swap-test AUC per part.", max_h=7 * cm))
    story.append(fig(FIG / "compatibility" / "suggested_outfits.png",
                     caption="Outfits suggested from a mock wardrobe of 40 PolyVore test items.",
                     max_h=10 * cm))

    # --- 6. backend
    story += h1("backend", "Backend: FastAPI + MongoDB")
    story += [p("<i>backend/</i>, run with <i>uvicorn app.main:create_app --factory</i>; "
                "OpenAPI docs at <i>/docs</i>. Local MongoDB 4.0 (pymongo pinned below 4.14)."),
              Spacer(1, 4),
              table([["Endpoints", "Purpose"],
                     ["/auth/register, /auth/login, /me", "email + password (bcrypt), JWT; "
                      "profile: name, min_coverage, language"],
                     ["/items (POST, GET, PATCH, DELETE), /items/{id}/image",
                      "upload → analysed (category, sub_category, pattern, colour, vector, top-3 "
                      "answers). PATCH stores user corrections in <i>corrected</i>; the model's "
                      "guesses stay in <i>predicted</i>"],
                     ["/analyze, /buy-advice", "shop candidate (not saved, deleted after 24 h) "
                      "and its buy / think / skip verdict"],
                     ["/outfits/score, suggest, complete, explain, limits",
                      "the compatibility formula on the user's wardrobe, with points and "
                      "explanations; 422 on a clash; beach outfits"],
                     ["/similar, /catalog/{id}/image", "look-alikes in the wardrobe, the public "
                      "catalogue, the H&amp;M shop and the listings in stock"],
                     ["/insights", "what the wardrobe makes, lacks and holds twice"],
                     ["/listings, /listings/sell, /listings/mine", "browse listings, sell a "
                      "piece (admin approval first), manage one's own listings"],
                     ["/chat, /chat/history", "five agents with tools (section "
                      f"{sec('agents')}); Gemini or the local model (<i>CHAT_ENGINE</i>)"],
                     ["/items/{id}/explain, /candidates/{id}/explain", "why these labels "
                      "(heatmaps, computed on demand, never stored)"],
                     ["/weather, /tryon", "today's weather and season; a picture of the user "
                      "wearing the chosen pieces"],
                     ["/admin/*", "usage stats, model quality (how often users correct each "
                      "field), users, live editing of the formula, listing sources, moderation, "
                      "collector runs"]],
                    widths=[5.6 * cm, WIDTH - 5.6 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "<b>Clean photos before analysis</b> (<i>app/background.py</i>): every upload is "
        "turned upright with its EXIF rotation tag, shrunk to 1024 px, its background removed "
        "with rembg (U2-Net) and pasted on white, cropped around the item. When the item is "
        "worn, U2-Net cloth-seg cuts it down to the biggest garment. If the mask finds under 3% "
        "of the photo, the original is kept. ~3-5 s per photo on the CPU.",
        "<b>Weather</b> (<i>app/weather.py</i>): Open-Meteo (free, no key), cached 30 min per "
        "place. The season to dress for comes from the day's feels-like temperatures with the "
        "team's thresholds (<i>weather_seasons.csv</i>, REVIEW). Positions are rounded to ~10 km "
        "and never stored.",
        "<b>Virtual try-on</b> (<i>app/tryon.py</i>): the try-on models (CatVTON, Kolors, "
        "IDM-VTON, OOTDiffusion) need 8-16 GB of GPU, so the picture comes from Hugging Face "
        "Spaces, tried in order; one garment per call, an outfit is chained (at most 3). The "
        "person photo goes to the Space (the app says so) and nothing is stored. If no Space "
        "can dress the garments, the app falls back to a 2D overlay.",
        "<b>Privacy:</b> every query is filtered by <i>user_id</i>; another user's item "
        "answers 404. Agent tools are bound to the user, and a seller's contact never reaches "
        "the language model.",
        "<b>Honest colour:</b> a colour below 0.7 confidence is left empty (the guess is kept "
        "in <i>predicted</i>) and the UI asks the user to confirm it.",
        f"<b>Tests:</b> <i>python -m pytest</i> in <i>backend/</i> — {n_fast} fast tests "
        "with fake models, a fake background remover, fake weather and recorded shop answers on "
        f"a <i>dressme_test</i> database, plus {n_slow} real-model tests (<i>DRESSME_SLOW=1</i>).",
    ])

    # --- 7. listings
    story += h1("listings", "Listings: shops and friperie sellers")
    story += [p("\"Should I buy this?\" is more useful when the app also knows what is for sale. "
                "<i>mappings/listing_sources.csv</i> (team-owned) lists the sources; "
                "<i>src/phase4/collect_listings.py</i> runs nightly as a separate process: each "
                "enabled and approved source's connector reads the products, and every new "
                "picture is analysed like an upload. Products missing from a complete run become "
                "<i>gone</i>. Details in <i>LISTINGS.md</i>."),
              Spacer(1, 4),
              table([["Source", "How", "Status"],
                     ["Exist (exist.com.tn)", "sitemap → product pages' schema.org data, "
                      "through the polite client (robots.txt, delay, stop on 403 / 429)", "running"],
                     ["Hamadi Abid (ha.com.tn)", "its sitemap, then the JSON call its own pages "
                      "make (adult sections only)", "running"],
                     ["Zara, Bershka, Pull&amp;Bear", "Access Denied on the first page (bot "
                      "protection), again on a polite re-check on 2026-10-07: shown only as a "
                      "frozen, dated snapshot", "off"],
                     ["H&amp;M France", "every product page answers 403 (bot protection)", "off"],
                     ["Zen", "robots.txt forbids its product pages", "off"],
                     ["Friperie sellers", "photo + price + size + city + contact in the app; "
                      "pending until an admin approves it", "running"]],
                    widths=[3.8 * cm, WIDTH - 5.8 * cm, 2 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "<b>We never work around a block:</b> a refusal stops the source, saves nothing and "
        "shows on Admin > Sources. Before a source is enabled, a read-only check "
        "(<i>check_shop_source.py</i>, or the Check button) detects its kind and a team member "
        "reads its terms.",
        "Products are saved one at a time as they are read, so a stopped or blocked run keeps "
        "what it saved; only a complete good run marks products gone.",
        "<b>In the app:</b> Shops (browse, then \"Should I buy this?\" on any listing), Sell "
        "(post and manage one's listings), an \"In shops now\" row in Similar, and Admin > "
        "Listings (counts, charts, collector runs started, followed live and stopped).",
        "Labels on listings are model predictions only; prices in EUR are converted with the "
        "team's rates (<i>currency_rates.csv</i>, REVIEW).",
    ])

    # --- 8. agents
    story += h1("agents", "AI agents in the chat")
    story += [p("The chat is five agents. Each one is a system prompt (the shared rules: answer "
                "in the user's language, never invent clothes, respect the modesty level, be "
                "short) plus its own tools: Python functions bound to the current user, which "
                "the model calls and the backend runs. Every agent also has "
                "<i>list_wardrobe</i>. Details in <i>AGENTS.md</i>."),
              Spacer(1, 4),
              table([["Agent", "Helps with", "Its own tools"],
                     ["Stylist", "what to wear today or for an occasion",
                      "suggest_outfits, score_outfit, complete_outfit, get_weather"],
                     ["Shopping advisor", "should I buy this, where to find a piece",
                      "buy_advice_last_scan, search_listings, find_similar"],
                     ["Wardrobe analyst", "what is missing, unused pieces, duplicates",
                      "wardrobe_insights, wardrobe_stats, find_near_twins"],
                     ["Seller assistant", "what to sell and at what price",
                      "pieces_to_sell, price_hint, my_listings, prepare_sell"],
                     ["Explainer", "why a score, a label or a verdict",
                      "explain_outfit, what_if, explain_labels, explain_verdict, "
                      "how_scoring_works"]],
                    widths=[3.2 * cm, 5 * cm, WIDTH - 8.2 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "<b>Router</b> (<i>agents/router.py</i>): one short model call picks the agent; if it "
        "fails, the team's keyword table decides (<i>agent_keywords.csv</i>, REVIEW, Darija "
        "rows need the native review); else the Stylist. <i>ROUTER=keywords</i> skips the call "
        "to save Gemini quota.",
        "<b>Advise, never act:</b> the Seller assistant prepares a filled Sell form as a "
        "button; the user adds their contact and sends it, and an admin approves it. Prices "
        "come from look-alike listings (shop prices × the team's resale factor, REVIEW).",
        "Every answer carries its agent (a badge in the app) and the pictures of the pieces "
        "its tools returned; the Explainer can open the labels panel of a piece.",
        "<b>Engine</b> (<i>app/chat_engine.py</i>): Gemini (free key: 20 requests a day, one "
        "answer costs 2-7) or a local model with Ollama. The backend runs the tool calls (at "
        "most 6 rounds); a model that repeats the same call is asked to answer without tools, "
        "and an empty answer becomes a short message in the user's language.",
    ])

    # --- 9. local chat model
    story += h1("chat", "Local chat model")
    story += [p("With <i>CHAT_ENGINE=ollama</i> the agents run on our own machine: no key, no "
                "daily quota, and the demo works offline. The model is Qwen3-4B-Instruct, "
                "fine-tuned with QLoRA (Unsloth, rank 16, only the assistant's turns learned) on "
                "a free Kaggle T4, exported to GGUF and served by Ollama. Details in "
                "<i>LLM.md</i>."),
              Spacer(1, 4),
              table([["Step", "What"],
                     ["Dataset", "<i>build_chat_dataset.py</i>: 4,500 / 250 / 400 synthetic chats "
                      "(French 45%, Darija 35% incl. Arabizi, English 20%), each with one agent's "
                      "real prompt and tools, plus ~5% router rows. The backend's <b>real</b> tools "
                      "run on random wardrobes and listings in a scratch database, so every score, "
                      "price and explanation in the answers is real."],
                     ["What it teaches", "list the wardrobe before any tool that takes ids, check "
                      "the weather before \"what do I wear today?\", no tool for greetings or "
                      "off-topic, send a question for another agent to it in one sentence, and "
                      "say so when the user names a piece they do not own. 40% of the chats start "
                      "with earlier turns as plain text, as the app sends them: seen by the model "
                      "but not learned"],
                     ["Training", "v4: 220 min on the T4, 1 epoch"],
                     ["Darija", "<i>reports/phase4/darija_review.md</i>: every Darija word and "
                      "sentence for a native check; the agents' new phrases are not reviewed yet"]],
                    widths=[3 * cm, WIDTH - 3 * cm]),
              Spacer(1, 6)]
    if chat_eval:
        n_dec = next(iter(chat_eval.values()))["summary"]["decisions"]
        story += [p(f"Evaluation on 150 test chats ({n_dec} decisions per model: each assistant "
                    "turn is one decision, the model sees the real conversation up to that "
                    "point; the test wardrobes and a third of the phrasings were never seen in "
                    "training):"), Spacer(1, 4),
                  table([["Model", "Tool decision", "Tool name", "Arguments", "Language",
                          "Router", "s / decision"]] +
                        [[MODEL_NAMES.get(m, m), f"{r['summary']['tool_decision']}%", f"{r['summary']['tool_name']}%",
                          f"{r['summary']['arguments']}%", f"{r['summary']['language']}%",
                          f"{r['summary'].get('route')}%", f"{r['summary']['seconds']}"]
                         for m, r in chat_eval.items()],
                        widths=[3.6 * cm] + [(WIDTH - 3.6 * cm) / 6] * 6),
                  Spacer(1, 6)]
        story.append(fig(chart_chat(chat_eval), caption="Same test decisions for both models "
                         "(v4 test set). The router column rests on only 4 router decisions.",
                         max_h=7 * cm))
        story += [p("This evaluation is lenient: the model sees the <b>correct</b> conversation up to "
                    "each decision, so once the right wardrobe list is there the next tool is easy. "
                    "<i>evaluate_chat_e2e.py</i> runs <b>whole chats</b> through the app's engine and "
                    "real tools with no help (<i>reports/phase4/chat_e2e_evaluation.md</i>):"),
                  Spacer(1, 4),
                  table([["Whole chats, no help", "dressme-chat-v3", "dressme-chat-v4"],
                         ["chats with earlier turns (history)", "33 / 47", "<b>39 / 47</b>"],
                         ["chats without history", "41 / 51", "41 / 51"],
                         ["sell another piece (after a sale)", "5 / 8", "<b>8 / 8</b>"],
                         ["hand-offs to another agent", "3 / 8", "<b>5 / 8</b>"],
                         ["scoring a piece the user does not own", "<b>4 / 6</b>", "1 / 6"],
                         ["<b>all</b>", "74 / 98 (75.5%)", "<b>80 / 98 (81.6%)</b>"]],
                        widths=[7.6 * cm] + [(WIDTH - 7.6 * cm) / 2] * 2),
                  Spacer(1, 6)]
    story += bullets([
        "<b>An audit found why v1 failed:</b> it was trained on the original single assistant "
        "(4 tools) while the app now sends five agents and 20 different tools, and the chat "
        "template shipped with the base model wrote an empty "
        "<i>&lt;think&gt;&lt;/think&gt;</i> before every last answer, which the app's template "
        "never does. v1 learned it, began its answers with stray tags and called tools for "
        "\"thank you\". Both are fixed since v2.",
        "<b>v3</b> added the Explainer's look-alike tool (v2 made up a reason in a live chat), the "
        "app's own words in search (v2 wrote <i>slacks</i>, <i>violet</i>) and what to do with a "
        "piece the user does not own. <b>v4</b> (the app's model, team rule: the better one) fixes "
        "a failure found in a real chat: the app sends earlier turns as plain text, without the "
        "tool calls behind them, and v2 / v3, trained only on chats whose earlier turns kept "
        "their tool calls, then answered from that text (\"I can't find a blue jacket\" the "
        "wardrobe holds). v4's data has such history, shown to the model but hidden from the "
        "loss (<i>finetune_chat.mask_history</i>).",
        "<b>Still weak in v4:</b> scoring a piece the user does not own (1 / 6: it scores another "
        "piece instead, a regression from v3's 4 / 6), and hand-offs (5 / 8). The test chats come "
        "from the same generator as the training data: they measure tool use and language, not "
        "how natural the answers sound with real users.",
        "<b>Speed</b> on the RTX 2050 with the backend's models loaded: ~21 tokens/s, "
        "11-18 s per answer that uses tools (Ollama puts 58% of the model on the GPU), plus "
        "~3 s for the router's call.",
        "When a tool or an agent's job changes, the dataset is rebuilt and the model retrained: "
        "it only knows the tools as they were when it was trained.",
    ])

    # --- 10. XAI (the details are in the XAI report: src/phase4/build_xai_report.py)
    story += h1("xai", "Explainability (XAI)")
    story += [p("Users act on the app's answers with their own money, so every answer can say "
                "why. The explanations only show how an answer was made; they never change it. "
                "Built as four sub-projects (specs and plans in <i>docs/superpowers/</i>); the "
                "methods, the faithfulness tests, screenshots, limitations and open team decisions "
                "are in the separate <b>XAI report</b> (<i>reports/phase4/xai_report.pdf</i>)."),
              Spacer(1, 4),
              table([["Sub-project", "What the user sees", "Status"],
                     ["1. Item labels", "\"Why these labels?\": where the model looked (Grad-CAM), "
                      "the colour's pixels, the top 3 answers and a \"not sure, check\" badge", "done"],
                     ["2. Outfits and verdicts", "points per part that add up to the score, what "
                      "works and what does not, the weakest piece and its best swap; the path "
                      "to a buy / think / skip verdict", "done"],
                     ["Explainer agent", "the same explanations in the chat, plus \"what if I "
                      "wear X instead?\" and \"why are these two alike?\"", "done"],
                     ["3. Similarity + chat", "why two pieces look alike (shared labels, "
                      "concepts); \"How I answered\" under each chat answer", "done"],
                     ["4. XAI report + admin", "the jury report and Admin > Explainability "
                      "(evaluations, real-use flag, chat tool calls, XAI settings)", "done"]],
                    widths=[3.6 * cm, WIDTH - 5.6 * cm, 2 * cm]),
              Spacer(1, 6)]
    story.append(fig(chart_unsure(), caption="Test split, 29,633 pictures. Answers flagged "
                     "\"not sure\" are right about half the time or less, so the flag points "
                     "the user at the labels worth checking. More results in the XAI report.",
                     max_h=6 * cm))

    # --- 11. frontend
    story += h1("frontend", "Frontend: React + Tailwind")
    story += [p("<i>frontend/</i>: React 19, Vite, TypeScript, Tailwind 4, talking to the API "
                "through the <i>/api</i> dev proxy."),
              Spacer(1, 4),
              table([["Screen", "What the user does"],
                     ["Today", "outfit of the day for today's weather (or a chosen season and "
                      "occasion, incl. Beach), with \"Why this score?\""],
                     ["Scan", "photo in the friperie → analysis + buy / think / skip, \"Why this "
                      "verdict?\", try it on"],
                     ["Wardrobe, Insights", "add items by photo, confirm or correct the labels "
                      "(\"Why these labels?\"); what the wardrobe makes and lacks"],
                     ["Build", "pick pieces, get a 0-100 score with its points, apply the best "
                      "swap, let the app complete the outfit, try it on"],
                     ["Similar", "\"you already own something like this\", H&amp;M and listings "
                      "look-alikes"],
                     ["Shops, Sell", "listings in stock with their verdict; post and manage "
                      "one's own friperie listings"],
                     ["Chat", "the five agents, with a badge, item pictures and action buttons"],
                     ["Profile", "name, modesty level (min_coverage), language"],
                     ["Admin", "stats, model quality, users, formula weights, listing sources, "
                      "moderation, collector runs"]],
                    widths=[3.2 * cm, WIDTH - 3.2 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "Three languages: English, French and Arabic (right-to-left), with plural rules; the "
        "explanation lines are built from codes and translated in the app.",
        "Design rules in <i>DESIGN.md</i>, product brief in <i>PRODUCT.md</i>.",
    ])

    # --- 12. testing
    story += h1("testing", "Testing and demo readiness")
    story += [p("Before the jury demo the whole app was run as a user would meet it: the real "
                "API, MongoDB and the React app in Chromium, at phone and desktop widths, with "
                "the test fakes standing in for the models and Gemini. The walkthrough, the chat "
                "audit and the work that followed found and fixed these bugs:"),
              Spacer(1, 4),
              table([["Found", "Fix"],
                     ["Build page showed the score panel twice on phones",
                      "the desktop side panel is hidden below the desktop width"],
                     ["Phone portrait photos were analysed lying on their side (EXIF rotation "
                      "ignored)", "uploads apply the rotation tag; a test fails without the fix"],
                     ["<i>merge_and_split.py</i> crashed on pandas 3 (allowed by "
                      "<i>requirements.txt</i>)", "one column type fixed; output byte-identical "
                      "to pandas 2"],
                     ["The local chat engine stopped a normal plan (list tops, list bottoms, "
                      "score) before scoring, and replaced an empty answer with a made-up "
                      "English sentence", "only a repeated identical call stops it; an empty "
                      "answer becomes a short message in the user's language"],
                     ["The chat model v1 began answers with stray tags (training template)",
                      "the empty think block is removed from the training texts (v2)"]],
                    widths=[7.5 * cm, WIDTH - 7.5 * cm]),
              Spacer(1, 6),
              p("<i>DEMO.md</i> holds the jury demo script: what to prepare the day before and "
                "30 minutes before, the run order with talking points, and fallbacks. With the "
                "local chat model everything runs offline except the weather and the virtual "
                "try-on, which both have fallbacks (calendar season, 2D overlay). The real models "
                "still need a dry run on the demo laptop.")]

    # --- 13. local photos
    story += h1("local", "Local test photos")
    story += [p("Our own phone photos (wardrobe and friperie) are the only data from the real "
                "DressMe setting, and the only way to measure traditional wear and swimwear. "
                "They are the <b>test set only</b>. The pipeline is ready; collection starts "
                "after the demo (targets: 500–1,000 wardrobe items, 150–300 friperie items, "
                "50–100 traditional garments).")]
    story += bullets([
        "<i>LOCAL_PHOTOS.md</i>: consent and privacy (anonymous contributor ids, no faces, "
        "shop owner's permission), how to shoot (one whole item per photo, plain surface, "
        "JPEG), and how to fill each label column.",
        "<i>src/phase3/map_local.py --init</i> lists new photos in <i>labels.csv</i>; the default run "
        "checks every label against <i>mappings/</i> and stops with the line number, then writes "
        "<i>local.csv</i> (ids <i>lc_</i>).",
        "<i>merge_and_split.py</i> adds them to <i>dressme.csv</i> with <i>split</i> and "
        "<i>outfit_split</i> forced to test; their colours count as real labels.",
        "Still to do once photos exist: include <i>local</i> in the image cache, the embeddings "
        "and the evaluation scripts.",
    ])

    # --- 14. decisions
    story += h1("decisions", "Key decisions")
    story += [table([["Decision", "Why"],
                     ["EfficientNet for category, sub_category and pattern",
                      "team rule \"whichever is better\": it won all three fields"],
                     ["Keep the gradient-boosting colour model",
                      "FashionCLIP vectors are worse on the hand labels"],
                     ["Colour empty below 0.7 confidence", "a wrong colour hurts more than none; "
                      "the user confirms it"],
                     ["Team-set compatibility weights", "the data measures them but does not "
                      "set them; style-only would lose readable reasons"],
                     ["One packed image cache", "small-file reads were the training bottleneck"],
                     ["H&amp;M catalogue, then polite Tunisian shops, instead of scraping",
                      "the Inditex and H&amp;M sites block automated access; we never try to get "
                      "around bot protection"],
                     ["Friperie listings approved by an admin", "users see only reviewed "
                      "listings; the agent prepares a sale but never posts it"],
                     ["Remove the background of uploads", "the models were trained on white "
                      "product shots; a bed, rack or person in the photo confuses them"],
                     ["No repeated sub_category / category over its limit",
                      "a hard rule, not a lower score: two pairs of jeans is never an outfit"],
                     ["Five agents instead of one assistant", "a short prompt and few tools per "
                      "agent: easier for a small local model, and each can be tested alone"],
                     ["Local chat model, fine-tuned on synthetic chats", "no daily quota, works "
                      "offline; the real tools write the answers, so the model learns our scores "
                      "and never invents clothes. Team rule: the better model is used (v4)"],
                     ["Explanations only show how an answer was made", "they reuse the same "
                      "code as the answer, so they cannot disagree with it"],
                     ["Local photos for test only", "the one honest measure of the real "
                      "setting; never trained on"],
                     ["Predictions are never labels", "<i>predicted_attributes.csv</i> and the "
                      "<i>predicted</i> field stay separate from ground truth / user input"]],
                    widths=[6 * cm, WIDTH - 6 * cm])]

    # --- 15. limits
    story += h1("limits", "Limits and risks")
    story += bullets([
        "Traditional (jebba, kaftan) and swimwear are too rare in the public data to learn; "
        "traditional is read as dress. Local photos are needed.",
        "Street photos remain harder than product shots (category 93% vs 98%).",
        "Colour, pattern and structure add no measurable signal in the swap test; the team "
        "weights cost ~6 AUC points against style alone. The weakest-piece explanation is "
        "limited by the same signal.",
        "PolyVore has no pattern labels, so its patterns are predictions.",
        "Background removal costs ~3-5 s per photo on the CPU; cloth-seg often misses items "
        "lying flat, so it is only used on worn items. Only the cleaned photo is kept.",
        "The models have not been measured on real phone photos yet (local test set pending).",
        "Listings depend on shops that may change or block us: only two Tunisian shops run, "
        "the Inditex rows are a frozen snapshot, and the H&amp;M catalogue has no prices.",
        "Virtual try-on depends on free Hugging Face Spaces that can be down or busy (the "
        "default one was broken on 2026-10-04); the 2D overlay is the fallback.",
        "The chat model is tested on synthetic chats from the same generator as its training "
        "data; real users will phrase things differently. It is slow on the 4 GB GPU "
        "(11-18 s per answer). The Darija it learned is only partly reviewed by a native "
        "speaker.",
        "Many team rules are still marked REVIEW (weights, XAI cuts, resale factors, router "
        "keywords, weather thresholds, currency rates).",
        "Datasets are for non-commercial academic use only and are never redistributed.",
    ])

    # --- 16. next
    story += h1("next", "Next steps")
    story += bullets([
        "Retrain the local chat model with the newest Explainer tools (explain_similarity), "
        "and calibrate the \"not sure\" cuts on real uploads (Admin > Explainability).",
        "Native-speaker review of the Darija (<i>darija_review.md</i>, section 7 is new), then "
        "rebuild the chat dataset and retrain once, together with the Shopping advisor's weak "
        "spots.",
        "Try the chat with real users' own phrasing, beyond the synthetic test.",
        "Dry run on the demo laptop with the real models, background removal, the local chat "
        "model and the try-on Spaces (<i>DEMO.md</i>).",
        "Collect and label local photos (<i>LOCAL_PHOTOS.md</i>), then evaluate the classifier, "
        "colour model and background removal on them.",
        "Team session to tune the compatibility weights and close the REVIEW rows.",
        "User test with the personas; use the admin \"model quality\" page (correction rates) "
        "to see where the models fail in real use.",
    ])

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="DressMe — Phase 4 report", author="DressMe team")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    build()
