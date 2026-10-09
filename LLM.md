# Local chat model (Ollama + fine-tuning)

The Assistant page can run on a model on our own machine instead of Gemini:
no key, no 20-requests-a-day quota, and it works offline on demo day.

```
build_chat_dataset.py ──> Kaggle (finetune_chat.py, QLoRA) ──> make_ollama_model.py ──> backend CHAT_ENGINE=ollama
   synthetic chats          free T4 GPU, ~2-5 h                 GGUF -> `dressme-chat-v2`   evaluate_chat.py compares
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

### 2.1 Build the dataset (any machine with the backend requirements + local MongoDB, ~1 min)

```
python src/phase4/build_chat_dataset.py --show 5
```

→ `data/processed/chat_sft/{train,val,test}.jsonl` (4000 / 250 / 400 conversations). Each conversation talks to **one of the five agents** (`backend/app/agents/`) with that agent's real system prompt and tools, imported from the backend, so training and the app always match; ~5% of the rows teach the agent router instead (its prompt, a question, the agent's name). Each conversation has a random wardrobe, saved with a pool of shop and friperie listings in a scratch MongoDB database (`dressme_chat_build`, dropped at the end), and the backend's **real** tool functions run on it: scores, verdicts, prices, insights and explanations come from `compatibility.py`, `explain_outfit.py` and `app/resale.py` with the team's settings. Only the H&M catalogue and the weather are small fakes. The data teaches: list_wardrobe before any tool that takes item ids, get_weather before "what do I wear today?", no tool for greetings / thanks / off-topic, and one sentence pointing to the right agent when a question reaches the wrong one. The sentences are in `src/phase4/chat_phrases.py` and `chat_phrases_agents.py` (the agents' new scenarios). A suggestion without an explicit count returns one best outfit; requests such as “give me four” still exercise the requested count. The first dataset (v1, the original four tools) is kept in `data/processed/chat_sft_v1/`.

> **Team: please complete the native-speaker review of the Darija in `src/phase4/chat_phrases.py` and `chat_phrases_agents.py`** (nouns, colours and answers; all of the second file is new and unreviewed, section 7 of the sheet). The first team corrections are already applied to the phrase table and dataset review sheet; the model still learns every word exactly as written. Then rebuild the dataset after any further corrections. The review sheet is [reports/phase4/darija_review.md](reports/phase4/darija_review.md): every Darija word and sentence with transliteration, meaning, open questions and a Correction column.

The answer language follows the language the user **writes** in; the profile language is only used when that is unclear (system prompt in `routers/chat.py`; the dataset already works that way, 12% of chats are in another language than the profile). Before 2026-10-04 the prompt let the profile language win, and the base model answered French and Darija questions in English.

### 2.2 Train on Kaggle (our 4 GB GPU is too small for a 4B model)

QLoRA with Unsloth: the base model is loaded in 4 bits and only small LoRA adapters are trained (1 epoch, rank 16, only the assistant turns are learned). The free Kaggle T4 (16 GB) took 2.3 h for v1 (3000 shorter conversations); v2 has about twice the tokens.

> **Template trap (fixed 2026-10-08):** the tokenizer Unsloth ships with `unsloth/Qwen3-4B-Instruct-2507` uses the hybrid Qwen3 "thinking" template, which writes an empty `<think>

</think>

