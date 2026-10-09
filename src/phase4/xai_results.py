"""
The headline numbers of the XAI evaluations, read from their reports (one reader,
so the jury report and Admin > Explainability always show the same numbers):

    reports/phase4/explanations_evaluation.md         item labels (evaluate_explanations.py)
    reports/phase4/outfit_explanations_evaluation.md  outfit scores (evaluate_outfit_explanations.py)
    reports/phase4/concepts_evaluation.md             concept probes (evaluate_concepts.py)

    results(root) -> {"labels": {...}, "outfits": {...}, "concepts": {...}}

Each block has `date` (the report file's date) and `command` (how to re-run it);
a report that is not there gives {"missing": True, "command": ...}.
"""

import re
from datetime import date

REPORTS = {
    "labels": ("explanations_evaluation.md", "python src/phase4/evaluate_explanations.py"),
    "outfits": ("outfit_explanations_evaluation.md", "python src/phase4/evaluate_outfit_explanations.py"),
    "concepts": ("concepts_evaluation.md", "python src/phase4/evaluate_concepts.py"),
}


def md_tables(text):
    """Every markdown table of a text, as a list of row dicts (cells as strings)."""
    tables, rows, header = [], None, None
    for line in text.splitlines() + [""]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else None
        if cells is None:
            if rows is not None:
                tables.append(rows)
            rows, header = None, None
        elif header is None:
            header, rows = cells, []
        elif all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue                                   # the |---|---:| line
        else:
            rows.append(dict(zip(header, cells)))
    return tables


def number(text):
    """'40.0% [35.7, 44.3]' -> 0.4; '0.875' -> 0.875; '1,234' -> 1234.0; 'too few' -> None."""
    m = re.search(r"-?[\d,]*\.?\d+", text)
    if not m:
        return None
    value = float(m.group().replace(",", ""))
    return value / 100 if "%" in text[m.end():m.end() + 1] else value


def labels(tables):
    flag = {}
    for row in tables[0]:
        flag.setdefault(row["field"], {"field": row["field"]})[f"{row['group']}_accuracy"] = number(row["accuracy"])
        if row["group"] == "unsure":
            flag[row["field"]]["unsure_share"] = number(row["share"])
    deletion = next(t for t in tables if t and "heatmap" in t[0])
    return {"flag": list(flag.values()),
            "deletion": [{"field": r["field"], "heatmap": number(r["heatmap"]),
                          "shifted_region": number(r["shifted_region"]),
                          "scattered_pixels": number(r["scattered_pixels"])}
                         for r in deletion if number(r["share"]) == 0.1]}


def outfits(tables):
    return {"rows": [{"dataset": r["dataset"], "outfits": int(number(r["outfits"])),
                      "hit": number(r["weakest = intruder"]), "chance": number(r["chance"]),
                      "points_add_up": r["points add up"]} for r in tables[0]]}


def concepts(tables, text):
    rows = [{"concept": r["concept"], "label": r["label"].strip("`"), "auc": number(r["AUC"]),
             "with_label": int(number(r["with the label"]))} for r in tables[0]]
    mean = re.search(r"Mean AUC over the \d+ checkable concepts: (\d+\.\d+)", text)
    return {"rows": rows, "mean_auc": float(mean.group(1)) if mean else None}


def results(root):
    """The numbers of the three XAI evaluation reports under root/reports/phase4/."""
    out = {}
    for key, (name, command) in REPORTS.items():
        path = root / "reports" / "phase4" / name
        if not path.exists():
            out[key] = {"missing": True, "command": command}
            continue
        text = path.read_text(encoding="utf-8")
        tables = md_tables(text)
        block = labels(tables) if key == "labels" else outfits(tables) if key == "outfits" \
            else concepts(tables, text)
        out[key] = {**block, "date": date.fromtimestamp(path.stat().st_mtime).isoformat(),
                    "command": command, "report": f"reports/phase4/{name}"}
    return out
