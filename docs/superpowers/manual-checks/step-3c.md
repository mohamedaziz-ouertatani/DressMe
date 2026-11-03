# Manual check: step 3c, the walking skeleton of the assistant

Nothing changes on screen in this step (the Assistant page is still the "being rebuilt" placeholder). The checks are about the
start-up and the API. The backend changed, so rebuild first: `docker compose up -d --build backend`, wait about a minute.
Commands are for PowerShell, from the project root.

## A. A broken `agents.yaml` stops the start-up with a clear message

1. Open `mappings/agents.yaml`. Under `stylist` > `tools:` add a line `      - teleport` (same indent as `- list_wardrobe`). Save.
2. Restart the backend: `docker compose restart backend`, then read the end of its log: `docker compose logs --tail 15 backend`.
   OK: the log ends with `AgentsConfigError: agents.yaml: agent 'stylist', field 'tools': tool 'teleport' is not registered
   (known tools: list_wardrobe)` and the container does not become healthy (`/health` does not answer).
3. Remove the line you added (or `git checkout mappings/agents.yaml`), restart again. OK: the backend starts normally
   (`Invoke-RestMethod http://localhost:8000/health` says `ok` after about a minute).
4. Optional, other messages: delete the `instructions:` line of `stylist` -> `agent 'stylist', field 'instructions': Field
   required`. Set `max_rounds: 7` -> `... 7 is above limits.max_rounds (6)`. Revert each time.

## B. The route is there and says "not available"

5. Open http://localhost:8000/docs. OK: a section **assistant** with **POST /chat**, body `message` (1 to 1000 characters),
   optional `chat_id` and `agent`.
6. Log in from the docs page (Authorize, with a token from `POST /auth/login`), then **Try it out** with
   `{"message": "What can I wear?"}`. OK: **503** and `{"detail": "assistant_unavailable"}`. (No model is plugged in yet: that is
   step 3d. Nothing is saved.)
7. With `{"message": ""}` OK: 422. With `"agent": "wizard"`: 422 `unknown_agent`.

## C. Nothing else moved

8. Open the app: Home, Dress, Wardrobe, Buy? work as before; the Assistant page still shows "The assistant is being rebuilt".
9. Admin > Overview still loads (the new event type `assistant` has no events yet).