` before the last answer of every conversation. Ollama's template never does. v1 learned it: its final answers began with stray tags and it called tools for "thank you". `finetune_chat.py` now removes the empty block and stops if any `<think>` is left. The Kaggle CLI must use the mohameddazizz account (see CLAUDE.md).

```
kaggle datasets create -p data/processed/chat_sft            # first time (private by default)
kaggle datasets version -p data/processed/chat_sft -m "new data"   # after rebuilding
kaggle kernels push -p kaggle/chat_finetune
kaggle kernels status mohameddazizz/dressme-chat-finetune
kaggle kernels output mohameddazizz/dressme-chat-finetune -p models/llm/dressme-chat-v2-download
```

The dataset folder also holds a copy of `src/phase4/finetune_chat.py` (written by the build script), and the notebook runs that copy, so **rebuild and re-upload after changing the training script**. The output is `models/llm/dressme-chat/` (git-ignored): `gguf/*.gguf` (~2.5 GB), `lora/` and `training_log.json` (loss per step, val loss).

Training on our own machine works only on Linux / WSL with a CUDA GPU and `pip install -r requirements-llm.txt`; on 4 GB, only a smoke test with a smaller model:
`python src/phase4/finetune_chat.py --base unsloth/Qwen3-1.7B --limit 50 --max-seq 2048 --gguf none`.

### 2.3 Register it in Ollama

```
python src/phase4/make_ollama_model.py --gguf models/llm/dressme-chat-v2/gguf/<file>.gguf --name dressme-chat-v2
```

This writes a Modelfile next to the GGUF's model folder (`models/llm/dressme-chat-v2/Modelfile`), using the GGUF and the chat template of `qwen3:4b-instruct`, the format the model was trained on. Then it runs `ollama create`. Then set `OLLAMA_MODEL=dressme-chat-v2` in `backend/.env` (if the evaluation says it is better).

### 2.4 Evaluate (team rule: the app uses whichever is better)

```
python src/phase4/evaluate_chat.py            # qwen3:4b-instruct vs dressme-chat vs dressme-chat-v2, 150 test conversations
```

Baseline before fine-tuning (`qwen3:4b-instruct`, `--limit 30`, 75 decisions, 2026-10-04, old language rule): tool decision 76.0%, tool name 33.3%, **arguments 13.9%** (0% on score and suggest), language 94.9%, 8.6 s per decision. It knows *when* to use a tool, but rarely picks the right one with the right ids, and it invents reasons (e.g. "two tops is too revealing" for the max-1-top rule). The language check only looks for Arabic script, so MSA counts as Darija. Until 2026-10-04 the language check compared every answer with the language of the conversation's *last* question, but the language can change between questions, so even the expected answers scored only 93.9% (now 100%; `answer_languages` in the dataset gives one language per answer). The baseline language figure above used the old check; rebuild the dataset before re-running.

**Results (2026-10-09, `reports/phase4/chat_evaluation.md`, 150 test conversations of the v2 dataset, five agents + router):**

| Model | Tool decision | Tool name | Arguments | Language | Router | s / decision |
|---|---|---|---|---|---|---|
| qwen3:4b-instruct | 79.5% | 46.1% | 26.7% | 78.1% | 80.0% | 10.8 |
| dressme-chat (v1) | 58.4% | 69.4% | 57.8% | 90.9% | 70.0% | 4.9 |
| **dressme-chat-v2** | **98.0%** | **97.2%** | **92.8%** | **98.8%** | **90.0%** | 5.4 |

v2 is the app's model (`OLLAMA_MODEL=dressme-chat-v2`). Weakest spots: the Shopping advisor (search arguments 64%, look-alikes 73%; it once sent a made-up id to `find_similar` instead of calling `list_wardrobe`), "not owned" questions and hand-offs from the Shopping advisor (50%, few examples). The test is synthetic, from the same generator as the training data: it measures tool use and language, not how natural the answers sound with real users.

Answers are capped at 600 tokens (`num_predict`, backend and evaluation; our longest training answer is ~150): at temperature 0 the base model once repeated itself until Ollama's 5-minute timeout.

→ `reports/phase4/chat_evaluation.md`. Every assistant turn of a test conversation is one decision, and the model sees the real conversation up to that point. It reports: tool decision (call a tool or answer?), tool name, arguments, and language of the answer, per scenario, with example answers. The test wardrobes are new, and about a third of the questions use phrasings the training split never saw.

Limits: synthetic data measures tool use and language, not how natural the answers sound. Also try a few real questions in the app. If the fine-tuned model sounds stiff or repeats our templates word for word, try fewer steps (`--epochs 0.5`) or add more phrasings to `chat_phrases.py`.

## Agents

Since 2026-10-08 the chat is five agents (AGENTS.md). v1 (`dressme-chat`) was trained on the original single prompt and four tools, before the agents; its training data is in `data/processed/chat_sft_v1/`. v2 (`dressme-chat-v2`) is trained on every agent's prompt and tools, plus router rows. With `CHAT_ENGINE=ollama`, the router adds one short call per message (`OllamaEngine.classify`, at most 10 tokens, ~3 s on the RTX 2050; `ROUTER=keywords` skips it).

When a tool's name, arguments or docstring changes, or an agent's job changes, rebuild the dataset and retrain: the model only knows the tools as they were when it was trained.
