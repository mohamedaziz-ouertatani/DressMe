# Local chat model (Ollama + fine-tuning)

The Assistant page can run on a model on our own machine instead of Gemini:
no key, no 20-requests-a-day quota, and it works offline on demo day.

```
build_chat_dataset.py ──> Kaggle (finetune_chat.py, QLoRA) ──> make_ollama_model.py ──> backend CHAT_ENGINE=ollama
   synthetic chats          free T4 GPU, ~1-2 h                 GGUF -> `dressme-chat`      evaluate_chat.py compares
```

## 1. Use the base model now (no training)

`qwen3:4b-instruct` is already pulled (`ollama list`). In `backend/.env`:

```
CHAT_ENGINE=ollama
OLLAMA_MODEL=qwen3:4b-instruct
```

Restart the backend. `app/chat_engine.py` (`OllamaEngine`) sends the same system prompt and the same four tools as for Gemini; Ollama answers with tool calls, the backend runs them and sends the results back (at most 6 rounds). Errors: 503 = Ollama not running or the model not pulled, 502 = Ollama failed or timed out. `CHAT_ENGINE=gemini` switches back.

Why Qwen3-4B-Instruct: it is the best tool-calling model of this size in our `ollama list`, it has no "thinking" mode (fast answers), and it knows French and Arabic. qwen2.5:3b and phi3:mini are weaker at tools; qwen2.5-coder is for code.

GPU: the 4B model needs ~2.5 GB plus ~1 GB for its context (`OLLAMA_NUM_CTX=8192`), and the backend's own models take ~1.5 GB, so on the RTX 2050 (4 GB) Ollama puts some layers on the CPU by itself. Answers then take a few seconds; the first one also loads the model.

Measured on the RTX 2050 (2026-10-04, backend running, `ollama ps` = 4.1 GB, 42% CPU / 58% GPU): ~21 tokens/s generated, prompt read at 1,000-9,000 tokens/s. One chat answer = 11-18 s when it calls tools (each tool round sends the whole conversation again, and `list_wardrobe` of 24 items is long), ~35 s for the first answer (model loading). On the CPU only it was 11-51 s per answer.

> **Check `ollama ps`: the PROCESSOR column must show some GPU.** If Ollama starts while the PC is short of RAM, it sometimes finds no GPU (`server.log`: `total_vram="0 B"`) and runs 100% on the CPU until it restarts. Fix: quit Ollama from the tray icon and start it again.

## 2. Fine-tune it

Goal: the base model already chats; fine-tuning teaches it **our** job: call the right tool with the right arguments, use `list_wardrobe` then `score_outfit` for "does A go with B?", never invent clothes, keep answers short, and answer in the user's language, including Tunisian Darija and Arabizi questions.

### 2.1 Build the dataset (any machine, ~1 min)

```
python src/build_chat_dataset.py --show 5
```

→ `data/processed/chat_sft/{train,val,test}.jsonl` (3000 / 200 / 300 conversations). Each one has a random wardrobe, and the backend's **real** tool functions run on it (through a tiny fake database), so scores, verdicts and reasons come from `src/compatibility.py` with the team's weights. The system prompt and tool descriptions are imported from `backend/app/routers/chat.py`, so training and the app always match. The sentences are in `src/chat_phrases.py`.

> **Team: please have a native speaker read the Darija in `src/chat_phrases.py`** (nouns, colours and answers). It was written without a native check, and the model learns every word as written. Then rebuild the dataset.

### 2.2 Train on Kaggle (our 4 GB GPU is too small for a 4B model)

QLoRA with Unsloth: the base model is loaded in 4 bits and only small LoRA adapters are trained (1 epoch, rank 16, only the assistant turns are learned). The free Kaggle T4 (16 GB) does it in ~1-2 h. The Kaggle CLI must use the mohameddazizz account (see CLAUDE.md).

```
kaggle datasets create -p data/processed/chat_sft            # first time (private by default)
kaggle datasets version -p data/processed/chat_sft -m "new data"   # after rebuilding
kaggle kernels push -p kaggle/chat_finetune
kaggle kernels status mohameddazizz/dressme-chat-finetune
kaggle kernels output mohameddazizz/dressme-chat-finetune -p models/llm
```

The dataset folder also holds a copy of `src/finetune_chat.py` (written by the build script), and the notebook runs that copy, so **rebuild and re-upload after changing the training script**. The output is `models/llm/dressme-chat/` (git-ignored): `gguf/*.gguf` (~2.5 GB), `lora/` and `training_log.json` (loss per step, val loss).

Training on our own machine works only on Linux / WSL with a CUDA GPU and `pip install -r requirements-llm.txt`; on 4 GB, only a smoke test with a smaller model:
`python src/finetune_chat.py --base unsloth/Qwen3-1.7B --limit 50 --max-seq 2048 --gguf none`.

### 2.3 Register it in Ollama

```
python src/make_ollama_model.py
```

This writes `models/llm/dressme-chat/Modelfile`, using the GGUF and the chat template of `qwen3:4b-instruct`, the format the model was trained on. Then it runs `ollama create dressme-chat`. Then set `OLLAMA_MODEL=dressme-chat` in `backend/.env`.

### 2.4 Evaluate (team rule: the app uses whichever is better)

```
python src/evaluate_chat.py            # qwen3:4b-instruct vs dressme-chat, 150 test conversations
```

→ `reports/chat_evaluation.md`. Every assistant turn of a test conversation is one decision, and the model sees the real conversation up to that point. It reports: tool decision (call a tool or answer?), tool name, arguments, and language of the answer, per scenario, with example answers. The test wardrobes are new, and about a third of the questions use phrasings the training split never saw.

Limits: synthetic data measures tool use and language, not how natural the answers sound. Also try a few real questions in the app. If the fine-tuned model sounds stiff or repeats our templates word for word, try fewer steps (`--epochs 0.5`) or add more phrasings to `chat_phrases.py`.
