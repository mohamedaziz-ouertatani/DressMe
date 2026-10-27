# Step 3d, in plain words: the Stylist with a real model

## Ollama and host.docker.internal
**Ollama** runs language models on the PC's GPU and answers on `http://localhost:11434`. The backend runs in Docker,
where "localhost" is the container itself, so it calls `host.docker.internal`: Docker's name for the PC.

## The OllamaClient is a translator
The loop speaks one language (`chat(messages, tools, max_tokens) -> ModelReply`), Ollama another (`POST /api/chat`).
`ollama.py` translates both ways: our tool results get Ollama's `tool_name`, Ollama's `tool_calls` become our `ToolCall`s.
Any failure (off, too slow, model missing) becomes `ModelUnavailable` -> 503. The loop did not change, except two small
additions (a `<think>` note in the trace, and refusing a tool the agent was not given).

## Think off
Qwen can "think" first (hidden reasoning). We switch it off (`think: false`): answers come several times faster, and a
`<think>` block that slips into the text is removed anyway.

## The 4 sampling knobs (mappings/agents.yaml, REVIEW)
temperature **0.7** (randomness), top_p **0.8** and top_k **20** (choose only among the likeliest words),
presence_penalty **1.5** (avoid repeating words). Qwen recommends these with thinking off.

## Context window, GPU memory, cold start
`num_ctx` **8192** tokens must hold the instructions, six tool descriptions, the results and the answer. A bigger window
needs more GPU memory: at 8192 the model takes 3.4 GB and runs **100% on the GPU** (`ollama ps`). Loading takes ~13 s
(minutes after a reboot); `keep_alive` **10m** keeps it loaded, so the next questions answer in seconds.

## How a model picks a tool
It reads each tool's name, description and argument schema, and writes a call when one fits. So each description says
**what it does, one example, and "do not use it for..."**, e.g. `build_outfit`: "Up to three outfits built around 1 to 3
of the user's pieces... Example: build_outfit(pieces=[2])... Do not use it with numbers you were not given in this turn."

## The Stylist's 6 tools: each reuses a screen's function
`list_wardrobe` (the items) - `search_wardrobe` (3b's search, `find_owned`) - `get_weather` (Dress's weather, default
city) - `suggest_outfits` (`GET /outfits/today`: the same three outfits) - `build_outfit` (`POST /outfits/build`) -
`score_outfit` (`POST /outfits/score`). Pieces go out as refs, scores as whole numbers: no ids, no free text.

## The live check (golden wardrobe, qwen3.5:4b)
| Question | Tools | s | Verdict |
|---|---|---|---|
| What should I wear today? | get_weather, suggest_outfits(everyday) | 25 (cold) | right tools, real pieces |
| Quelle tenue pour un entretien d'embauche ? | none | 8.5 | **invented** pieces (4 refs removed), French |
| ماذا ألبس مع بنطالي الأسود؟ | search_wardrobe("black jeans") | 4.8 | honest: none owned, Arabic |
| Do I have a white shirt? | search_wardrobe | 4.9 | right: two white tops |
| Black skirt + white top together? | search x2, score_outfit | 8.8 | right tools and pieces |
| What is smart casual? | none | 4.3 | fine, not labelled "general advice" |
| Write my maths homework | none | 3.1 | polite refusal |
| ...my pink cowboy hat? | search_wardrobe (then repeat) | 10.0 | honest: none found |

## Five teacher questions
- **Why does the app not stop when Ollama is off?** The model is only needed by `/chat`; it answers 503 and
  `/assistant/status` says false, everything else works.
- **Why call the screens' functions and not write new ones?** One function, two callers: the chat and Dress can never
  disagree, and the tests compare them.
- **Why whole numbers and refs in tool results?** Fewer tokens, nothing the model can copy wrongly, no id to leak.
- **Why turn thinking off?** Speed on a 4 B model, and the answer is only the answer.
- **Why did the French question go wrong?** It answered without a tool and invented pieces; the `{n}` rule removed the
  invented numbers, but not the words. Measuring and fixing this is 3g / 3h, not prompt tweaks now.

## What is left
3e: the other four agents, the router, handoff, retries / a second provider. 3f: the chat screen. 3g: traps and the
groundedness rate. 3h: our fine-tune of `qwen3.5:4b`.
