# Step 3a: remove the old chat

Branch `upgrade/step-3a-remove-old-chat`, from `origin/main` (`2bf5798`). Local only, nothing pushed.
Facts: `docs/superpowers/discovery/2026-10-25-step3-facts.md`. Baseline: 412 collected, 409 passed, 3 skipped.

**Goal:** delete the whole old chat (engine, router, five agents, Ollama / Gemini, fine-tune scripts, the
`dressme-chat-v4` model files' wiring) so the new Ask flow (steps 3b to 3h) is built on clean ground. Nothing of
the old chat is reused later: not its code, prompts, tool designs, training data or model. The code stays readable
only through the git tag `pre-chat-removal`.

**The one exception to "nothing is removed":** `POST /chat`, `GET /chat/history`, `DELETE /chat/history`, the
`chat` count of `GET /admin/stats`, and the `traces` part of `GET /admin/xai`. No other endpoint or field is
removed or retyped.

## Part 0: done before any deletion

| What | Result |
|---|---|
| Safety tag | `pre-chat-removal` on `d64479e` (the branch tip after cherry-picking the facts file) |
| Main reset | local `main` `1a07881` kept as `backup/main-before-reset-2026-10-25`; `main` is now `origin/main` `2bf5798` (the diff was `SETUP.md` only) |
| DB backup | `backups\dressme-20261025-164031.archive.gz` (git-ignored by `.gitignore:39 backups/`) |
| Sensitive files | PASS: no tracked file under `data/` or `backups/`, no tracked `.env`, no dumps or weights; only tracked file over 5 MB is `reports/phase3/phase3_report.pdf` (7.6 MB, a project deliverable) |
| Usage check | see the table below |

### Usage check: what outside the chat uses what is planned for deletion

| Planned for deletion | Used outside the old chat? | Decision |
|---|---|---|
| `chat_engine.py`, `agents/*`, `routers/chat.py`, `ChatMessage` | `main.py`, `conftest.py`, the chat tests, `src/phase4` chat scripts (all deleted or edited here) | delete |
| `resale.py`, `resale_pricing.csv`, `test_resale.py` | only `agents/seller.py`, `test_resale.py`, `build_chat_dataset.py`; a word in `build_phase4_report.py` text | delete |
| `agent_keywords.csv` | only `agents/router.py` | delete |
| `google-genai` | imported only in `chat_engine.py` (lazy); pins in `backend/requirements.txt` and `docker/constraints.txt` | delete; transitive pins removed only if they vanish from `pip freeze` after the rebuild |
| `httpx` | `weather.py:83`, `seed_demo.py:20`, and also `gradio_client` | **KEEP** |
| `currency_rates.csv` | `src/phase4/connectors/sitemap.py:35` | **KEEP** (not chat) |
| `listing_out`, `listing_query`, `SELLERS`, `shop_name`, `ListingIndex.search(exclude_seller=)` | `routers/listings.py`, `routers/admin.py`, screens | **KEEP** (only a comment changes) |
| `explain_outfit.py`, `explain_similarity.py`, `explain.py`, `wardrobe_counts`, `routers.outfits` helpers, `weather.py`, `compatibility.py` | screens and routes | **KEEP, untouched** |
| `?why=1` on the item page, the `/sell` prefill | normal screens | **KEEP** |
| `requirements-llm.txt` (unsloth, not in the brief) | nothing in the app; a pip list for fine-tuning | **KEEP**, only its header comment loses the dead pointers to `LLM.md` and `kaggle/chat_finetune/` |
| `scripts/check_demo.ps1` Ollama check (not in the brief) | its only job is "the chat is off without Ollama" | remove that check (chat-specific); 3f adds its own |
| `build_phase3_report.py`, `build_phase4_report.py`, `build_xai_report.py` (not in the brief) | they generate the dated Phase 3 / 4 / XAI reports and describe the chat as it was | **KEEP**; they read `chat_evaluation.json` only if present. Flagged in the report for a later clean-up |
| `docs/superpowers/plans|specs|discovery` and `HANDOFF.md` body | dated design records | **KEEP**; `HANDOFF.md` gets a one-line banner |

## Commits (small, in this order)

1. **plan** (this file).
2. **backend**: delete `chat_engine.py`, `agents/`, `routers/chat.py`, `resale.py`, `ChatMessage`; `main.py` builds no engine
   and `create_app` loses `chat_engine`; `config.py` loses the chat settings; `db.py` loses the `chats` index and the
   `"chats"` entry of `USER_COLLECTIONS`; `events.py` loses `"chat"`; `admin_xai.py` loses `trace_stats` and the
   `traces` key; comments that name the chat are reworded; `google-genai` leaves `requirements.txt`; mappings
   `agent_keywords.csv`, `resale_pricing.csv` deleted.
3. **tests**: delete `test_chat`, `test_agents`, `test_explainer_agent`, `test_seller_agent`, `test_chat_trace`,
   `test_chat_dataset`, `test_resale`; `conftest.py` loses `FakeChatEngine` and the argument; `test_deletion_complete`,
   `test_admin`, `test_admin_xai` lose their chat parts. Run the suite in the container.
4. **frontend**: delete `ChatPage.tsx`, the chat API calls, types and chat-only i18n keys; `DayStats.chat` optional;
   XaiPage trace section replaced by a `TODO(step 3g)`; new `AssistantPage` placeholder at `/assistant`, `/chat`
   redirects; Home's row and the nav point to `/assistant`.
5. **settings and Docker**: `.env.example`, `docker-compose.yml`, `docker/setup.ps1`, `docker/constraints.txt`,
   `scripts/check_demo.ps1`, `requirements-llm.txt` header, `src_path.py` comments.
6. **training, reports, docs**: `kaggle/chat_finetune/`, the seven `src/phase4` chat scripts, the four chat reports,
   `AGENTS.md`, `LLM.md`; `DEMO.md` step 6 and its rows (renumbered); `README.md`, `SETUP.md`, `LISTINGS.md`,
   `PRODUCT.md`, `CLAUDE.md` (old-chat mentions out, GPU line fixed to the RTX 4070 Laptop, 8 GB); `HANDOFF.md` banner.
7. **docs for the step**: `manual-checks/step-3a.md`, `docs/learn/step-3a.md`.

## Verification

- Grep the repo for the old names (the list in the brief) and explain each remaining hit.
- Goldens: `git diff` on `backend/tests/golden` is empty. Deletion test passes.
- Rebuild (requirements changed): `docker compose up -d --build backend`, wait about a minute, run the suite in the container.
- `npm run lint` and the build (typecheck + `vite build`).
- `http://localhost:8000/openapi.json`: no `/chat` path, every other path still there (compared with the paths before).
- Drop the `chats` collection in `dressme` (2 documents, backed up) and in `dressme_test` if it exists; admin stats loaded by hand with an old `chat` event in `events`.
- `git show pre-chat-removal:backend/app/chat_engine.py` still works.
- Fast-forward the branch into local `main`.

## As built

| Commit | What |
|---|---|
| plan | this file |
| `backend:` | the chat code, `resale.py`, two mappings, the wiring, **and the 109 chat tests + `test_trace_stats`** (one commit: the suite is red without them) |
| `frontend:` | `ChatPage` and its API / types / 40 i18n keys out, `AssistantPage` in, `/chat` redirects |
| `settings and Docker:` | `.env.example`, compose, `setup.ps1`, `check_demo.ps1`, 11 constraint pins, two comments |
| `training scripts, chat reports and docs:` | 15 files deleted, 8 docs edited |
| `docs for the step` | `manual-checks/step-3a.md`, `docs/learn/step-3a.md`, this section |

Decisions taken inside the brief's room (listed in the final report): `check_demo.ps1` lost its Ollama check;
`requirements-llm.txt` kept; the two chat figures and the three report builders kept; `extra_hosts` removed (only Ollama
used it); `days` of `GET /admin/xai` kept as an unused parameter (TODO(step 3g)); two tests the brief did not list were
edited (`test_promote_decisions.py` asserted a `chat` total, `test_outfits.py` had "chat" in a test name).

Results: 302 collected (412 - 110), 299 passed, 3 skipped before and after the rebuild; goldens identical to the tag;
`npm run lint` 0 warnings, `npm run build` passes; routes 70 -> 67 (only the 3 chat ones); `chats` dropped in `dressme`
(2 documents) and absent in `dressme_test`.