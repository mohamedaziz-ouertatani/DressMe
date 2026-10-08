# Explainer agent — design (XAI)

Date: 2026-10-08. Status: approved in chat. Builds on XAI sub-projects 1
(item labels, PR #49) and 2 (outfit score + buy advice, PR #50).

## Goal

A fifth DressMe chat agent, the **Explainer**, that answers "why?" questions
with tools on the user's real data: why an outfit scores what it does, what
would change it, why the app labelled a piece as it did, why a buy verdict,
and how the scoring works. It follows the existing agent pattern
(`backend/app/agents/`, `AGENTS.md`): a prompt + tools bound to the user,
picked by the router.

## Tools (`backend/app/agents/explainer.py`)

All read only the logged-in user's data; unknown or other users' ids are
ignored (an error dict, never another user's item).

| tool | returns |
|---|---|
| `list_wardrobe` | shared tool (item ids) |
| `explain_outfit(item_ids)` | score, points per part (`contributions`), strengths and problems as English facts, weakest piece + its best swap (from `/outfits/explain` logic, team `min_swap_gain`), the worst pair (lowest style or colour) |
| `what_if(item_ids, remove_id, add_id)` | score + points per part before and after the change, and the difference; a clash is reported, not scored |
| `explain_labels(item_id)` | per field (category, sub_category, pattern, colour): stored value, confidence, top 3 alternatives, unsure flag (team cuts), corrected by the user or not; `item_id="last_scan"` = the last analysed photo; for wardrobe items an `explain` chat action opening the "Why these labels?" panel |
| `explain_verdict()` | the last scan's verdict + `buy_explanation` (path, beats, lost_to, near misses, twins) |
| `how_scoring_works()` | the team's current weights, good-outfit and verdict thresholds, and the XAI cuts, read from the CSV files |

Strengths / problems are turned into short English sentences by one helper
(`fact(line)`) so the model never sees raw codes; it answers in the user's
language as the shared rules say.

## Prompt

Shared rules + job: explain DressMe's answers. Only state reasons found in a
tool result; model labels are guesses — give their confidence; if no tool
gives a cause, say it is not known; never invent a rule or a number. Other
agents' prompts learn the Explainer exists ("why?" questions go to it).

## Chat action `explain`

`{"kind": "explain", "url": "/wardrobe/<24-hex id>?why=1"}` — accepted by
`common.chat_actions` only in exactly that shape (like `sell`); the Chat page
shows "Open the explanation"; the item page opens its panel when `?why=1`.

## Routing

Agent description for the router; keywords in `mappings/agent_keywords.csv`
(REVIEW): why, explain, how does, score, pourquoi, explique, comment, 3lech,
alech, علاش (Darija rows marked "REVIEW: native check").

## App

Badge `agent_explainer` (Explainer / Explicateur / المفسّر), tool names
`tool_*` for the five new tools, the `explain` action button, `?why=1` on the
item page. en / fr / ar.

## Tests

Each tool on a wardrobe built through the API with the fakes; privacy (another
user's ids → error, nothing leaked); `what_if` clash; the `explain` action
filter rejects any other URL; the router sends "why …" to the Explainer by
keywords; the existing agent tests keep passing.

## Out of scope

Explainer conversations in the fine-tuning dataset (`build_chat_dataset.py`):
the Darija wording needs native review first.
