# Final measurement of the chat assistant

The numbers for the results section. Run this once, on the PC (Ollama with the chat model on), after the last change
to the assistant. **Do not change any prompt, description, example or check between the runs**, and do not tune on what
you see: a fail on the fresh questions is a result, not something to fix before reporting.

Total time: about 1 h 15 min (mostly the 10-run English trap set). Run the long ones as separate processes with a log.

## 0. Prepare (PowerShell, in the DressMe folder)

```powershell
git pull
docker compose up -d --build backend
docker inspect -f "{{.State.Health.Status}}" dressme-backend-1     # repeat until: healthy
ollama ps                                                             # the model loads on the first question
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q  # full suite once (~3 min)
mkdir bench\results\final                                              # the reports of this measurement
```

Write down: the commit (`git log --oneline -1`) and the `CHAT_MODEL` in `backend/.env`.

## 1. Fresh questions (never tuned on): 36 questions x 5 runs, all languages (~15 min)

`bench/assistant/final_questions.yaml`: 6 per agent area (stylist, wardrobe analyst, explainer, seller, shopping,
general + safety); en 20, fr 8, ar 5, arabizi 3.

```powershell
docker exec -d dressme-backend-1 sh -c "python -m app.eval_traps --traps /app/bench/assistant/final_questions.yaml --lang all --repeat 5 --out /app/bench/results/final > /app/bench/results/final/fresh.log 2>&1"
```

Follow it with `Get-Content bench\results\final\fresh.log -Wait`.

## 2. The full trap set, English, 10 runs (~35 min)

All 6 agents' traps together, the first time since 3e.2 (`--lang en` is the default).

```powershell
docker exec -d dressme-backend-1 sh -c "python -m app.eval_traps --repeat 10 --out /app/bench/results/final > /app/bench/results/final/traps-en.log 2>&1"
```

## 3. French and Arabic, measured once (~10 min)

Only `en` was ever run before. 3 runs each, so one bad answer does not decide the number.

```powershell
docker exec -d dressme-backend-1 sh -c "python -m app.eval_traps --lang fr,ar,arabizi --repeat 3 --out /app/bench/results/final > /app/bench/results/final/traps-fr-ar.log 2>&1"
```

## 4. The router's held-out test split (~1 min)

```powershell
docker exec dressme-backend-1 python -m app.eval_router --split test --repeat 5 --out /app/bench/results/final
```

## 5. Read, then write the numbers down

`bench/results/` is not in git, so copy the numbers into `docs/superpowers/handoff/chat-assistant-state.md` (results
table, one row per run, with the report file name) and the presentation. For each report:

| Run | Answers passed | Questions passing every run | Made-up numbers | Router accuracy | Handoffs | Report |
| --- | --- | --- | --- | --- | --- | --- |
| Fresh questions, all languages x5 | | | | | | `final/traps-...` |
| Full trap set, en x10 | | | | | | |
| Trap set, fr + ar + arabizi x3 | | | | | | |
| Router test split x5 | n/a | n/a | n/a | | n/a | `router-...` |

Also read the answers, not only the checks (the reports list a `review` line per question): two automatic checks were
wrong before. Fill the human review column for at least the fresh questions, and note per language how often the
answer came in the wrong language. The Darija / Arabizi lines then go to a native speaker
(`bench/assistant/darija_review.md`).

The luck threshold still holds: a difference under about 4 of 10 runs is noise.
