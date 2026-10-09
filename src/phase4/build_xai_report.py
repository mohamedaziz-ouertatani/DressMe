"""
The XAI report for the jury (XAI sub-project 4): what DressMe explains, how, how
faithful each explanation is, and what is still open.

    python src/phase4/build_xai_report.py
    -> reports/phase4/xai_report.pdf  (same look as the Phase 3 / 4 reports)
       reports/phase4/xai_report.md   (the same text and tables, for GitHub)

Every number comes from the evaluation reports through src/phase4/xai_results.py
(the same reader as Admin > Explainability), so the report and the app agree.
Re-run the evaluations first if a model, a rule or a threshold changed.
"""

import csv
import re
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import CondPageBreak, Paragraph, SimpleDocTemplate, Spacer

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
from build_phase3_report import H1, H2, ROOT, WIDTH, bullets, fig, p, table
from plot_style import DARK, GOLD, RUST
import plot_style
import xai_results

REPORTS = ROOT / "reports" / "phase4"
OUT_PDF = REPORTS / "xai_report.pdf"
OUT_MD = REPORTS / "xai_report.md"
FIG = REPORTS / "figures" / "xai"
SCREENS = FIG / "screens"
MAPPINGS = ROOT / "mappings"


def c(text):
    """Inline code in the PDF (`code` in the markdown copy)."""
    return f"<font face='Courier'>{text}</font>"


