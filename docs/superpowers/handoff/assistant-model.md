# Hand-off: the assistant's model (step 3d)

The assistant's answers come from a language model that runs in **Ollama on your own PC**, not in Docker. The backend
container reaches it at `http://host.docker.internal:11434`. Which model is a setting.

## 1. Pick the model

| `CHAT_MODEL` | Size | Who | Evaluated? |
|---|---|---|---|
| `qwen3.5:4b` (default) | 3.3 GB on disk, ~3.4 GB of GPU memory | everyone who can | **yes**: the only model the reports measure |
| `dressme-chat-v4` | 2.5 GB | a teammate short of disk space who already has it | **no** |

Why only one model is evaluated: the project's results (the live checks of 3d, the traps of 3g, the fine-tune of 3h)
must all describe the same model, or the numbers cannot be compared. `qwen3.5:4b` is the base that 3h fine-tunes.
`dressme-chat-v4` is the old chat's fine-tune (removed in step 3a): it is there only so the app runs on a smaller disk.
Its answers may be worse and nobody measures them, so never report a result made with it.

## 2. Set it up

1. Install Ollama (https://ollama.com) and start it (the tray icon, or `ollama serve`).
2. Pull the model: `ollama pull qwen3.5:4b` (or check that `ollama list` already shows `dressme-chat-v4`).
3. In `backend/.env` (never committed) add:
   ```
   CHAT_MODEL=qwen3.5:4b
   OLLAMA_URL=http://host.docker.internal:11434
   ```
   (Both are the defaults, so with the default model you may leave them out. Without Docker, use
   `OLLAMA_URL=http://localhost:11434`.)
4. Restart the backend: `docker compose up -d --build backend`, wait about a minute. Its log says
   `assistant: model qwen3.5:4b at http://host.docker.internal:11434; Ollama answered /api/show: yes`.
   `NO` means Ollama is off or does not have the model: the app still runs and the assistant answers 503.

## 3. Check it

- `GET /assistant/status` (logged in, e.g. from http://localhost:8000/docs) -> `{"available": true, "model": "qwen3.5:4b"}`.
- Ask one question (`POST /chat`), then `ollama ps` on the PC. OK:
  `qwen3.5:4b  ...  3.4 GB  100% GPU  8192  ...  9 minutes from now`.
  **PROCESSOR must say 100% GPU.** If it says e.g. `25%/75% CPU/GPU`, the GPU is too small or busy (another model is
  loaded: `ollama stop <name>`), and answers get several times slower.
- The first question after a reboot can take minutes (the model is read from disk) and may answer 503 once; after
  that a cold load is ~13 s and a loaded model answers in a few seconds. Ollama keeps the model loaded 10 minutes after
  the last question (`keep_alive` in `mappings/agents.yaml`).

## 4. What the team may tune

`mappings/agents.yaml`, section `model:` (REVIEW): temperature, top_p, top_k, presence_penalty, num_ctx (context window:
more = more GPU memory), keep_alive, timeout_s, think. The API refuses to start with a clear message if a value is out of
range.
