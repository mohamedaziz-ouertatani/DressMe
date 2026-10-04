"""
Registers the fine-tuned GGUF (from src/finetune_chat.py / the Kaggle notebook)
in Ollama as `dressme-chat`, so the backend can use it with
CHAT_ENGINE=ollama and OLLAMA_MODEL=dressme-chat (LLM.md).

The chat template (how messages and tool calls are written for the model) is
copied from the base model already in Ollama (qwen3:4b-instruct), because the
fine-tuned model was trained with exactly that format; a GGUF alone does not
always tell Ollama how to handle tools.

Usage (from the project root, Ollama running):
    python src/make_ollama_model.py
    python src/make_ollama_model.py --gguf path/to/model.gguf --name dressme-chat --base qwen3:4b-instruct
Writes models/llm/dressme-chat/Modelfile, then runs `ollama create`.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "llm" / "dressme-chat"


def ollama(*args):
    try:
        done = subprocess.run(["ollama", *args], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        sys.exit("ollama is not installed (https://ollama.com)")
    if done.returncode != 0:
        sys.exit(f"ollama {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gguf", type=Path, help="default: the only .gguf under models/llm/dressme-chat/")
    ap.add_argument("--name", default="dressme-chat")
    ap.add_argument("--base", default="qwen3:4b-instruct", help="Ollama model to copy the template from")
    args = ap.parse_args()

    gguf = args.gguf
    if gguf is None:
        found = sorted(MODEL_DIR.rglob("*.gguf"))
        if len(found) != 1:
            sys.exit(f"expected one .gguf under {MODEL_DIR}, found {len(found)}: pass --gguf")
        gguf = found[0]

    base_modelfile = ollama("show", args.base, "--modelfile")
    try:
        template = base_modelfile.split('TEMPLATE """', 1)[1].split('"""', 1)[0]
    except (IndexError, ValueError):
        sys.exit("the base model's Modelfile does not contain a readable TEMPLATE block")
    if '"""' in template:
        sys.exit("the base template contains triple quotes: write the Modelfile by hand")
    parameters = [line.split(None, 1) for line in ollama("show", args.base, "--parameters").splitlines()
                  if line.strip()]
    lines = [f"FROM {gguf.resolve()}", f'TEMPLATE """{template.strip()}"""']
    for key, value in parameters:
        if key != "temperature":           # the backend sets it per request
            lines.append(f"PARAMETER {key} {value.strip()}")

    modelfile = MODEL_DIR / "Modelfile"
    modelfile.parent.mkdir(parents=True, exist_ok=True)
    modelfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {modelfile}; creating {args.name} (copies ~2.5 GB)...")
    ollama("create", args.name, "-f", str(modelfile))
    print(f"done: `ollama run {args.name}`, or OLLAMA_MODEL={args.name} in backend/.env")


if __name__ == "__main__":
    main()
