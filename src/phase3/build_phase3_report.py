"""
Build the Phase 3 PDF report: reports/phase3/phase3_report.pdf

It combines the three EDA reports, the label mapping results and some code
excerpts into one document for the Phase 3 validation.

Needs: the EDA figures (reports/phase3/figures/...) and data/processed/*.csv.
Run:   python src/phase3/build_phase3_report.py
"""

from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
from plot_style import CMAP, CREAM, DARK, GOLD, RUST, SERIES, apply
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph,
                                Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle)

apply()  # DressMe chart colours

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "reports" / "phase3" / "figures"
OUT = ROOT / "reports" / "phase3" / "phase3_report.pdf"
MERGED = ROOT / "data" / "processed" / "dressme.csv"          # merge_and_split.py
COLOUR_REPORT = ROOT / "reports" / "phase3" / "colour_estimation.md"     # estimate_colours.py
COLOUR_EST = ROOT / "data" / "processed" / "colour_estimates.csv"
COLOUR_VALID = ROOT / "reports" / "phase3" / "colour_validation.csv"     # evaluate_colour_labels.py

# DressMe colours (see src/common/plot_style.py): rust headings, dark table headers
ACCENT = colors.HexColor(RUST)
HEADER = colors.HexColor(DARK)
LIGHT = colors.HexColor(CREAM)
CODE_BG = colors.HexColor("#FAF6F0")

# ---------------------------------------------------------------- styles
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=ACCENT, fontSize=18, spaceAfter=8,
                    keepWithNext=1)  # a heading never ends a page
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=ACCENT, fontSize=13, spaceBefore=10,
                    keepWithNext=1)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontSize=11, spaceBefore=6, keepWithNext=1)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=9.5, leading=13)
BULLET = ParagraphStyle("Bullet", parent=BODY, leftIndent=12, bulletIndent=2)
CAPTION = ParagraphStyle("Caption", parent=BODY, fontSize=8, textColor=colors.grey,
                         alignment=TA_CENTER)
CODE = ParagraphStyle("Code", fontName="Courier", fontSize=7.3, leading=9,
                      backColor=CODE_BG, borderPadding=6, leftIndent=6, rightIndent=6,
                      spaceBefore=4, spaceAfter=10)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8, leading=10)
HEAD = ParagraphStyle("Head", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")

WIDTH = A4[0] - 4 * cm  # usable width


# Section order: numbers are computed from this list, so adding a section
# never breaks the "see section N" references (use sec("key")).
SECTIONS = ["context", "inventory", "traceability", "schema", "fp", "fpd", "pv", "mapping",
            "colour", "merged", "local", "decisions", "risks", "next"]


def sec(key):
    return SECTIONS.index(key) + 1


def h1(key, title):
    return Paragraph(f"{sec(key)}. {title}", H1)


TODO = "<font color='#8E4420'><i>[to fill]</i></font>"  # placeholder for the team


def p(text):
    return Paragraph(text, BODY)


def bullets(items):
    return [Paragraph(t, BULLET, bulletText="•") for t in items]


def fig(path, width=WIDTH, caption=None, max_h=9 * cm, keep=True):
    """An image scaled to `width`, but never taller than max_h."""
    iw, ih = ImageReader(str(path)).getSize()
    w = width
    h = w * ih / iw
    if h > max_h:
        h, w = max_h, max_h * iw / ih
    out = [Image(str(path), width=w, height=h)]
    if caption:
        out.append(Paragraph(caption, CAPTION))
    out.append(Spacer(1, 6))
    return KeepTogether(out) if keep else out  # tables need a plain list


def table(rows, widths=None, header=True):
    rows = [[Paragraph(str(c), HEAD if header and i == 0 else CELL) for c in r]
            for i, r in enumerate(rows)]
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT])]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), HEADER),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(style))
    return t


APPENDIX = []  # code excerpts, printed at the end of the report (appendix B)


def code(text):
    """Send an excerpt to appendix B and leave a pointer in the body."""
    APPENDIX.append(text)
    return p(f"<i>→ Code excerpt: appendix B.{len(APPENDIX)}.</i>")


def inline_code(text):
    """Code block (the one short excerpt kept in the body, and appendix A)."""
    return KeepTogether([Preformatted(text.strip("\n"), CODE)])  # never split across pages


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, "DressMe · Phase 3 — Data collection")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


# ------------------------------------------------- cross-dataset figures
def merged_figures():
    """Two new charts built from data/processed/*.csv. Returns stats for the text."""
    names = {"fashion_product": "Fashion Product", "fashionpedia": "Fashionpedia",
             "polyvore": "PolyVore"}
    dfs = {names[n]: pd.read_csv(ROOT / "data" / "processed" / f"{n}.csv", dtype=str)
           for n in names}
    out_dir = FIG / "summary"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) category mix per dataset (stacked bars, % of rows)
    cats = ["top", "bottom", "dress", "outerwear", "shoes", "bag", "accessory", "traditional",
            "swimwear"]
    share = pd.DataFrame({k: d["category"].value_counts(normalize=True) * 100
                          for k, d in dfs.items()}).reindex(cats).fillna(0).T
    ax = share.plot(kind="barh", stacked=True, figsize=(8, 2.8), color=SERIES, width=0.7)
    ax.set_xlabel("% of rows")
    ax.set_xlim(0, 100)
    ax.legend(ncol=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.3))
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(out_dir / "category_mix.png", dpi=160)
    plt.close()

    # 2) share of rows with a value, per schema field and dataset
    fields = ["category", "sub_category", "primary_colour", "pattern", "season",
              "usage", "style", "coverage"]
    fill = pd.DataFrame({k: [d[f].notna().mean() * 100 for f in fields]
                         for k, d in dfs.items()}, index=fields).T
    fig_, ax = plt.subplots(figsize=(8, 2.4))
    im = ax.imshow(fill.values, cmap=CMAP, vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(fields)), fields, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(fill)), fill.index, fontsize=8)
    for i in range(fill.shape[0]):
        for j in range(fill.shape[1]):
            v = fill.values[i, j]
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=7.5,
                    color="white" if v > 60 else "black")
    fig_.colorbar(im, ax=ax, fraction=0.03)
    plt.tight_layout()
    plt.savefig(out_dir / "field_fill.png", dpi=160)
    plt.close()

    counts = {k: d["category"].value_counts() for k, d in dfs.items()}
    total = pd.concat(counts, axis=1).fillna(0).sum(axis=1).astype(int)
    return {"rows": {k: len(d) for k, d in dfs.items()}, "total_cat": total,
            "fill": fill.round(1)}


