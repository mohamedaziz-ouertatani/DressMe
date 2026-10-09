"""
Fine-tunes the local chat model on the synthetic conversations of
src/phase4/build_chat_dataset.py, with QLoRA (Unsloth): the base model is loaded in
4 bits and only small LoRA adapters are trained, then everything is merged and
exported to GGUF for Ollama (src/phase4/make_ollama_model.py). See LLM.md.

Base: Qwen3-4B-Instruct-2507, the same model as `ollama pull qwen3:4b-instruct`,
so the evaluation compares the base and the fine-tuned model fairly.

Only the assistant's turns are learned (tool calls and answers); the system
prompt, questions and tool answers are masked out (train_on_responses_only).

Where to run it: a 4B model needs ~8-10 GB of GPU memory to train, more than
our RTX 2050 (4 GB). The default is the private Kaggle notebook
(kaggle/chat_finetune/, free T4 16 GB, ~1-2 h). For a local smoke test on 4 GB:
    python src/phase4/finetune_chat.py --base unsloth/Qwen3-1.7B --limit 50 --max-seq 2048 --gguf none

Usage (Linux / WSL / Kaggle; Unsloth needs a CUDA GPU):
    pip install -r requirements-llm.txt
    python src/phase4/finetune_chat.py                      # data/processed/chat_sft -> models/llm/dressme-chat
Output: <out>/lora/ (adapters), <out>/gguf/*.gguf (for Ollama), <out>/training_log.json.
"""

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "processed" / "chat_sft"
OUT_DIR = ROOT / "models" / "llm" / "dressme-chat"
BASE = "unsloth/Qwen3-4B-Instruct-2507"

# Qwen chat format: everything after "assistant" is learned, everything after
# "user" is masked (tool answers are sent in a user turn: <tool_response>)
INSTRUCTION_PART = "<|im_start|>user\n"
RESPONSE_PART = "<|im_start|>assistant\n"


def read_jsonl(path, limit=None):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return rows[:limit] if limit else rows


EMPTY_THINK = "<think>\n\n</think>\n\n"


def to_texts(rows, tokenizer, max_seq):
    """Each conversation rendered with the model's own chat template (tools included).
    Conversations longer than max_seq tokens are dropped, never cut in the middle.

    The template Unsloth ships with Qwen3-4B-Instruct-2507 is the hybrid "thinking" one: it
    writes an empty <think></think> before the LAST answer. Ollama's template (the one the
    app uses) never does, and the first model learned it: its final answers started with
    stray tags. So the empty block is removed, and any other <think> stops the training."""
    texts, too_long = [], 0
    for r in rows:
        text = tokenizer.apply_chat_template(r["messages"], tools=r["tools"], tokenize=False)
        text = text.replace(EMPTY_THINK, "")
        if "<think>" in text or "</think>" in text:
            raise ValueError(f"conversation {r.get('id')}: <think> left in the training text")
        if len(tokenizer(text, add_special_tokens=False)["input_ids"]) > max_seq:
            too_long += 1
            continue
        texts.append(text)
    return texts, too_long


def sft_config(args, out, has_eval, bf16):
    from trl import SFTConfig
    common = dict(
        output_dir=str(out / "trainer"), dataset_text_field="text",
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.accum,
        num_train_epochs=args.epochs, learning_rate=args.lr, lr_scheduler_type="cosine",
        warmup_ratio=0.03, weight_decay=0.01, optim="adamw_8bit", logging_steps=10,
        eval_strategy="epoch" if has_eval else "no", per_device_eval_batch_size=args.batch,
        save_strategy="no", fp16=not bf16, bf16=bf16, seed=3407, report_to="none",
        packing=False)
    try:                                      # the argument was renamed in recent trl
        return SFTConfig(max_length=args.max_seq, **common)
    except TypeError:
        return SFTConfig(max_seq_length=args.max_seq, **common)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", type=Path, default=DATA_DIR)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--epochs", type=float, default=1)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16, help="LoRA rank")
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=8, help="gradient accumulation (batch x accum = 16)")
    ap.add_argument("--max-seq", type=int, default=4096)
    ap.add_argument("--limit", type=int, help="first N train conversations (smoke test)")
    ap.add_argument("--gguf", default="q4_k_m", help="GGUF quantization for Ollama, or 'none'")
    args = ap.parse_args()

    # unsloth must be imported before transformers / trl (it patches them)
    from unsloth import FastLanguageModel, is_bfloat16_supported
    from unsloth.chat_templates import train_on_responses_only
    from datasets import Dataset
    from trl import SFTTrainer

    started = time.time()
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base, max_seq_length=args.max_seq, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(
        model, r=args.rank, lora_alpha=args.rank, lora_dropout=0, bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth", random_state=3407)

    train_texts, train_long = to_texts(read_jsonl(args.data / "train.jsonl", args.limit), tokenizer, args.max_seq)
    val_path = args.data / "val.jsonl"
    val_texts, _ = to_texts(read_jsonl(val_path, args.limit), tokenizer, args.max_seq) \
        if val_path.exists() else ([], 0)
    print(f"train: {len(train_texts)} conversations ({train_long} longer than {args.max_seq} tokens dropped), "
          f"val: {len(val_texts)}")
    print("example:\n" + train_texts[0][-1500:])

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=Dataset.from_dict({"text": train_texts}),
        eval_dataset=Dataset.from_dict({"text": val_texts}) if val_texts else None,
        args=sft_config(args, args.out, bool(val_texts), is_bfloat16_supported()))
    trainer = train_on_responses_only(trainer, instruction_part=INSTRUCTION_PART,
                                      response_part=RESPONSE_PART)
    result = trainer.train()

    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(args.out / "lora"))
    tokenizer.save_pretrained(str(args.out / "lora"))
    if args.gguf != "none":
        # merges the adapters into the base model, then converts (builds llama.cpp once)
        model.save_pretrained_gguf(str(args.out / "gguf"), tokenizer, quantization_method=args.gguf)

    log = {"base": args.base, "args": {k: str(v) for k, v in vars(args).items()},
           "train_conversations": len(train_texts), "dropped_too_long": train_long,
           "val_conversations": len(val_texts), "train_loss": result.training_loss,
           "minutes": round((time.time() - started) / 60, 1),
           "history": trainer.state.log_history}
    (args.out / "training_log.json").write_text(json.dumps(log, indent=2))
    print(f"done in {log['minutes']} min, train loss {result.training_loss:.3f} -> {args.out}")


if __name__ == "__main__":
    main()
