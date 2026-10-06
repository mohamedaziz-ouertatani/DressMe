"""
Runs ON KAGGLE (a private notebook with a free T4 GPU, 16 GB), not on our machines.

Our RTX 2050 (4 GB) is too small to fine-tune a 4B model, so the training runs
here. The notebook installs Unsloth, finds our private dataset (the folder
written by src/phase4/build_chat_dataset.py, which also holds a copy of
src/phase4/finetune_chat.py) and runs that script. Everything it writes lands in the
notebook output: the LoRA adapters, the GGUF file for Ollama and the training log.

Pushed with (from the project root, after uploading the dataset; see LLM.md):
    kaggle kernels push -p kaggle/chat_finetune
Then, when it has finished (~1-2 h):
    kaggle kernels output mohameddazizz/dressme-chat-finetune -p models/llm
"""

import subprocess
import sys
from pathlib import Path

# Unsloth pulls matching versions of torch / transformers / trl / bitsandbytes
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "unsloth"], check=True)

# where Kaggle mounts a dataset has changed over time: search for it
data = next(Path("/kaggle/input").rglob("train.jsonl")).parent
out = Path("/kaggle/working/dressme-chat")
subprocess.run([sys.executable, str(data / "finetune_chat.py"), "--data", str(data), "--out", str(out)],
               check=True)

# keep only what we download: the quantized GGUF, the adapters and the log
# (not the merged 16-bit model or llama.cpp's build files, ~10 GB)
working = Path("/kaggle/working")
gguf_dir = out / "gguf"
gguf_dir.mkdir(parents=True, exist_ok=True)
ggufs = list(working.rglob("*.gguf"))
quantized = [g for g in ggufs if "f16" not in g.name.lower()] or ggufs
for g in quantized:
    if g.parent != gguf_dir:
        g.rename(gguf_dir / g.name)
for path in gguf_dir.iterdir():
    if path.suffix != ".gguf" or path.name not in {g.name for g in quantized}:
        subprocess.run(["rm", "-rf", str(path)])
for path in [*working.iterdir(), *out.iterdir()]:
    if path not in (out, gguf_dir, out / "lora", out / "training_log.json"):
        subprocess.run(["rm", "-rf", str(path)])
print(sorted(str(p) for p in out.rglob("*") if p.is_file()))
