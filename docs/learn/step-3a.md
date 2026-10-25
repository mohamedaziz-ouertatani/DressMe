# Step 3a, in plain words: removing the old chat

## 1. What was removed, and why
- The old chat: a chat engine (it talked to Gemini in the cloud or to a small model on our PC through Ollama), five
  "agents" (each is a prompt plus a few functions the model may call, called **tools**), the three `/chat` endpoints,
  the chat page, its tests, the training scripts and reports of the `dressme-chat` models, and the Docker / `.env` lines.
- Why: I rebuild the Ask flow and the assistant myself, from zero, in steps 3b to 3h. A clean base is easier to explain
  than a chat I did not design.

## 2. What the app looks like now
- The **Assistant** tab still exists. It opens `/assistant`: a small page that says **"The assistant is being rebuilt"**,
  with a button to Dress. It works in English, French and Arabic (right to left). `/chat` sends you there.
- Everything else (Home, Dress, Buy?, Shops, Wardrobe, Admin) works as before. The only things gone from the API:
  `POST /chat`, `GET /chat/history`, `DELETE /chat/history`, the `chat` count in the admin stats and the chat part
  of the Explainability page.

## 3. The files that changed most
- `backend/app/chat_engine.py` (282 lines): turned our Python functions into tools and asked Gemini or Ollama to use them.
- `backend/app/agents/` (8 files, about 860 lines): the five agents, their prompts, their tools and the router that
  picked one per message.
- `backend/app/routers/chat.py` (82 lines): the three endpoints and the saved history.
- `frontend/src/pages/ChatPage.tsx` (187 lines): the chat screen. Now `AssistantPage.tsx` (25 lines) is in its place.
- `backend/app/main.py` and `backend/tests/conftest.py`: the app used to build a chat engine at start-up and every
  test passed a fake one. Both are gone.

## 4. Reading the old code through the tag
A **git tag** is a name pinned to one commit. `pre-chat-removal` is pinned just before the deletions.
```
git show pre-chat-removal:backend/app/chat_engine.py | more      # read one old file
git tag                                                          # lists pre-chat-removal
```

## 5. Five teacher questions
- **Why delete the old chat instead of fixing it?** The new assistant works differently from the start (my own tools,
  my own training data, my own model), so fixing would mean keeping design choices I did not make and cannot explain.
- **How do you know nothing was forgotten?** I searched the whole repository for 16 old names: no code, config or script
  still uses them. The tests pass (302 collected, 299 passed, 3 skipped), the golden answers are unchanged, the build
  and lint pass, and the list of API routes lost exactly the 3 chat ones (70 to 67).
- **How can you get the old code back?** From the tag (`git show pre-chat-removal:<path>`), or the backup branch
  `backup/main-before-reset-2026-10-25`. The database was backed up to `backups/dressme-20261025-164031.archive.gz`.
- **What did you reuse from the old chat, and why nothing?** Nothing: not its code, prompts, tool designs, training
  data or model. What stayed (outfit scoring, buy advice, weather, the explanations) belongs to the app's screens, not
  to the chat, so the screens still need it.
- **What happens to old chat events in the database?** They stay in the `events` log, untouched. The admin overview shows
  them in an "Old chat" column only on the days that have some. The two saved chat messages (`chats` collection) were
  dropped after the backup.

## 6. Not reused, in any later step
The old chat's code, prompts, tool designs, training data and the `dressme-chat-v4` model are not used again. The new
assistant uses the base `qwen3:4b` model, which I fine-tune myself in step 3h.

## 7. What comes back in steps 3b to 3h
- 3b: searching the wardrobe by words (the Wardrobe "search or ask" bar).
- 3c and 3d: the other parts of the Ask flow (not written down in the repository yet).
- 3e: my own price logic for selling.
- 3f: the new assistant's conversation page, in place of the placeholder.
- 3g: the Explainability page shows the new chat's groundedness rate and real tool-call counts.
- 3h: fine-tuning `qwen3:4b` myself.
