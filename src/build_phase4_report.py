"""
Build the Phase 4 PDF report: reports/phase4_report.pdf

It sums up the full prototype: FashionCLIP embeddings, the EfficientNet
classifier, the compatibility formula, the FastAPI + MongoDB backend and the
React frontend. Numbers come from the evaluation reports and files in
reports/ and mappings/ (no data/ needed), so it runs on any checkout.

Run:   python src/build_phase4_report.py
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

# same styles and helpers as the Phase 3 report, so both look alike
from build_phase3_report import (BODY, FIG, H1, H2, H3, ROOT, WIDTH, bullets, fig,
                                 inline_code, p, table)
from plot_style import DARK, GOLD, RUST

OUT = ROOT / "reports" / "phase4_report.pdf"
REPORTS = ROOT / "reports"
FIG4 = FIG / "phase4"
MAPPINGS = ROOT / "mappings"

SECTIONS = ["context", "architecture", "embeddings", "classifier", "compatibility",
            "backend", "frontend", "testing", "local", "decisions", "limits", "next"]


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


# ------------------------------------------------------------------ charts
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
    path = FIG4 / "classifier_vs_probe.png"
    fig_.tight_layout()
    fig_.savefig(path, dpi=200)
    plt.close(fig_)
    return path


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
    path = FIG4 / "classifier_training.png"
    fig_.tight_layout()
    fig_.savefig(path, dpi=200)
    plt.close(fig_)
    return path


def chart_compatibility():
    """AUC per part, from reports/compatibility_evaluation.md."""
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
    path = FIG4 / "compatibility_auc.png"
    fig_.tight_layout()
    fig_.savefig(path, dpi=200)
    plt.close(fig_)
    return path


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
    story += bullets([
        "Phase 4 turns the Phase 3 dataset (<i>dressme.csv</i>, 3 public sources, unified "
        "schema) into a working app, built as <b>five sub-projects</b>: FashionCLIP embeddings, "
        "an EfficientNet classifier, a compatibility formula, a FastAPI + MongoDB backend and a "
        "React frontend. All five are done.",
        "<b>FashionCLIP</b> gives a 512-number vector for 282,135 pictures / crops. A linear "
        f"probe on these vectors reaches {probe['category']:.1f}% category and "
        f"{probe['sub_category']:.1f}% sub_category: the bar the classifier had to beat.",
        f"<b>EfficientNet-B0</b> (three heads) beats it on every field: category "
        f"<b>{pct['category']:.1f}%</b>, sub_category <b>{pct['sub_category']:.1f}%</b>, "
        f"pattern <b>{pct['pattern']:.1f}%</b> on the test split. The app uses it for all three.",
        "The <b>compatibility formula</b> (style + colour + pattern + structure, weights set by "
        "the team) scores outfits 0-100 with reasons. Swap-test AUC: 66.6% PolyVore, 78.7% "
        "Fashionpedia. Style carries almost all the measurable signal.",
        "The <b>backend</b> exposes wardrobe upload with automatic analysis, \"should I buy "
        "this?\", outfit suggest / score / complete, look-alikes in the wardrobe and the H&amp;M "
        "shop catalogue, a Gemini chat assistant with function calling and an admin dashboard.",
        "The <b>frontend</b> (React 19 + Tailwind 4) covers scan, wardrobe, outfit building, "
        "look-alikes, chat and profile in English, French and Arabic (RTL).",
        "<b>Real photos:</b> uploads are turned upright (phone EXIF rotation) and their "
        "background is removed (U2-Net, plus cloth-seg when the item is worn), so they look "
        "like the white product shots the models were trained on. Outfits never repeat a "
        "sub_category or exceed a category limit.",
        f"<b>Demo readiness:</b> {n_fast} backend tests pass; a browser walkthrough of every "
        "screen and the follow-up work found and fixed three bugs before the jury demo "
        "(<i>DEMO.md</i>). The pipeline "
        "for our own test photos is ready (<i>LOCAL_PHOTOS.md</i>); collection is next.",
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
                "scores outfits filtered by modesty, season and occasion, (4) finds look-alikes, "
                "and (5) offers a chat assistant that only talks about clothes the user owns."),
              Spacer(1, 6),
              table([["Sub-project", "Output", "Status"],
                     ["4.1 Embeddings", "FashionCLIP vectors + similarity index", "done"],
                     ["4.2 Classifier", "EfficientNet-B0: category, sub_category, pattern",
                      "done"],
                     ["4.3 Compatibility", "weighted formula, 0-100 score with reasons", "done"],
                     ["4.4 Backend", "FastAPI + MongoDB + Gemini chat", "done"],
                     ["4.5 Frontend", "React + Tailwind app and admin dashboard", "done"]],
                    widths=[3.5 * cm, WIDTH - 5.5 * cm, 2 * cm])]

    # --- 2. architecture
    story += h1("architecture", "Architecture")
    story += [inline_code("""
  React app (frontend/)  --/api-->  FastAPI (backend/app)  ----->  MongoDB
                                         |                         users, items, chat, events
                                         |
            upload: EXIF rotation -> app/background.py (rembg U2-Net + cloth-seg) -> on white
                                         |
                    app/ml.py  Analyzer: EfficientNet + colour model + FashionCLIP
                               Catalog:  SimilarityIndex (PolyVore, Fashion Product, H&M)
                                         |
                    src/compatibility.py  (rules + weights in mappings/*.csv)
                                         |
                    Gemini API  (chat, function calling on the wardrobe)
"""),
              p("Models train on the local GPU (RTX 2050, 4 GB). The backend reuses the "
                "<i>src/</i> code directly, so the evaluated models are exactly those the app "
                "runs. Team-set rules (weights, colour harmony, pattern mixing, outfit "
                "structure) live in CSV files, never in code.")]

    # --- 3. embeddings
    story += h1("embeddings", "FashionCLIP embeddings")
    story += bullets([
        "<i>src/embed_fashionclip.py</i>: one 512-d unit vector (float16) per picture, i.e. "
        "per <i>image_group</i> for product shots and per item crop (≥ 32 px) for Fashionpedia. "
        "282,135 vectors; resumable, one shard per dataset.",
        "<i>src/similarity.py</i> (<i>SimilarityIndex</i>): nearest-neighbour search, reused by "
        "the API for look-alikes and for the H&amp;M shop.",
        "<i>src/evaluate_embeddings.py</i> → <i>reports/embeddings_evaluation.md</i>.",
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
        "<i>src/build_image_cache.py</i> packs every picture, letterboxed to a 224 px white "
        "square, into one file: opening 282k small files on Windows ran at ~300 img/s.",
        "<i>gpu_batch</i> decodes JPEGs and augments on the GPU (no hue change, so colours "
        f"stay true). Training: {len(log)} epochs, ~{train_min / len(log):.0f} min each "
        f"(~{train_min:.0f} min total) at ~200 img/s, resumable.",
        "<i>predict</i> keeps the sub_category inside the predicted category, as the app shows it.",
    ])
    story.append(fig(chart_training(log), caption="Validation accuracy per epoch "
                     "(reports/classifier_training_log.csv); the best epoch is the last one.",
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
    story += [p("<i>src/compatibility.py</i>: score = weighted sum of four parts from 0 to 1, "
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
                      "shoes and per-category limits (outfit_structure.csv)"]],
                    widths=[2.3 * cm, 1.6 * cm, WIDTH - 3.9 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "<b>Functions:</b> <i>filter_items</i> (profile: min_coverage, season, occasion; "
        "unknown fields pass), <i>suggest_outfits</i>, <i>complete_outfit</i> and "
        "<i>buy_advice</i>.",
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
                      "upload → analysed (category, sub_category, pattern, colour, vector). "
                      "PATCH stores user corrections in <i>corrected</i>; the model's guesses "
                      "stay in <i>predicted</i>"],
                     ["/analyze", "shop candidate, not saved to the wardrobe, deleted after 24 h"],
                     ["/buy-advice", "buy / think / skip for the last scan"],
                     ["/outfits/score, /outfits/suggest, /outfits/complete, /outfits/limits",
                      "the compatibility formula on the user's wardrobe; 422 on a clash; "
                      "category limits for the Build page"],
                     ["/similar, /catalog/{id}/image", "look-alikes in the wardrobe, the public "
                      "catalogue and the H&amp;M shop (\"buy something like this\")"],
                     ["/chat, /chat/history", "Gemini with function calling: list_wardrobe, "
                      "suggest_outfits, score_outfit, buy_advice_last_scan"],
                     ["/admin/*", "usage stats, model quality (how often users correct each "
                      "field), user management, live editing of the formula"]],
                    widths=[5.6 * cm, WIDTH - 5.6 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "<b>Clean photos before analysis</b> (<i>app/background.py</i>): every upload is "
        "turned upright with its EXIF rotation tag (phones store portrait photos sideways), "
        "shrunk to 1024 px, its background removed with rembg (U2-Net) and pasted on white, "
        "cropped around the item. When the item is worn, U2-Net keeps the whole person, so "
        "U2-Net cloth-seg cuts it down to the biggest garment. If the mask finds under 3% of "
        "the photo, the original is kept. ~3-5 s per photo on the CPU; "
        "<i>REMOVE_BACKGROUND=0</i> / <i>CLOTH_MODEL=</i> switch the steps off.",
        "<b>Privacy:</b> every query is filtered by <i>user_id</i>; another user's item "
        "answers 404.",
        "<b>Honest colour:</b> a colour below 0.7 confidence is left empty (the guess is kept "
        "in <i>predicted</i>) and the UI asks the user to confirm it.",
        "<b>H&amp;M catalogue</b> replaces scraping (team decision 2026-10-03): 63k adult "
        "articles, pictures shrunk to 320 px in a private Kaggle notebook, embedded with "
        "FashionCLIP. The Zara / Bershka / Pull&amp;Bear rows already scraped are kept only as "
        "a frozen demo.",
        f"<b>Tests:</b> <i>python -m pytest</i> in <i>backend/</i> — {n_fast} fast tests "
        "with fake models and a fake background remover on a <i>dressme_test</i> database, "
        f"plus {n_slow} real-model tests (<i>DRESSME_SLOW=1</i>).",
    ])

    # --- 7. frontend
    story += h1("frontend", "Frontend: React + Tailwind")
    story += [p("<i>frontend/</i>: React 19, Vite, TypeScript, Tailwind 4, talking to the API "
                "through the <i>/api</i> dev proxy."),
              Spacer(1, 4),
              table([["Screen", "What the user does"],
                     ["Today", "outfit of the day from their wardrobe, filtered by profile"],
                     ["Scan", "photo in the friperie → analysis + buy / think / skip, with reasons"],
                     ["Wardrobe", "add items by photo, confirm or correct the predicted labels"],
                     ["Build", "pieces grouped by category; pick items, get a 0-100 score, or "
                      "let the app complete the outfit (a clashing piece is swapped out)"],
                     ["Similar", "\"you already own something like this\" and shop look-alikes"],
                     ["Chat", "assistant that only talks about clothes the user owns"],
                     ["Profile", "name, modesty level (min_coverage), language"],
                     ["Admin", "stats, model quality, users, formula weights"]],
                    widths=[3 * cm, WIDTH - 3 * cm]),
              Spacer(1, 6)]
    story += bullets([
        "Three languages: English, French and Arabic (right-to-left), with plural rules.",
        "Design rules in <i>DESIGN.md</i>, product brief in <i>PRODUCT.md</i>.",
    ])

    # --- 8. testing
    story += h1("testing", "Testing and demo readiness")
    story += [p("Before the jury demo the whole app was run as a user would meet it: the real "
                "API, MongoDB and the React app in Chromium, at phone and desktop widths, with "
                "the test fakes standing in for the models and Gemini. Every screen and flow "
                "worked: scan → verdict → similar → add to wardrobe, item corrections, Build + "
                "complete, chat with tool calls, Arabic right-to-left, and the four admin pages. "
                "The walkthrough and the work that followed it found three bugs:"),
              Spacer(1, 4),
              table([["Found", "Fix"],
                     ["Build page showed the score panel twice on phones",
                      "the desktop side panel is hidden below the desktop width"],
                     ["Phone portrait photos were analysed lying on their side (EXIF rotation "
                      "ignored)", "uploads apply the rotation tag; a test fails without the fix"],
                     ["<i>merge_and_split.py</i> crashed on pandas 3 (allowed by "
                      "<i>requirements.txt</i>)", "one column type fixed; output byte-identical "
                      "to pandas 2"]],
                    widths=[7.5 * cm, WIDTH - 7.5 * cm]),
              Spacer(1, 6),
              p("<i>DEMO.md</i> holds the jury demo script: what to prepare the day before and "
                "30 minutes before, a 9-step run order with talking points, and fallbacks. "
                "Everything except the Gemini chat runs offline. The real models and Gemini still "
                "need a dry run on the demo laptop.")]

    # --- 9. local photos
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
        "<i>src/map_local.py --init</i> lists new photos in <i>labels.csv</i>; the default run "
        "checks every label against <i>mappings/</i> (vocabularies, category ↔ sub_category, "
        "photo size, the same photo saved twice, ids that look like names) and stops with the "
        "line number, then writes <i>local.csv</i> (ids <i>lc_</i>).",
        "<i>merge_and_split.py</i> adds them to <i>dressme.csv</i> with <i>split</i> and "
        "<i>outfit_split</i> forced to test; their colours count as real labels.",
        "Still to do once photos exist: include <i>local</i> in the image cache, the embeddings "
        "and the evaluation scripts.",
    ])

    # --- 10. decisions
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
                     ["H&amp;M catalogue instead of scraping", "all three shop sites block "
                      "scraping; we never try to get around bot protection"],
                     ["Remove the background of uploads", "the models were trained on white "
                      "product shots; a bed, rack or person in the photo confuses them"],
                     ["No repeated sub_category / category over its limit",
                      "a hard rule, not a lower score: two pairs of jeans is never an outfit"],
                     ["Local photos for test only", "the one honest measure of the real "
                      "setting; never trained on"],
                     ["Predictions are never labels", "<i>predicted_attributes.csv</i> and the "
                      "<i>predicted</i> field stay separate from ground truth / user input"]],
                    widths=[6 * cm, WIDTH - 6 * cm])]

    # --- 9. limits
    story += h1("limits", "Limits and risks")
    story += bullets([
        "Traditional (jebba, kaftan) and swimwear are too rare in the public data to learn; "
        "traditional is read as dress. Local photos are needed.",
        "Street photos remain harder than product shots (category 93% vs 98%).",
        "Colour, pattern and structure add no measurable signal in the swap test; the team "
        "weights cost ~6 AUC points against style alone.",
        "PolyVore has no pattern labels, so its patterns are predictions.",
        "Background removal costs ~3-5 s per photo on the CPU; cloth-seg often misses items "
        "lying flat, so it is only used on worn items. Only the cleaned photo is kept, so a "
        "bad cut-out cannot be redone from the original.",
        "The models have not been measured on real phone photos yet (local test set pending).",
        "The H&amp;M catalogue has no prices and is not Tunisian stock; the shop demo is frozen.",
        "Datasets are for non-commercial academic use only and are never redistributed.",
    ])

    # --- 10. next
    story += h1("next", "Next steps")
    story += bullets([
        "Dry run on the demo laptop with the real models, background removal and Gemini "
        "(<i>DEMO.md</i>).",
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
