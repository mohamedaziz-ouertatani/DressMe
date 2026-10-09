# XAI jury report + Admin > Explainability — design (XAI sub-project 4 of 4)

Date: 2026-10-09. Status: implemented. Branch `xai-report` (from main, after #54).

## Goals

1. A standalone **XAI report** for the jury (`reports/phase4/xai_report.pdf` + `.md`):
   why XAI matters for DressMe, what each explanation does and how faithful it is,
   the results, app screenshots, limitations and the team's open decisions.
2. **Admin > Explainability**: the same evaluation numbers, the flag's behaviour on
   real uploads, Explainer / trace statistics, and editing `mappings/xai_settings.csv`.
3. The Phase 4 report's XAI section shortened to a summary pointing to the XAI report;
   sub-projects 3-4 marked done.

## Design

### `src/phase4/xai_results.py` (one reader for the PDF and the admin page)

- `md_tables(text)` → every markdown table of a report as a list of row dicts.
- `results(root)` → `{"labels", "outfits", "concepts"}`, each with `date` (the report
  file's date), `command` (how to re-run it) and its numbers:
  - labels: sure / unsure accuracy per field; deletion drops at 10 % (heatmap,
    shifted region, scattered pixels);
  - outfits: per dataset, weakest = intruder, chance, points add up;
  - concepts: AUC per checkable concept, mean AUC.
  A missing report gives `{"missing": true, "command": ...}`.

### `src/phase4/build_xai_report.py`

Reportlab, same helpers and look as `build_phase4_report.py`. Sections: why XAI;
overview table (explanation, method, where in the app, evidence); item labels;
outfit scores + buy verdicts; similarity + concepts; Explainer agent + chat trace;
limitations; open team decisions (every REVIEW row of `xai_settings.csv` and
`style_concepts.csv`). Charts in `reports/phase4/figures/xai/`, numbers from
`xai_results`. Screenshots (demo account) in `reports/phase4/figures/xai/screens/`,
copied from the browser checks. A `.md` version with the same text and tables.

### Backend: `routers/admin.py`

- `GET /admin/xai` → `{"evaluations": results(), "real_use": ..., "traces": ...,
  "settings": [...], "concepts": [...]}`:
  - **real_use** per field: items with stored alternatives, flagged unsure (team cuts
    from the settings folder), corrected-and-changed rate among unsure vs sure; plus
    the count of items analysed before the XAI layer (no alternatives).
  - **traces** over `days` (default 30): model answers with a trace, per tool:
    calls, errors (`error:` / `failed:`), agents; Explainer answers that called no tool.
  - **settings**: rows of `xai_settings.csv` (name, value, note); **concepts**: the
    concept list (read-only).
- `PUT /admin/xai/settings {values}` → writes `xai_settings.csv` in the settings
  folder (notes and order kept): `min_conf_*`, `margin`, `strength_*` in [0, 1];
  `near_miss`, `min_swap_gain` ≥ 0; unknown names → 422. Admin only.

### App: `admin/XaiPage.tsx`, tab "Explainability"

Four sections: evaluation cards (number, chance / baseline, date, re-run command),
real-use table, trace table, editable settings (like Formula, with notes and a
"commit the file" reminder after saving).

## Tests

`md_tables` / `results` on the real reports and on a missing file; `/admin/xai`
blocks on seeded items and chats; settings PUT (validation, file written in the
temporary mappings copy, notes kept); non-admin → 403.

## Changes while building

- The admin endpoints live in their own router (`routers/admin_xai.py`, same `/admin` prefix and
  admin guard): `routers/admin.py` was already 400+ lines.
- The admin page uses its own always-visible table; the shared `TableView` is a collapsed
  "show as a table" companion for charts.
- The chat-trace screenshot was retaken at native resolution (820 px viewport) to be readable in the PDF.
- No separate plan document: the work followed the existing admin / report patterns, task by task with tests.