def final_stats():
    """Validation EDA on the merged file (data/processed/dressme.csv) + its charts."""
    df = pd.read_csv(MERGED, dtype=str, keep_default_na=False)
    df["duplicate"] = df["duplicate"] == "True"
    out_dir = FIG / "summary"
    names = {"fashion_product": "Fashion Product", "fashionpedia": "Fashionpedia",
             "polyvore": "PolyVore"}
    df["dataset"] = df["dataset"].map(names)
    uniq = df[~df["duplicate"]]
    order = ["train", "val", "test"]

    # 1) rows per split and dataset
    split_tab = pd.crosstab(df["dataset"], df["split"]).reindex(columns=order)
    ax = split_tab.plot(kind="barh", stacked=True, figsize=(8, 2.4),
                        color=[RUST, GOLD, DARK], width=0.7)
    ax.set_xlabel("rows")
    ax.legend(ncol=3, fontsize=8)
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(out_dir / "split_sizes.png", dpi=160)
    plt.close()

    # 2) share of each field filled in the final file (unique pictures)
    fields = ["category", "sub_category", "primary_colour", "pattern", "season",
              "usage", "style", "coverage"]
    fill = pd.DataFrame({d: [(g[f] != "").mean() * 100 for f in fields]
                         for d, g in uniq.groupby("dataset")}, index=fields).T
    fill.loc["All (merged)"] = [(uniq[f] != "").mean() * 100 for f in fields]
    fig_, ax = plt.subplots(figsize=(8, 2.7))
    im = ax.imshow(fill.values, cmap=CMAP, vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(fields)), fields, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(fill)), fill.index, fontsize=8)
    for i in range(fill.shape[0]):
        for j in range(fill.shape[1]):
            v = fill.values[i, j]
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=7.5,
                    color="white" if v > 60 else "black")
    fig_.colorbar(im, ax=ax, fraction=0.03)
    plt.tight_layout()
    plt.savefig(out_dir / "field_fill_final.png", dpi=160)
    plt.close()

    # 3) colour distribution: real labels vs estimated (clothes only)
    clothes = uniq[uniq["category"].isin(["top", "bottom", "dress", "outerwear"])]
    col = pd.crosstab(clothes["primary_colour"].replace("", "(empty)"),
                      clothes["colour_source"].replace("", "none"), normalize="columns") * 100
    col = col.drop(index="(empty)", errors="ignore")
    col = col[[c for c in ["label", "estimated"] if c in col]]
    col = col.loc[col.sum(axis=1).sort_values().index]
    ax = col.plot(kind="barh", figsize=(8, 5.2), color=[RUST, GOLD], width=0.8)
    ax.set_xlabel("% of clothes with a colour (per source)")
    ax.legend(["real label (Fashion Product)", "estimated (PolyVore + Fashionpedia)"],
              fontsize=8)
    plt.tight_layout()
    plt.savefig(out_dir / "colour_final.png", dpi=160)
    plt.close()

    # 4) tables for the text
    cat_split = (pd.crosstab(uniq["category"], uniq["split"], normalize="index") * 100
                 ).reindex(columns=order).round(1)
    cat_n = uniq["category"].value_counts()
    o = df[df["outfit_id"] != ""].drop_duplicates("outfit_id")
    outfits = pd.crosstab([o["dataset"], o["outfit_split"]], o["outfit_clean"])
    black = {src: 100 * (clothes.loc[clothes["colour_source"] == src, "primary_colour"]
                         == "black").mean() for src in ["label", "estimated"]}
    colour_src = (pd.crosstab(df["dataset"], df["colour_source"].replace("", "empty"),
                              normalize="index") * 100).round(1)
    # colour coverage, with its base stated: all rows vs items with usable pixels
    # (rows in colour_estimates.csv = items the model could look at)
    est = pd.read_csv(COLOUR_EST, dtype=str, keep_default_na=False, usecols=["id"])
    has_px = df["id"].isin(est["id"]) | (df["colour_source"] == "label")
    has_colour = df["primary_colour"] != ""
    cov = pd.DataFrame({"rows": df.groupby("dataset").size(),
                        "usable": has_px.groupby(df["dataset"]).sum(),
                        "filled": has_colour.groupby(df["dataset"]).sum()})
    cov.loc["All"] = cov.sum()
    cov["pct_usable"] = 100 * cov["filled"] / cov["usable"]
    cov["pct_rows"] = 100 * cov["filled"] / cov["rows"]
    return {"n": len(df), "n_unique": len(uniq), "n_dup": int(df["duplicate"].sum()),
            "cov": cov,
            "split_tab": split_tab, "cat_split": cat_split, "cat_n": cat_n,
            "outfits": outfits, "black": black, "colour_src": colour_src,
            "fill": fill.round(1)}


def colour_accuracy_table():
    """The threshold table written by estimate_colours.py (markdown -> rows)."""
    lines = COLOUR_REPORT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("| minimum confidence"))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        if "---" not in line:
            rows.append([c.strip() for c in line.strip("|").split("|")])
    overall = next(l for l in lines if l.startswith("- All predictions:"))
    per_colour = []
    start = next(i for i, l in enumerate(lines) if l.startswith("| colour |"))
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        per_colour.append([c.strip() for c in line.strip("|").split("|")])
    filled = [l for l in lines if l.startswith("- Colour filled for")]
    return rows, overall[2:].replace("**", ""), per_colour, filled


