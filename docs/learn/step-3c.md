# Step 3c, in plain words: the skeleton of the assistant

## What was built
The whole chat path, end to end, with a **fake model** that follows a script and ONE real tool, `list_wardrobe`. You can
call `POST /chat`, the fake model asks the tool for your pieces, the tool answers from your own wardrobe, and the answer comes
back with `{1}`, `{2}` marking pieces. No real language model yet (3d), no screen yet (3f).

## One turn
```
message -> loop -> model.chat(messages, tools) -> "call list_wardrobe"
                        ^                              |
                        |                         registry.run -> tool -> your items -> ledger gives refs 1, 2, 3
                        +---- tool result (refs, no ids) <-------+
        model.chat(...) -> "Try {2} with {1}." -> {n} rule (invented numbers removed) -> answer -> saved in `chats`
```

## The files (`backend/app/assistant/`)
- `model.py`: what a model reply looks like, the fake one for tests, and `NoModel` (the default: "unavailable").
- `ledger.py` + `placeholders.py`: the small numbers for pieces, and the `{n}` rule.
- `tools.py` + `tools_wardrobe.py`: what a tool is, the registry that runs it safely, and `list_wardrobe`.
- `agents.py` + `mappings/agents.yaml`: the agents (job, instructions, tools, limits), checked at start-up.
- `loop.py`: one turn. `routers/chat.py`: the route that saves the turn in `chats`.

## The words, one line each
- **Tool**: a function the model may ask for, with a description it reads and arguments that are checked.
- **Registry**: the list of tools; it shows their schemas and runs a call without ever crashing the turn.
- **Ledger**: this turn's table "1 = that jacket, 2 = those jeans". The model sees numbers, never database ids.
- **Agent**: a job (stylist...), its instructions, the few tools it may use and its limits.
- **Loop**: ask the model, run its tools, show it the results, repeat until it answers.
- **Stop rules**: an answer ends the turn; at most `max_rounds` rounds; the same call twice stops it; then one last question with no tools.

## The trace of "What can I wear with my black jeans?" (fake model)
1. Messages: system (stylist instructions + shared rules), user (the question). Tools offered: `list_wardrobe`.
2. Fake model: call `list_wardrobe(category="bottom", colour="black")`.
3. Registry checks the arguments, runs the tool on **your** items. The model reads: `{"pieces": [{"ref": 1, "category": "bottom",
   "type": "skirt", "colour": "black", "pattern": "solid", "season": [...]}], "total": 1}`.
4. Fake model: "Try {2} with {1}. {99}".
5. Rule: {1} was shown, so it stays; {2} and {99} were not, so they are removed. Answer: "Try with {1}."
6. Saved in `chats`; the response carries piece 1 as a normal item (photo link included).

## Five teacher questions
- **Why can't the model see database ids?** An id is a key to the data. If the model could write one, a wrong or hostile
  message could make it ask for someone else's item. Numbers valid only for this turn leave nothing to guess.
- **Why a fake model first?** To test everything around the model (rules, safety, saving) in milliseconds and without
  randomness. A real model can then be swapped in without touching any of it.
- **What stops an endless loop?** `max_rounds`, the repeat check (same tool, same arguments), and a last call with no tools.
- **Why YAML and why validate at start-up?** The team edits agents without code. A typo would otherwise show up in a user's chat;
  now the API refuses to start and names the agent and the field.
- **What happens to an invented {n}?** It is removed from the text, the answer stays tidy, and the number is saved in
  `unknown_refs` so we can measure how often a model invents pieces.

## What is left
3d: a real model (Ollama) and the other tools. 3e: the other four agents and the router. 3f: the chat screen. 3g: the traps
(tests that try to fool it). 3h: our own fine-tuned model.
