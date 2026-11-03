# Manual check: step 3d, the Stylist with a real model

Nothing changes on screen (the Assistant page is still the placeholder). The backend changed, so rebuild first:
`docker compose up -d --build backend`, wait about a minute. Ollama must run on the PC with `qwen3.5:4b` pulled
(`docs/superpowers/handoff/assistant-model.md`). Use your own account, with **some pieces in the wardrobe (8 or more is
best)**. Commands are for PowerShell, from the project root.

## A. Start-up

1. `docker compose logs backend | Select-String "assistant:"`. OK: `assistant: model qwen3.5:4b at
   http://host.docker.internal:11434; Ollama answered /api/show: yes`.
2. Open http://localhost:8000/docs, **Authorize** with a token from `POST /auth/login`. `GET /assistant/status` -> OK:
   `{"available": true, "model": "qwen3.5:4b"}`.

## B. Three questions (POST /chat, Try it out), each with a new body (no chat_id)

3. `{"message": "What should I wear today?"}`. OK: 200 after a few seconds (the first one after a while can take ~30 s:
   the model loads). `trace` lists `suggest_outfits` (often after `get_weather`), each with `"ok": true`. `answer` names
   pieces as `{1}`, `{2}`..., and every number in it is a key of `pieces`; each piece there is one of YOUR items.
4. `{"message": "Do I have a white shirt?"}` (or a piece you own). OK: `trace` has `search_wardrobe` with your words as
   `query`; the answer says yes with `{n}` only if `pieces` holds such a piece, and says so plainly when not.
5. `{"message": "Write my maths homework"}`. OK: a polite refusal, no tool in `trace`, `stop_reason` `answered`.
6. On the PC, `ollama ps`. OK: `qwen3.5:4b ... 100% GPU  8192 ...`.

## C. Ollama off

7. Quit Ollama (tray icon > Quit Ollama). Wait a minute (the status is remembered for 60 s).
8. `GET /assistant/status` -> OK: `{"available": false, ...}`. `POST /chat` -> OK: **503** `assistant_unavailable`.
   Open the app: Home, Dress, Wardrobe still work.
9. Start Ollama again (Start menu > Ollama). After a minute `GET /assistant/status` says `true` again and `POST /chat` works.