# ------------------------------------------------------------ the report
def build():
    s = merged_figures()
    rows = s["rows"]
    n_total = sum(rows.values())
    m = final_stats()
    acc_rows, acc_overall, acc_per_colour, colour_filled = colour_accuracy_table()
    used = next(r for r in acc_rows if "used" in r[0])  # the threshold in use
    sp = m["split_tab"].sum()
    cv = m["cov"]
    n_sub = len(pd.read_csv(ROOT / "mappings" / "sub_category_vocabulary.csv"))
    # open team decisions = rows whose note says REVIEW, in any mapping file
    n_review = sum(f.read_text(encoding="utf-8").count("REVIEW")
                   for f in (ROOT / "mappings").glob("*.csv"))
    # hand-label check of the cut in use (evaluate_colour_labels.py), if done
    hand_check = "hand-label check pending"
    if COLOUR_VALID.exists():
        v = pd.read_csv(COLOUR_VALID)
        v = v[v["cut"] == float(used[0].split()[0])]
        hand_check = "hand labels: " + ", ".join(
            f"{r.accuracy:.0f}% on {r.dataset}" for r in v.itertuples())
    story = []

    # --- cover / summary
    story += [Spacer(1, 3 * cm),
              Paragraph("DressMe", ParagraphStyle("T", parent=H1, fontSize=30, leading=36)),
              Paragraph("Phase 3 — Data collection &amp; Exploratory Data Analysis",
                        ParagraphStyle("S", parent=H2, fontSize=15)),
              Spacer(1, 0.4 * cm),
              p("AI personal fashion assistant · ESPRIT, Advanced Data Science project "
                f"(team of 6) · Report generated {date.today().isoformat()}"),
              Spacer(1, 1.2 * cm),
              Paragraph("Executive summary", H2)]
    story += bullets([
        "Three public datasets were explored and mapped to one <b>unified label schema</b>: "
        f"Kaggle Fashion Product ({rows['Fashion Product']:,} rows kept), Fashionpedia "
        f"({rows['Fashionpedia']:,} worn items) and Maryland PolyVore "
        f"({rows['PolyVore']:,} product shots in 31k outfits): <b>{n_total:,} labelled "
        "items</b> in total.",
        "The sources complement each other: Fashion Product is the only one with text labels "
        "(colour, season, usage); Fashionpedia brings real street photos plus pattern and "
        "<b>coverage</b> (modesty) attributes; PolyVore brings user-made outfits for the "
        "<b>compatibility</b> model.",
        "Main data risks: strong class imbalance, no colour label outside Fashion Product, "
        "~24k duplicate images in PolyVore (split leakage), small crops in Fashionpedia, and a "
        "large domain gap between catalogue shots and friperie phone photos.",
        "Mapping rules live in <font face='Courier'>mappings/*.csv</font>, never in code; the "
        "apply scripts stop when a source value has no rule. "
        + (f"{n_review} rules are flagged <b>REVIEW</b> for team decision." if n_review
           else "All <b>REVIEW</b> decisions are settled."),
        "<b>Colour</b> was estimated for PolyVore and Fashionpedia with a small model trained "
        f"on Fashion Product's real labels. At the confidence cut used it is {used[2]} "
        f"accurate on unseen Fashion Product images (it gives a colour to {used[1]} of them). "
        f"Estimated colours were kept for {cv.loc['PolyVore', 'pct_usable']:.0f}% of "
        f"PolyVore items and {cv.loc['Fashionpedia', 'pct_usable']:.0f}% of Fashionpedia "
        "items <i>with usable pixels</i>, i.e. "
        f"{cv.loc['PolyVore', 'pct_rows']:.0f}% and {cv.loc['Fashionpedia', 'pct_rows']:.0f}% "
        "<i>of all rows</i>; otherwise the colour stays empty.",
        f"<b>Merged dataset</b>: {m['n']:,} rows ({m['n_unique']:,} unique pictures / crops) "
        f"in one file, split <b>{sp['train']:,} / {sp['val']:,} / {sp['test']:,}</b> "
        "(train / val / test) with no picture shared between splits. All Phase 3 goals are "
        "done except the collection of local photos.",
    ])
    story.append(PageBreak())

    # --- 1. context
    story += [h1("context", "Context and goals"),
              p("DressMe targets young Tunisians on a limited budget who shop mostly "
                "second-hand (friperie), often buying unlabelled items that can rarely be "
                "returned. Phases 1 (Empathize) and 2 (Ideate) are complete; the survey "
                "(57 responses) guides the data choices:"),
              table([["Survey finding", "Consequence for the data"],
                     ["Black dominates 84% of wardrobes", "Colour labels must separate black / "
                      "navy / charcoal well; check black share per dataset"],
                     ["56% shop second-hand", "Real friperie photos reserved for the test set"],
                     ["40% frustrated by fit", "Keep fit / silhouette hints (Fashionpedia)"],
                     ["42% want “should I buy this?” advice", "Need compatibility data "
                      "(PolyVore outfits) and rich attributes"]],
                    widths=[5.5 * cm, WIDTH - 5.5 * cm]),
              Spacer(1, 8),
              Paragraph("Phase 3 objectives", H2)]
    story += bullets(["EDA per dataset: size, class balance, missing values, colour "
                      "distribution.",
                      "Label mapping from each dataset to the unified schema.",
                      "Merged, cleaned dataset with train / val / test splits (local photos "
                      "reserved for test).",
                      "EDA report for the Phase 3 validation (this document)."])
    story += [Paragraph("Target tech stack", H2),
              p("React + TailwindCSS · FastAPI · MongoDB · EfficientNet (classification) · "
                "FashionCLIP (embeddings, similarity) · Gemini API (chat) · custom weighted "
                "compatibility formula.")]

    # --- dataset inventory
    story += [h1("inventory", "Dataset inventory"),
              p("All sources are used for non-commercial academic work only and are never "
                "redistributed. Sizes are what we use after cleaning (rows in "
                "<font face='Courier'>data/processed/</font>)."),
              table([["Source", "Content", "Size", "Licence / terms", "Access"],
                     ["Kaggle Fashion Product Images (Small)", "catalogue shots, text labels",
                      f"{rows['Fashion Product']:,} items (44,441 raw)", "MIT (Kaggle page)",
                      "downloaded"],
                     ["Fashionpedia", "street / runway photos, masks, attributes",
                      f"{rows['Fashionpedia']:,} worn items in 46,743 photos",
                      "annotations CC BY 4.0; images not owned by Fashionpedia (Flickr and "
                      "free-licence sites)", "downloaded"],
                     ["Maryland PolyVore (Re-PolyVore)", "product shots grouped in outfits",
                      f"{rows['PolyVore']:,} items in 31,333 outfits",
                      "Apache-2.0 (dataset repository); images from Polyvore users",
                      "downloaded"],
                     ["DeepFashion2", "consumer + shop photos, 13 categories, landmarks",
                      "491k images (announced)", "non-commercial research only (request form)",
                      "access requested"],
                     ["DressCode", "high-resolution garment + model pairs",
                      "53,792 pairs (announced)", "non-commercial academic research, "
                      "no modified redistribution (Yoox Net-a-Porter licence)",
                      "access requested"],
                     ["ModaNet", "street photos with pixel masks (multi-item capture)",
                      "~55k images (announced)", "to check on the official page",
                      "planned, not requested yet"],
                     ["VITON-HD", "person + garment pairs (virtual try-on)",
                      "~14k pairs (announced)", "to check on the official page",
                      "planned, not requested yet"],
                     ["Local photos (wardrobe / friperie)", "our own phone photos",
                      "target 750–1,500 items + ~100 near-duplicate pairs",
                      "signed consent of every contributor (see section "
                      f"{sec('local')})", "in progress"]],
                    widths=[3.4 * cm, 3.4 * cm, 3.2 * cm, 4.4 * cm, WIDTH - 14.4 * cm]),
              Spacer(1, 4),
              p("The collection plan named <i>Polyvore Outfits</i> (~68k outfits); we use the "
                "Maryland version (31,333 outfits), which has the same kind of user-made "
                "outfits and was available without a request."),
              Spacer(1, 10)]

    # --- traceability: dataset -> features -> personas
    story += [h1("traceability", "Traceability: data → features → personas"),
              p("Every dataset traces back to a feature, and every feature to a persona and a "
                "“How might we” question (HMW) from Phase 2, as in the Phase 3 collection plan. "
                "Features and personas without a dataset here (occasion &amp; weather styling "
                "for Salma, the chat assistant, the style profile) use APIs, the survey or "
                "app-generated data instead."),
              table([["Dataset", "DressMe features it trains or tests", "Personas · HMW"],
                     ["Fashion Product", "photo capture + auto-tagging (category, colour, "
                      "season, usage); trains the colour model behind colour stretch",
                      "Amira · H2; Ines · H7"],
                     ["Fashionpedia", "multi-item photo capture (masks); pattern tagging; "
                      "coverage for the modest filter of the style profile",
                      "Amira · H2; all personas"],
                     ["PolyVore", "outfit generation, complete the look (compatibility "
                      "formula)", "Amira, Youssef · H1 H3"],
                     ["DeepFashion2 (requested)", "auto-tagging robustness on consumer photos; "
                      "landmarks for the fit check", "Amira · H2; Rania · H5"],
                     ["DressCode (requested)", "virtual try-on", "Ines, Youssef · H7"],
                     ["Local photos", "real test set (friperie domain) for auto-tagging and "
                      "instant scan; local garments; fit-check subset; near-duplicate pairs "
                      "for the duplicate warning; purchase-advisor evaluation set",
                      "Amira · H2; Nour · H4; Rania · H5; Youssef, Nour · H3 H4; "
                      "Youssef, Skander · H8"]],
                    widths=[3.5 * cm, WIDTH - 8 * cm, 4.5 * cm])]

    # --- schema
    story += [CondPageBreak(8 * cm), h1("schema", "Unified label schema"),
              p("Every source is converted to the same fields so the models can be trained on "
                "the merged data."),
              table([["Field", "Values"],
                     ["category", "top, bottom, dress, outerwear, shoes, bag, accessory, "
                      "traditional, swimwear"],
                     ["sub_category", f"{n_sub} controlled values (t-shirt, shirt, jeans, jebba, "
                      "sneakers…) in sub_category_vocabulary.csv, each tied to a parent category"],
                     ["primary / secondary_colour", "fixed 21-colour palette "
                      "(colour_palette.csv)"],
                     ["pattern", "solid, striped, checked, floral, printed"],
                     ["season (multi)", "summer, winter, mid-season"],
                     ["usage (multi)", "casual, formal, sport, wedding, eid, work"],
                     ["style (multi)", "classic, streetwear, modest, sporty, trendy"],
                     ["coverage", "1 (very revealing) … 5 (fully covered)"],
                     ["source", "public_dataset, wardrobe, friperie"]],
                    widths=[4 * cm, WIDTH - 4 * cm]),
              Spacer(1, 8), Paragraph("Mapping conventions", H2)]
    story += bullets([
        "Rules are CSV files in <font face='Courier'>mappings/</font>; the apply script fails "
        "if a source value has no rule, so nothing is silently dropped.",
        "Multi-value fields are joined with <font face='Courier'>|</font>.",
        "Unknown stays empty: we <b>never guess</b> (e.g. a product with no pattern keyword is "
        "not assumed solid).",
        "Ids are prefixed per dataset (<font face='Courier'>fp_</font>, "
        "<font face='Courier'>fpd_</font>, <font face='Courier'>pv_</font>); output goes to "
        "<font face='Courier'>data/processed/&lt;dataset&gt;.csv</font>.",
    ])
    story.append(p("The mapping scripts share two safety checks: a source value with no rule, "
                   "or a rule that outputs a value outside the schema, stops the script "
                   "(<font face='Courier'>src/phase3/map_fashion_product.py</font>)."))
    story.append(code('''
def check_covered(values, mapping_keys, what):
    """Stop with a clear message if a source value has no mapping rule."""
    missing = sorted(set(values.dropna()) - set(mapping_keys))
    if missing:
        sys.exit(f"ERROR: {what} values with no rule in mappings/: {missing}")


def check_allowed(values, allowed, what):
    """Stop if a mapping file uses a value that is not in the unified schema."""
    wrong = sorted(set(values) - allowed - {""})
    if wrong:
        sys.exit(f"ERROR: {what} values not in the unified schema: {wrong}")
'''))
    story.append(PageBreak())

    # --- 3. Fashion Product
    fp = FIG / "fashion_product"
    story += [h1("fp", "EDA — Kaggle Fashion Product Images (Small)"),
              table([["Metric", "Value"],
                     ["Rows in styles.csv", "44,446 (22 rows repaired: commas inside names)"],
                     ["Usable products (row + image)", "44,441"],
                     ["Missing values", "usage 317, season 21, baseColour 15, name 7, year 1"],
                     ["Image size", "60×80 px, catalogue shots on white background"],
                     ["Labels", "gender, master/sub category, 142 article types, 46 colours, "
                      "season, usage, product name"]],
                    widths=[5.5 * cm, WIDTH - 5.5 * cm]),
              Spacer(1, 6), Paragraph("Class balance", H2)]
    story += bullets([
        "masterCategory: Apparel 48.1%, Accessories 25.4%, Footwear 20.8%, Personal Care "
        "5.4%. <b>2,430 off-topic rows</b> (Personal Care, Home, Sporting Goods) are dropped.",
        "142 article types, <b>72 have fewer than 50 images</b>: merged into coarser "
        "sub_categories during mapping. Top: Tshirts 7,069, Shirts 3,215, Casual Shoes 2,846.",
        "usage is dominated by Casual (77.4%); season by Summer (48.3%).",
    ])
    story.append(fig(fp / "articleType_top40.png", caption="Top 40 article types", max_h=7 * cm))
    story.append(Table([[fig(fp / "usage.png", width=WIDTH / 2 - 4, max_h=5 * cm, keep=False),
                         fig(fp / "season.png", width=WIDTH / 2 - 4, max_h=5 * cm, keep=False)]],
                       colWidths=[WIDTH / 2] * 2))
    story += [Paragraph("Colour distribution", H2)]
    story += bullets([
        "46 colour names, grouped into our 21-colour palette via fashion_product_colour.csv.",
        f"Black 21.9%, White 12.5%, Blue 11.1%, Brown 7.9%, Grey 6.2% of items (section {sec('merged')} "
        "discusses how this relates to the survey).",
    ])
    story.append(fig(fp / "baseColour.png", caption="Base colour distribution", max_h=7 * cm))
    story += [Paragraph("Take-aways", H3)]
    story += bullets([
        "Only source with text labels: the reference for colour, season and usage.",
        "Tiny images and studio conditions: very different from friperie phone photos, so our "
        "own photos stay in the test set.",
        "Pattern is read from keywords in the product name; only 21% of rows get one.",
    ])
    story.append(fig(fp / "samples.png", caption="Random sample of product images", max_h=4.2 * cm))
    story.append(CondPageBreak(8 * cm))

    # --- 4. Fashionpedia
    fpd = FIG / "fashionpedia"
    story += [h1("fpd", "EDA — Fashionpedia"),
              table([["Split", "Images", "Objects", "Whole items", "Parts"],
                     ["train", "45,623", "333,401", "163,060", "170,341"],
                     ["val", "1,158", "8,781", "4,688", "4,093"],
                     ["test", "2,044", "no labels (not used)", "–", "–"]],
                    widths=[WIDTH / 5] * 5),
              Spacer(1, 6)]
    story += bullets([
        "Street and runway photos, several items per photo (median 3, max 20): each photo is "
        "one outfit. Median image 682×1024 px.",
        "46 categories (27 whole items, 19 garment parts such as sleeve, neckline, pocket) and "
        "294 attributes in 11 groups.",
        "<b>No colour label</b>. 53% of whole items have no attribute at all (mostly shoes and "
        "accessories); 94.1% of clothes have a textile-pattern attribute.",
        "Ids restart per split, so they are prefixed with the split name.",
    ])
    story.append(fig(fpd / "items.png", caption="Whole-item categories", max_h=8 * cm))
    story += bullets([
        "Imbalance: shoe 28.6% (labelled one per foot), dress 11.5%, top 10.1%; cape, leg "
        "warmer, umbrella &lt; 0.1%.",
        "<b>33.8% of item crops are shorter than 64 px</b> (watch 93%, sock 90%, glasses 87%): "
        "probably too small to classify.",
    ])
    story.append(fig(fpd / "bbox_short_side.png", caption="Short side of item crops (px)",
                     max_h=6 * cm))
    story += [Paragraph("Attributes used for the schema", H2),
              table([["Fashionpedia group", "Items with it", "→ DressMe field"],
                     ["textile pattern", "44.3%", "pattern (plain 60k, floral 3.7k, stripe 3.1k…)"],
                     ["length", "40.1%", "coverage (with sleeve / neckline parts)"],
                     ["nickname", "30.1%", "sub_category (118 values: classic t-shirt, gown, "
                      "jeans…)"],
                     ["silhouette", "44.8%", "fit / style hints (regular, tight, loose…)"]],
                    widths=[4 * cm, 2.5 * cm, WIDTH - 6.5 * cm]),
              Spacer(1, 6),
              Table([[fig(fpd / "pattern.png", width=WIDTH / 2 - 4, max_h=5.5 * cm, keep=False),
                      fig(fpd / "length.png", width=WIDTH / 2 - 4, max_h=5.5 * cm, keep=False)]],
                    colWidths=[WIDTH / 2] * 2)]
    story += [Paragraph("Estimated colour", H2)]
    story += bullets([
        "Median pixel colour inside 2,000 random clothing masks (crop ≥ 64 px), snapped to the "
        "palette with a Lab distance.",
        "black 25.1%, navy 19.2%, silver 14.0%, grey 10.8%, brown 7.0%. Shadows push colours "
        "towards grey / silver, and multicolour can never be predicted this way.",
    ])
    story.append(fig(fpd / "colour_estimate.png", caption="Estimated colour of clothes",
                     max_h=6 * cm))
    story.append(p("Colours are compared in Lab space, which is closer to human perception "
                   "than RGB (<font face='Courier'>src/phase3/colour_utils.py</font>)."))
    story.append(code('''
def rgb_to_lab(rgb):
    """Convert sRGB colours (N x 3, 0-255) to CIE Lab."""
    c = np.asarray(rgb, dtype=float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)  # linear RGB
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])  # normalise to D65 white
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], axis=1)

class Palette:
    def nearest(self, rgb):
        """Name of the palette colour closest to one RGB colour."""
        dist = np.linalg.norm(self.lab - rgb_to_lab([rgb]), axis=1)
        return self.names[dist.argmin()]
'''))
    story.append(fig(fpd / "samples.png", caption="Example Fashionpedia photos", max_h=4.5 * cm))
    story.append(CondPageBreak(8 * cm))

    # --- 5. PolyVore
    pv = FIG / "polyvore"
    story += [h1("pv", "EDA — Maryland PolyVore (Re-PolyVore)"),
              table([["Metric", "Value"],
                     ["Images", "126,927 in 20 category folders"],
                     ["Outfits", "31,333 (median 4 items, max 34)"],
                     ["Junk files", "22 (desktop.ini, a .lnk shortcut, a “- Copy.jpg”)"],
                     ["Unlinked images", "276 named <number>.jpg (no outfit)"],
                     ["Exact duplicates", "24,273 extra copies in 14,756 groups; 304 groups "
                      "span two folders (label conflicts)"],
                     ["Background", "white in 99% of a 500-image sample"],
                     ["Text / colour / split", "none"]],
                    widths=[4.5 * cm, WIDTH - 4.5 * cm]),
              Spacer(1, 6)]
    story.append(fig(pv / "categories.png", caption="Images per folder", max_h=7 * cm))
    story += bullets([
        "Folders are coarse: <font face='Courier'>pants</font> also holds shorts, "
        "<font face='Courier'>top</font> holds shirt-jackets, so sub_category is only filled "
        "when the folder is unambiguous (35.8% of rows).",
        "Accessories (jewellery, eyewear, hats…) are 26.7% of images; no traditional items.",
        "Outfits with clothes <b>and</b> shoes: 39.1% (12,249). 2,053 single-item outfits are "
        "useless for compatibility.",
    ])
    story.append(Table([[fig(pv / "items_per_outfit.png", width=WIDTH / 2 - 4, max_h=5.5 * cm, keep=False),
                         fig(pv / "cooccurrence.png", width=WIDTH / 2 - 4, max_h=5.5 * cm, keep=False)]],
                       colWidths=[WIDTH / 2] * 2))
    story += [Paragraph("Estimated colour", H2)]
    story += bullets([
        "Clothes only: black 19.5%, silver 15.5%, grey 13.5%, cream 9.1%, navy 9.1%.",
        "Main systematic error: white / very light items land on silver. Metallic colours "
        "should probably be allowed only for shoes, bags and jewellery (team decision).",
    ])
    story.append(fig(pv / "colour_check.png", caption="Colour estimate check grid",
                     max_h=5.5 * cm))
    story.append(p("Duplicates across folders are dropped as label conflicts, and the file "
                   "MD5 is kept as <font face='Courier'>image_group</font> to stop split "
                   "leakage (<font face='Courier'>src/phase3/map_polyvore.py</font>)."))
    story.append(code('''
# label conflicts: same picture, different unified categories -> drop all copies.
labels = df.groupby("md5")[["category", "sub_category"]].nunique()
conflict = labels[(labels["category"] > 1) | (labels["sub_category"] > 1)].index
df = df[~df["md5"].isin(conflict)]

out = pd.DataFrame({
    "id": "pv_" + df["folder"] + "_" + df["file"].str.removesuffix(".jpg"),
    "category": df["category"],
    ...
    "image_group": df["md5"],  # same value = same picture: keep in one split
})
'''))
    story.append(fig(pv / "example_outfits.png", caption="Example user-made outfits",
                     max_h=5.5 * cm))
    story.append(CondPageBreak(8 * cm))

    # --- 6. mapping results
    tot = s["total_cat"]
    story += [h1("mapping", "Label mapping results"),
              table([["Dataset", "Script", "Rows out", "Notes"],
                     ["Fashion Product", "map_fashion_product.py",
                      f"{rows['Fashion Product']:,}", "off-topic and Indian ethnic rows "
                      "dropped; colour, season, usage from text"],
                     ["Fashionpedia", "map_fashionpedia.py", f"{rows['Fashionpedia']:,}",
                      "one row per worn item, bbox to crop, outfit_id = photo"],
                     ["PolyVore", "map_polyvore.py", f"{rows['PolyVore']:,}",
                      "folder-based labels, image_group = MD5, conflicts dropped"],
                     ["Total", "", f"{n_total:,}", ""]],
                    widths=[3 * cm, 4.2 * cm, 2.2 * cm, WIDTH - 9.4 * cm]),
              Spacer(1, 8)]
    story.append(KeepTogether([Paragraph("Category mix per source", H2),
                               fig(FIG / "summary" / "category_mix.png", max_h=6 * cm)]))
    story.append(p("Combined: " + ", ".join(f"{c} {int(n):,}" for c, n in
                                            tot.sort_values(ascending=False).items())
                   + ". Shoes and accessories dominate; dress and outerwear are the "
                   "smallest clothing classes, and <b>traditional has no public data yet</b> "
                   "(jebba, kaftan… must come from our own photos)."))
    story += [Paragraph("Which fields each source can fill", H2)]
    story.append(fig(FIG / "summary" / "field_fill.png",
                     caption="% of rows with a value, per schema field", max_h=6 * cm))
    story += bullets([
        "<b>style</b> is empty everywhere: no public dataset labels it; it will come from the "
        "model / team annotation.",
        "<b>Colour</b> exists only for Fashion Product; PolyVore and Fashionpedia colours are "
        f"estimated in section {sec('colour')}.",
        "<b>coverage</b> only comes from Fashionpedia (40.1% of items).",
    ])
    story += [Paragraph("Coverage from Fashionpedia parts", H2),
              p("Neckline and sleeve-length attributes sit on <i>part</i> objects, not on the "
                "garment. Each part is linked to the one upper garment whose box contains it; "
                "the final coverage is the <b>lowest</b> score among length, nickname, sleeve "
                "and neckline (the most revealing part decides)."),
              code('''
def link_parts(anns, part_id):
    """Link each part (sleeve or neckline) to the one garment that contains it."""
    parts = anns[anns["category_id"] == part_id]
    garments = anns[anns["category_id"].isin(UPPER_IDS)]
    pairs = parts.merge(garments, on="image_id", suffixes=("", "_g"))

    # intersection of the two boxes, as a share of the part's box area
    x1 = np.maximum(pairs["bbox_x"], pairs["bbox_x_g"])
    y1 = np.maximum(pairs["bbox_y"], pairs["bbox_y_g"])
    x2 = np.minimum(pairs["bbox_x"] + pairs["bbox_w"], pairs["bbox_x_g"] + pairs["bbox_w_g"])
    y2 = np.minimum(pairs["bbox_y"] + pairs["bbox_h"], pairs["bbox_y_g"] + pairs["bbox_h_g"])
    inter = (x2 - x1).clip(lower=0) * (y2 - y1).clip(lower=0)
    pairs["inside"] = inter / (pairs["bbox_w"] * pairs["bbox_h"]).clip(lower=1)

    pairs = pairs[pairs["inside"] >= MIN_INSIDE]
    n_owners = pairs.groupby("ann_id")["ann_id_g"].transform("size")
    return pairs[n_owners == 1]          # keep only unambiguous owners
'''),
              p("Coverage distribution: 5 → 22,486 · 4 → 6,982 · 3 → 10,963 · 2 → 18,994 · "
                "1 → 4,722. Limitation: sleeveless items have no sleeve part, so their coverage "
                "can be overestimated when <font face='Courier'>sleeve</font> is not in "
                "<font face='Courier'>coverage_from</font>.")]
    story.append(KeepTogether([
        p("Pattern in Fashion Product is read from the product name, and left empty "
          "when no keyword matches:"),
        inline_code('''
def find_pattern(name, keywords):
    """Return the pattern of the first keyword (by priority) found in the product name."""
    if pd.isna(name):
        return pd.NA
    words = name.lower()
    for kw, pattern in keywords:
        if re.search(rf"\\b{kw}\\b", words):
            return pattern
    return pd.NA  # unknown: do NOT assume solid
''')]))
    story.append(CondPageBreak(8 * cm))

    # --- 7. colour estimation
    story += [h1("colour", "Colour estimation (PolyVore, Fashionpedia)"),
              p("Only Fashion Product has colour labels. We first tried the EDA rule (median "
                "pixel colour snapped to the nearest palette colour) and measured it against "
                "Fashion Product's real labels: it was right only <b>25–36%</b> of the time. "
                "Black fabric photographs as dark blue-grey and became <i>navy</i>, white in "
                "soft shadow became <i>cream</i> or <i>silver</i>, denim became <i>grey</i>. "
                "So the colour is <b>learned</b> instead:")]
    story += bullets([
        "Features: a 6×6×6 colour histogram in Lab space plus a few percentiles of the item's "
        "pixels. Product shots: white background removed (near-white regions touching the "
        "border). Fashionpedia: pixels inside the item's segmentation mask only.",
        "Model: gradient boosting trained on Fashion Product images of the <b>train</b> split, "
        "evaluated on its val + test images (never seen during training).",
        "<b>Never guess</b>: the colour stays empty when the model's confidence is below the "
        "cut, or when a Fashionpedia item is too small (crop &lt; 64 px) or has no polygon mask. "
        "<font face='Courier'>colour_confidence</font> is kept so a stricter cut can be used "
        "later, and <font face='Courier'>colour_source</font> = label / estimated.",
        "Gold and silver are not allowed for clothes (a team decision): the model's next "
        "best colour is used instead.",
    ])
    story += [Paragraph("Accuracy on unseen Fashion Product images", H2),
              p(acc_overall),
              table([["Minimum confidence", "Colour filled", "Accuracy"]] + acc_rows,
                    widths=[WIDTH / 3] * 3),
              Spacer(1, 6)]
    half = (len(acc_per_colour) + 1) // 2
    left, right = acc_per_colour[:half], acc_per_colour[half:]
    right += [["", "", ""]] * (len(left) - len(right))
    story += [p("Accuracy per true colour, above the confidence cut:"),
              table([["Colour", "Images", "Accuracy", "Colour", "Images", "Accuracy"]]
                    + [a + b for a, b in zip(left, right)], widths=[WIDTH / 6] * 6),
              Spacer(1, 6),
              p("Fashion Product photos are tiny (60×80) and often show a model, so these "
                "numbers are a rough guide. PolyVore (product shots on white) should behave "
                "similarly; Fashionpedia (street photos, shadows) is probably less accurate: "
                "see the check grids.")]
    # real accuracy on the target domains (hand labels, evaluate_colour_labels.py)
    story += [Paragraph("Accuracy on hand-labelled PolyVore and Fashionpedia items", H2)]
    if COLOUR_VALID.exists():
        val = pd.read_csv(COLOUR_VALID)
        story += [p("Random val / test items (crops ≥ 64 px), labelled by hand without seeing "
                    "the model's answer; “unsure” labels are left out. 95% confidence "
                    "interval in brackets."),
                  table([["Dataset", "Min. confidence", "Colour kept", "Accuracy (95% CI)"]]
                        + [[r.dataset, f"{r.cut}", f"{r.coverage:.0f}% ({r.kept})",
                            f"{r.accuracy:.1f}% ({r.ci_low:.0f}–{r.ci_high:.0f})"]
                           for r in val.itertuples()],
                        widths=[WIDTH / 4] * 4)]
        # most frequent mistakes, from the markdown written by evaluate_colour_labels.py
        md = COLOUR_VALID.with_suffix(".md").read_text(encoding="utf-8").splitlines()
        errors = [l[2:] for l in md if l.startswith("- ") and "→" in l][:5]
        story.append(p("Most frequent mistakes (true → predicted, all confidences): "
                       + "; ".join(errors) + ". Black read as navy or brown is the main "
                       "error, which matters because black dominates our users' wardrobes."))
    else:
        story.append(p("<i>Pending.</i> 200 PolyVore and 200 Fashionpedia items from val / "
                       "test are being labelled by hand "
                       "(<font face='Courier'>src/phase3/make_colour_labelling_sheet.py</font>); "
                       "<font face='Courier'>src/phase3/evaluate_colour_labels.py</font> will give "
                       "the real accuracy on these two datasets here."))
    story += [Paragraph("Result", H2)]
    # estimate_colours.py writes PolyVore first, then Fashionpedia
    story.append(table(
        [["Dataset", "All rows", "Items with usable pixels", "Colour kept",
          "% of usable items", "% of all rows"]]
        + [[d, f"{int(cv.loc[d, 'rows']):,}", f"{int(cv.loc[d, 'usable']):,}",
            f"{int(cv.loc[d, 'filled']):,}", f"{cv.loc[d, 'pct_usable']:.1f}%",
            f"{cv.loc[d, 'pct_rows']:.1f}%"] for d in ["PolyVore", "Fashionpedia"]],
        widths=[WIDTH / 6] * 6))
    story.append(p("<i>Usable pixels</i>: every PolyVore picture; for Fashionpedia only items "
                   "with a polygon mask and a crop of at least 64 px (the others get no "
                   "estimate at all)."))
    story.append(fig(FIG / "colour" / "check_polyvore.png",
                     caption="PolyVore: estimated colour (confidence)", max_h=6 * cm))
    story.append(fig(FIG / "colour" / "check_fashionpedia.png",
                     caption="Fashionpedia: estimated colour of item crops (confidence)",
                     max_h=6 * cm))
    story.append(p("The features, the metal rule and the confidence cut are in "
                   "<font face='Courier'>src/phase3/estimate_colours.py</font>."))
    story.append(code('''
def features(rgb_pixels):
    """Fixed-length colour description of a set of pixels (N x 3, RGB)."""
    lab = rgb_to_lab(rgb_pixels)
    hist, _ = np.histogramdd(lab, bins=(L_EDGES, AB_EDGES, AB_EDGES))
    hist = hist.ravel() / len(lab)
    pct = np.percentile(lab, [10, 25, 50, 75, 90], axis=0).ravel()
    return np.concatenate([hist, pct, lab.mean(axis=0), lab.std(axis=0)])


def predict(clf, X, categories):
    """Best colour per row; metallic colours are skipped for clothes."""
    proba = clf.predict_proba(X)
    classes = np.array(clf.classes_)
    no_metal = np.isin(np.asarray(categories), list(METAL_FREE))
    proba[np.ix_(no_metal, np.isin(classes, list(METALS)))] = 0
    proba = proba / proba.sum(axis=1, keepdims=True)
    best = proba.argmax(axis=1)
    return classes[best], proba[np.arange(len(best)), best]

# the colour stays empty when the model is not sure enough
df["primary_colour"] = np.where(conf >= MIN_CONFIDENCE, colour, "")
'''))
    story.append(CondPageBreak(8 * cm))

    # --- 8. merged dataset + splits (validation EDA)
    st = m["split_tab"]
    story += [h1("merged", "Merged dataset and train / val / test splits"),
              p(f"<font face='Courier'>src/phase3/merge_and_split.py</font> joins the three "
                f"processed files and the colour estimates into "
                f"<font face='Courier'>data/processed/dressme.csv</font>: <b>{m['n']:,} rows</b>, "
                f"of which {m['n_dup']:,} are extra copies of the same picture "
                f"(<font face='Courier'>duplicate</font> = True, to drop for classification)."),
              table([["Dataset", "train", "val", "test", "total"]]
                    + [[d] + [f"{int(st.loc[d, c]):,}" for c in ["train", "val", "test"]]
                       + [f"{int(st.loc[d].sum()):,}"] for d in st.index]
                    + [["Total"] + [f"{int(sp[c]):,}" for c in ["train", "val", "test"]]
                       + [f"{int(sp.sum()):,}"]],
                    widths=[WIDTH / 5] * 5),
              Spacer(1, 6),
              fig(FIG / "summary" / "split_sizes.png", max_h=5 * cm),
              Paragraph("How the splits are made", H2)]
    story += bullets([
        "Fashionpedia's official test set has no labels, so our train / val / test splits "
        "for Fashionpedia are all made from its labelled train + val images.",
        "80 / 10 / 10, decided by a hash of the group id: the same group always lands in the "
        "same split, even after re-running the script or adding rows.",
        "<font face='Courier'>split</font> (classification) is per picture: all copies of a "
        "picture (<font face='Courier'>image_group</font>) and all items of a Fashionpedia "
        "photo share one split.",
        "<font face='Courier'>outfit_split</font> (compatibility) is per outfit. In PolyVore "
        "the same product is reused in many outfits, which share other products, and so on: "
        "<b>61% of PolyVore rows form one chain</b>, so outfits and pictures cannot both be "
        "kept apart. A picture used in a test outfit goes to test, so every test outfit is "
        "made only of test pictures; <font face='Courier'>outfit_clean</font> = False marks "
        "outfits that share a picture with another split.",
        "Local photos (source = wardrobe / friperie) always go to test. The script stops if a "
        "picture ends up in two splits, or a test outfit contains a non-test picture.",
    ])
    story.append(code('''
def bucket(key):
    """Deterministic split for a group id: same key -> same split, every run."""
    n = int(hashlib.md5(f"{SEED}:{key}".encode()).hexdigest()[:8], 16) % 100
    if n < SHARES["train"]:
        return "train"
    if n < SHARES["train"] + SHARES["val"]:
        return "val"
    return "test"

# pictures: strictest split among their outfits (test > val > train), else own hash
in_outfits = (df[has_outfit].assign(r=df["outfit_split"].map(rank))
              .groupby("image_group")["r"].max().map(name))
group_split = dict(zip(groups, groups.map(bucket)))
group_split.update(in_outfits.to_dict())
df["split"] = df["image_group"].map(group_split)
'''))
    cs = m["cat_split"]
    story += [KeepTogether([Paragraph("Class balance across splits", H2),
              p("Share of each category's unique pictures in each split: every class stays "
                "close to 80 / 10 / 10, so val and test represent all categories."),
              table([["Category", "unique items", "train %", "val %", "test %"]]
                    + [[c, f"{int(m['cat_n'][c]):,}"] + [f"{cs.loc[c, k]:.1f}"
                                                        for k in ["train", "val", "test"]]
                       for c in m["cat_n"].index],
                    widths=[WIDTH / 5] * 5)]),
              Spacer(1, 6)]
    orows = [[d, spl, f"{int(r.get('True', 0)):,}", f"{int(r.get('False', 0)):,}"]
             for (d, spl), r in m["outfits"].iterrows()]
    story += [Paragraph("Outfits for the compatibility model", H2),
              table([["Dataset", "outfit_split", "clean outfits", "sharing a picture"]] + orows,
                    widths=[WIDTH / 4] * 4),
              Spacer(1, 4),
              p("Fashionpedia outfits (one photo each) are all clean. For PolyVore, a strict "
                "evaluation should use only the clean val / test outfits; the others are fine "
                "for a “non-disjoint” evaluation, as in the original Polyvore benchmark.")]
    story += [Paragraph("Missing values in the final file", H2),
              fig(FIG / "summary" / "field_fill_final.png",
                  caption="% of unique pictures / crops with a value, per field", max_h=5 * cm)]
    story += bullets([
        f"primary_colour is filled for {m['fill'].loc['All (merged)', 'primary_colour']:.0f}% "
        "of unique pictures / crops and "
        f"{cv.loc['All', 'pct_rows']:.0f}% of all {int(cv.loc['All', 'rows']):,} rows (real "
        "label or estimate); the rest stays empty on purpose.",
        "style is still empty everywhere, and season / usage come almost only from Fashion "
        "Product: these fields will need model predictions or team annotation.",
    ])
    story += [KeepTogether([Paragraph("Colour distribution", H2),
              fig(FIG / "summary" / "colour_final.png",
                  caption="Clothes only: real labels vs estimated colours", max_h=6 * cm)]),
              p(f"Black is {m['black']['label']:.1f}% of labelled clothes and "
                f"{m['black']['estimated']:.1f}% of clothes with an estimated colour. Our "
                "survey found that black dominates 84% of wardrobes. That is a share of "
                "wardrobes, not of items, so the numbers cannot be compared directly: black is "
                "well represented in every source, but the public data "
                "are probably more colourful than our users' wardrobes: the local test photos "
                "will show how much this matters.")]
    story.append(CondPageBreak(8 * cm))

    # --- local data collection (placeholders filled by the team)
    story += [h1("local", "Local data collection (in progress)"),
              p("Our own photos are the only data from the real DressMe setting: phone photos "
                "of second-hand and wardrobe items in Tunisia. They are used <b>only for the "
                "test set</b> (<font face='Courier'>source</font> = wardrobe / friperie; the "
                "split script enforces it) and are never committed or shared."),
              table([["Collection stream", "Target", "Protocol"],
                     ["Team and volunteer wardrobes", "500–1,000 items",
                      "The six team members and survey volunteers photograph their clothes in "
                      "real conditions (phone camera, home lighting, hanger / bed / floor)."],
                     ["Friperie sessions", "150–300 items", "Photos at the rack with the shop "
                      "owner's permission, reproducing Nour's 30-second scenario."],
                     ["Local garments", "50–100 items", "Traditional and occasion pieces "
                      "(jebba, kaftan, sefsari…) from family wardrobes."],
                     ["Fit-check subset", "50–100 items", "Garment laid flat next to an A4 "
                      "sheet for scale, plus tape measurements (chest, waist, length, inseam)."],
                     ["Near-duplicate pairs", "~100 pairs", "Similar items (same type and "
                      "colour) labelled duplicate / not duplicate."]],
                    widths=[4 * cm, 2.6 * cm, WIDTH - 6.6 * cm]),
              Spacer(1, 6),
              Paragraph("Consent and ethics", H2)]
    story += bullets([
        "Signed consent form for every contributor; photos can be withdrawn at any time.",
        "Faces blurred or cropped; no personal data beyond an anonymous contributor ID.",
        "No scraping of Instagram or Facebook sellers without explicit permission.",
        "Photos kept in the team's private storage and used only for this academic project.",
    ])
    story += [table([["Still to fix", "Plan"],
                     ["Labelling (who labels, double-check rule)", TODO],
                     ["Planned dates (collection plan: week 2 of the Phase 3 timeline)", TODO]],
                    widths=[7 * cm, WIDTH - 7 * cm]),
              Spacer(1, 8)]

    # --- decisions, quality, next steps
    story += [h1("decisions", "Team decisions (former REVIEW rows)"),
              table([["Topic", "Current rule", "Alternative"],
                     ["Indian ethnic wear (Fashion Product, Fashionpedia)", "<b>decided</b>: "
                      "removed (kurtas, kurtis, churidar, salwar, patiala, dupatta, sarees, "
                      "Nehru jackets…, plus every item with usage “Ethnic”)",
                      "map kurtas to tunic, Ethnic usage to formal"],
                     ["Swimwear (Fashion Product, Fashionpedia)", "<b>decided</b>: new "
                      "category swimwear (swimsuit, swim-shorts); swimming caps → accessory, "
                      "goggles dropped", "drop it"],
                     ["Kaftan (Fashionpedia)", "<b>decided</b>: traditional (close to the "
                      "Maghreb caftan)", "dress"],
                     ["Herringbone (Fashionpedia)", "<b>decided</b>: pattern left empty "
                      "(a fine zigzag weave, neither checked nor solid)", "checked or solid"],
                     ["Eyewear", "<b>decided</b>: sunglasses + eyeglasses merged",
                      "split (Kaggle only has sunglasses)"],
                     ["Metallic colours", "<b>decided</b>: not allowed for clothes "
                      "(estimates only)",
                      "allowed for all items"],
                     ["Colour confidence cut", f"<b>decided</b>: "
                      f"{used[0].replace(' ← used', '')} ({used[2]} accurate on Fashion "
                      f"Product; {hand_check})", "0.6: more colours, less accurate"],
                     ["PolyVore outfits sharing pictures", "kept, flagged outfit_clean = False",
                      "drop them from val / test"]],
                    widths=[4.3 * cm, 7 * cm, WIDTH - 11.3 * cm]),
              Spacer(1, 8),
              h1("risks", "Data quality risks and mitigations"),
              table([["Risk", "Mitigation"],
                     ["Class imbalance (shoes, tops vs dress, outerwear; 72 rare article types)",
                      "Coarse sub_categories, class weights / resampling at training"],
                     ["Estimated colours are noisy",
                      "Learned model, confidence cut, colour_source / colour_confidence kept"],
                     ["PolyVore duplicates (~24k)", "Same split per image_group; duplicate flag"],
                     ["Fashionpedia small crops (33.8% &lt; 64 px)",
                      "Filter by crop size for classification; no colour estimated"],
                     ["Outfit leakage", "outfit_split per outfit; outfit_clean for strict tests"],
                     ["Domain gap (catalogue vs phone photos)",
                      "Local wardrobe / friperie photos reserved for test"],
                     ["No traditional clothing", "Collect local photos (jebba, kaftan…)"],
                     ["Very few swimwear items (under 100)",
                      "Collect local photos (including modest swimwear)"]],
                    widths=[7 * cm, WIDTH - 7 * cm]),
              Spacer(1, 8),
              h1("next", "Next steps")]
    story += bullets([
        "Collect and label local wardrobe / friperie photos (test set, traditional items).",
        "Phase 4: train EfficientNet on <font face='Courier'>split</font> (without duplicates), "
        "compute FashionCLIP embeddings, and fit the compatibility formula on "
        "<font face='Courier'>outfit_split</font>.",
        "Once FashionCLIP embeddings exist, a colour model on top of them may beat the "
        "histogram model: compare on the same Fashion Product val / test images.",
        "Add DeepFashion2 and DressCode when access is granted.",
    ])


    story.append(PageBreak())
    story += [Paragraph("Appendix A — Project files", H1),
              p("<i>Datasets are used for non-commercial academic purposes only and are not "
                "redistributed.</i>"),
              table([["Path", "Content"],
                     ["src/phase3/eda_*.py", "EDA scripts → reports/phase3/eda_*.md, reports/phase3/figures/"],
                     ["src/phase3/map_*.py", "Mapping scripts → data/processed/*.csv"],
                     ["src/phase3/estimate_colours.py", "Colour model → data/processed/"
                      "colour_estimates.csv, reports/phase3/colour_estimation.md"],
                     ["src/phase3/merge_and_split.py", "Merge + splits → data/processed/dressme.csv"],
                     ["src/phase3/colour_utils.py", "Lab conversion and palette matching"],
                     ["mappings/*.csv", "All mapping rules, palette, sub_category vocabulary"],
                     ["src/phase3/make_colour_labelling_sheet.py", "Hand-labelling set (200 + 200 "
                      "items) and labelling page → data/interim/colour_labelling/"],
                     ["src/phase3/evaluate_colour_labels.py", "Accuracy on the hand labels → "
                      "reports/phase3/colour_validation.*"],
                     ["src/common/plot_style.py", "DressMe chart colours"],
                     ["src/phase3/build_phase3_report.py", "Builds this PDF"]],
                    widths=[5.5 * cm, WIDTH - 5.5 * cm])]
    story += [Spacer(1, 10), Paragraph("Appendix B — Code excerpts", H1)]
    for n, text in enumerate(APPENDIX, 1):
        story += [Paragraph(f"B.{n}", H3), inline_code(text)]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="DressMe — Phase 3 report", author="DressMe team")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    build()