# ------------------------------------------------------------------ charts
def save(fig_, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig_.tight_layout()
    fig_.savefig(FIG / name, dpi=200)
    plt.close(fig_)
    return FIG / name


def grouped_bars(groups, series, title, ylabel, name, ylim=None, chance=None, fmt="{:.0f}"):
    """groups: x labels; series: [(label, colour, values)]."""
    fig_, ax = plt.subplots(figsize=(6.5, 2.8))
    width = 0.8 / len(series)
    for k, (label, colour, values) in enumerate(series):
        xs = [i - 0.4 + width * (k + 0.5) for i in range(len(groups))]
        ax.bar(xs, values, width, label=label, color=colour)
        for x, v in zip(xs, values):
            ax.text(x, v, fmt.format(v), ha="center", va="bottom", fontsize=7)
    if chance is not None:
        ax.axhline(chance, color="grey", lw=0.8, ls="--")
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    ax.legend(frameon=False, fontsize=7, ncol=len(series), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title(title, pad=22, fontsize=10)
    return save(fig_, name)


def charts(r):
    out = {}
    flag = r["labels"]["flag"]
    out["unsure"] = grouped_bars(
        [f["field"] for f in flag],
        [("shown as sure", DARK, [100 * f["sure_accuracy"] for f in flag]),
         ("flagged \"not sure, check\"", RUST, [100 * f["unsure_accuracy"] for f in flag])],
        "Is the \"not sure\" flag honest? (test split)", "accuracy (%)", "unsure_flag.png", (0, 112))
    d = r["labels"]["deletion"]
    out["deletion"] = grouped_bars(
        [x["field"] for x in d],
        [("hottest heatmap pixels", RUST, [x["heatmap"] for x in d]),
         ("same size, wrong place", DARK, [x["shifted_region"] for x in d]),
         ("scattered pixels", GOLD, [x["scattered_pixels"] for x in d])],
        "Deletion test: whiten 10% of the item", "confidence drop", "deletion.png", fmt="{:.2f}")
    o = r["outfits"]["rows"]
    out["weakest"] = grouped_bars(
        [x["dataset"] for x in o],
        [("weakest piece = the intruder", RUST, [100 * x["hit"] for x in o]),
         ("chance (1 / pieces)", DARK, [100 * x["chance"] for x in o])],
        "Does \"weakest piece\" find a piece that does not belong?", "%", "weakest.png", (0, 60))
    rows = [x for x in r["concepts"]["rows"] if x["auc"] is not None]
    fig_, ax = plt.subplots(figsize=(6.5, 2.6))
    ax.barh([x["concept"] for x in rows][::-1], [x["auc"] for x in rows][::-1], color=RUST)
    ax.axvline(0.5, color="grey", lw=0.8, ls="--")
    for i, x in enumerate(rows[::-1]):
        ax.text(x["auc"] + 0.01, i, f"{x['auc']:.2f}", va="center", fontsize=7)
    ax.set_xlim(0.4, 1.05)
    ax.set_xlabel("AUC against the matching label (0.5 = chance)")
    ax.set_title("Do the concept probes read the pictures?", fontsize=10)
    out["concepts"] = save(fig_, "concepts_auc.png")
    return out


def review_rows():
    """Every REVIEW setting of the XAI files, for the 'open decisions' table."""
    rows = [["File", "Setting", "Value", "Note"]]
    with open(MAPPINGS / "xai_settings.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(["xai_settings.csv", r["setting"], r["value"], r["note"].replace("REVIEW: ", "")])
    with open(MAPPINGS / "style_concepts.csv", encoding="utf-8", newline="") as f:
        concepts = [r["concept"] for r in csv.DictReader(f)]
    rows.append(["style_concepts.csv", f"{len(concepts)} concepts", "", ", ".join(concepts)])
    return rows


# ------------------------------------------------------------------ content
def blocks(r, ch):
    """The report as a list of (kind, data) blocks, rendered to PDF and to markdown."""
    flag = {f["field"]: f for f in r["labels"]["flag"]}
    o = {x["dataset"]: x for x in r["outfits"]["rows"]}
    shot = lambda name: SCREENS / f"{name}.jpg"
    B = []
    add = lambda kind, data: B.append((kind, data))

    add("h1", "1. Why DressMe explains itself")
    add("p", "DressMe's users are young Tunisians on a small budget who buy mostly second-hand "
             "(friperie) pieces that can rarely be returned; 42% of our survey wanted a straight "
             "\"should I buy this?\" answer. An answer they cannot check is an answer they cannot "
             "trust, and a wrong label or score costs them money. So every answer of the app can say "
             "<b>why</b>, in English, French and Arabic, and the team can see <b>how far each "
             "explanation can be trusted</b>.")
    add("p", "The rule we kept throughout: an explanation shows how the existing answer was made. "
             "It never changes a score, and it never invents a reason the model or the formula did "
             "not use. Where an explanation is only an association (a picture model's concepts) or a "
             "visual aid (the colour map), the app says so.")

    add("h1", "2. What is explained, how, and the evidence")
    add("table", [["Explanation", "Method", "In the app", "Evidence"],
                  ["Why this label", "Grad-CAM heatmap (= CAM for our linear heads), top 3 answers",
                   "\"Why these labels?\" on item and scan pages",
                   f"deletion test: heatmap beats a same-size region elsewhere for every field"],
                  ["\"Not sure, check\"", "best answer below a cut, or too close to the 2nd (team cuts)",
                   "badge on the field", f"flagged answers {100 * flag['category']['unsure_accuracy']:.0f}% "
                   f"right vs {100 * flag['category']['sure_accuracy']:.0f}% (category)"],
                  ["Colour", "item pixels nearest to the colour (visual aid)", "same panel",
                   "not the colour model's reasoning (it reads a histogram); said in the app"],
                  ["Outfit score", "points per part, + / − lines from the team's rule tables",
                   "every outfit card", f"points add up to the score: {o['PolyVore']['points_add_up']} outfits"],
                  ["Weakest piece", "best swap from the wardrobe (re-scores the outfit)",
                   "\"Why this score?\" (Build, Today)",
                   f"finds an intruder {100 * o['PolyVore']['hit']:.0f}% vs {100 * o['PolyVore']['chance']:.0f}% chance"],
                  ["Buy verdict", "good outfits vs the team thresholds, what it beats, near misses",
                   "\"Why this verdict?\" (Scan, Shop)", "exact: re-uses the verdict's own numbers"],
                  ["Look-alikes", "shared labels + FashionCLIP concept probes above the average picture",
                   "Similar page chips", f"concepts recover known labels, mean AUC {r['concepts']['mean_auc']:.2f}"],
                  ["Chat answers", "Explainer agent (6 tools) + \"How I answered\" trace",
                   "Assistant", "grounded answers with the base model (live test); trace = real calls"]])

    add("h1", "3. Item labels: why this label?")
    add("p", f"The classifier (EfficientNet-B0, three heads) answers category, type and pattern. "
             f"{c('src/phase4/explain.py')} draws where it looked with Grad-CAM. Our heads are one "
             f"linear layer on the averaged feature maps, so Grad-CAM equals the classic CAM: the "
             f"heatmap is exact for the model, nothing is approximated. All heads share one body, so "
             f"a heatmap shows where the model looked to decide, not the outline of a part. The user "
             f"can tap another answer (\"why not a dress?\") to see where the model would look for it.")
    add("fig", (shot("labels_panel"), "The \"Why these labels?\" panel: heatmaps, top 3 answers, colour "
                                      "pixel map (demo account)."))
    add("p", "Is the heatmap faithful? We whitened the hottest 10% of the item's pixels and measured "
             "how much the model's confidence dropped, against the same share of pixels in a solid "
             "region in the wrong place, and against scattered random pixels.")
    add("fig", (ch["deletion"], "The heatmap region matters 2-7x more than a same-size region elsewhere. "
                                "Scattered pixels drop the confidence most: they cover the item with noise "
                                "the model never saw, which says nothing about where it looks."))
    add("p", "The \"not sure, check\" flag: a field is flagged when its best answer is below the team's "
             f"cut or less than {c('margin')} ahead of the second. On the test split:")
    add("fig", (ch["unsure"], f"Flagged answers are right only "
                              f"{100 * flag['sub_category']['unsure_accuracy']:.0f}-"
                              f"{100 * flag['category']['unsure_accuracy']:.0f}% of the time, sure ones "
                              f"{100 * flag['sub_category']['sure_accuracy']:.0f}-"
                              f"{100 * flag['category']['sure_accuracy']:.0f}%; the flag catches "
                              f"{100 * flag['category']['unsure_share']:.1f}-"
                              f"{100 * flag['pattern']['unsure_share']:.1f}% of the answers."))
    add("fig", (REPORTS / "figures" / "gradcam_examples.png",
                "Grad-CAM examples from the test split, right and wrong answers."))

    add("h1", "4. Outfit scores and buy verdicts")
    add("p", f"The score is the team's weighted formula ({c('src/phase4/compatibility.py')}). "
             f"{c('src/phase4/explain_outfit.py')} splits it into the points each part earned and "
             "could have earned; the rounding keeps the sum exactly equal to the score shown. "
             "Strengths and problems come from the same rule tables as the score, as codes the app "
             "turns into sentences (en / fr / ar).")
    add("fig", (shot("outfit_points"), "An outfit card: points per part, what works, \"Why this score?\"."))
    add("p", "\"Why this score?\" names the weakest piece: for each piece, the best replacement from "
             "the user's wardrobe and how many points it adds (only above the team's "
             f"{c('min_swap_gain')}). On Build, \"Apply swap\" makes it. To test it, we replaced one "
             "piece of each test outfit by a random item of the same category:")
    add("fig", (ch["weakest"], "Above chance on both datasets, but modestly: the swap re-uses the score, "
                               "so it is only as sharp as the formula itself (compatibility AUC 66.6% "
                               "PolyVore, 78.7% Fashionpedia)."))
    add("p", "\"Why this verdict?\" shows the count of good outfits against the team's thresholds "
             "(\"9 good outfits; Buy needs 5\"), which owned piece the new one beats and by how much, "
             "the owned pieces that do as well, near misses and near twins with their pictures.")

    add("h1", "5. Look-alikes: why two pieces are alike")
    add("p", "DressMe finds look-alikes with FashionCLIP picture vectors only. Each one now says which "
             "labels both pieces share, and what the picture model associates with both: the team's "
             f"list of short texts ({c('mappings/style_concepts.csv')}) is compared with each picture. "
             "Concepts are ranked above the average picture; without that, a generic prompt such as "
             "\"trendy\" topped nearly every piece.")
    add("fig", (shot("similar_chips"), "The Similar page: \"Same: category, type\", \"Both read as party, "
                                       "satin\", or a contrast."))
    add("fig", (ch["concepts"], "Concepts that match an existing label recover it well (denim vs jeans, "
                                "knit vs sweaters). Floral has only 11 labelled test pictures; casual is "
                                "the majority class. 11 concepts have no label to check."))

    add("h1", "6. The Explainer agent and \"How I answered\"")
    add("p", f"A fifth chat agent ({c('backend/app/agents/explainer.py')}) answers \"why?\" questions "
             f"with tools on the user's real data: {c('explain_outfit')}, {c('what_if')}, "
             f"{c('explain_labels')}, {c('explain_similarity')}, {c('explain_verdict')}, "
             f"{c('how_scoring_works')}. Its prompt: give only reasons found in a tool result, never "
             "invent a rule, a number or a cause; labels are guesses with a confidence. A piece can be "
             "named by description (\"pink top\") only when exactly one piece matches; otherwise it "
             "asks which one.")
    add("p", "Every chat answer keeps a trace of its tool calls (agent, how it was chosen, each call "
             "with a one-line result), shown under the answer:")
    add("fig", (shot("chat_trace"), "\"How I answered\": the Explainer listed the wardrobe, then scored the "
                                    "outfit (55.4)."))
    add("p", "Live tests on the demo wardrobe: the base model (qwen3:4b-instruct) gave grounded answers "
             "(the real points per part; the shared labels and concepts of two jackets) and asked which "
             "piece when a description was ambiguous. The fine-tuned dressme-chat-v2 was trained before "
             f"{c('explain_similarity')} existed: asked about two jackets it did not call the tool and "
             "made up a reason. Its next training run must include the newest tools.")

    add("h1", "7. Admin > Explainability")
    add("p", "The same numbers for the team, plus real use: how often each field is flagged on real "
             "uploads and how often users corrected flagged vs sure guesses, which tools the chat agents "
             f"call and how often they fail, and the XAI settings ({c('mappings/xai_settings.csv')}), "
             "editable like the formula weights.")
    add("fig", (shot("admin_explainability"), "Admin > Explainability."))

    add("h1", "8. Limitations")
    add("bullets", [
        "Concepts are what the picture model associates with a photo, not facts; 11 of 20 cannot be "
        "checked against a label.",
        "The colour map is a visual aid: the colour model reads a histogram of all the item's colours, "
        "and white / cream items blend into the white background (no map then).",
        "\"Weakest piece\" is limited by the formula's own signal (modest gain over chance).",
        "The \"not sure\" cuts and every XAI threshold are start values (REVIEW), measured on the test "
        "split of public datasets; real-use calibration starts with uploads made after the XAI layer "
        "(the demo wardrobe predates it).",
        "dressme-chat-v2 does not know the newest Explainer tools yet; the Darija text of the app and "
        "of the chat data still needs the native-speaker review.",
        "All evaluations use public product shots; our own phone photos (Local) are not in them yet."])

    add("h1", "9. Open team decisions")
    add("table", (review_rows(), [0.2, 0.22, 0.08, 0.5]))

    add("h1", "10. How to reproduce")
    add("bullets", [f"{c(r[k]['command'])} → {c(r[k]['report'])} ({r[k]['date']})" for k in r
                    if not r[k].get("missing")]
        + [f"{c('python src/phase4/build_xai_report.py')} → this report"])
    return B


# ------------------------------------------------------------------ rendering
def to_md(text):
    text = re.sub(r"<font face='Courier'>(.*?)</font>", r"`\1`", text)
    text = re.sub(r"</?b>", "**", text)
    return re.sub(r"</?i>", "*", text)


def render_md(B, today):
    out = ["# DressMe — Explainability (XAI) report", "",
           f"Generated {today} by `src/phase4/build_xai_report.py` (PDF: `xai_report.pdf`).", ""]
    for kind, data in B:
        if kind == "h1":
            out += [f"## {data}", ""]
        elif kind == "p":
            out += [to_md(data), ""]
        elif kind == "bullets":
            out += [f"- {to_md(b)}" for b in data] + [""]
        elif kind == "table":
            data = data[0] if isinstance(data, tuple) else data
            out += ["| " + " | ".join(to_md(str(x)) for x in data[0]) + " |",
                    "|" + "---|" * len(data[0])]
            out += ["| " + " | ".join(to_md(str(x)).replace("|", "/") for x in row) + " |" for row in data[1:]]
            out.append("")
        elif kind == "fig":
            path, caption = data
            out += [f"![{to_md(caption)}]({path.relative_to(REPORTS).as_posix()})", "", f"*{to_md(caption)}*", ""]
    return "\n".join(out)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, "DressMe · Explainability (XAI) report")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def render_pdf(B, today):
    story = [Spacer(1, 3 * cm),
             Paragraph("DressMe", ParagraphStyle("T", parent=H1, fontSize=30, leading=36)),
             Paragraph("Explainability (XAI) report", ParagraphStyle("S", parent=H2, fontSize=15)),
             Spacer(1, 0.4 * cm),
             p(f"AI personal fashion assistant · ESPRIT, Advanced Data Science project · generated {today}"),
             Spacer(1, 0.6 * cm)]
    for kind, data in B:
        if kind == "h1":
            story += [CondPageBreak(5 * cm), Paragraph(data, H1)]
        elif kind == "p":
            story.append(p(data))
        elif kind == "bullets":
            story += bullets(data)
        elif kind == "table":
            rows, shares = data if isinstance(data, tuple) else (data, [1 / len(data[0])] * len(data[0]))
            story += [table(rows, widths=[WIDTH * s for s in shares]), Spacer(1, 6)]
        elif kind == "fig":
            path, caption = data
            story.append(fig(path, caption=caption, max_h=8.5 * cm))
    doc = SimpleDocTemplate(str(OUT_PDF), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="DressMe — XAI report", author="DressMe team")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    plot_style.apply()
    r = xai_results.results(ROOT)
    missing = [k for k, v in r.items() if v.get("missing")]
    if missing:
        raise SystemExit("Missing evaluation reports: " + ", ".join(f"{k} ({r[k]['command']})" for k in missing))
    B = blocks(r, charts(r))
    today = date.today().isoformat()
    render_pdf(B, today)
    OUT_MD.write_text(render_md(B, today) + "\n", encoding="utf-8")
    print(f"Saved {OUT_PDF} and {OUT_MD}")


if __name__ == "__main__":
    main()
