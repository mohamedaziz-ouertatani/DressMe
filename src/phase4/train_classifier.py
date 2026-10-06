"""
Train the EfficientNet-B0 classifier (category, sub_category, pattern).

Data: the distinct pictures of dressme.csv (duplicate copies left out), read
from the packed image cache (src/phase4/build_image_cache.py) and decoded / augmented
on the GPU in whole batches (see classifier.gpu_batch). A background thread
reads the next batches while the GPU trains, so no worker processes are needed
(RAM is tight on this laptop). Training uses the `train`
split; the best epoch is chosen on `val`; `test` is never touched here (see
src/phase4/evaluate_classifier.py).

Each picture only trains the heads it has a label for: e.g. PolyVore has no
pattern, so it never trains the pattern head (missing label = -1, ignored).
Classes are weighted by 1/sqrt(frequency), so shoes and accessories do not
drown out the small classes (without fully ignoring how common they are).

A checkpoint is saved after every epoch; if the run stops, start it again and
it continues from the last epoch.

Output (git-ignored):
    models/checkpoints/classifier_last.pt   to resume
    models/checkpoints/classifier_best.pt   best val epoch (used by classifier.py)
    models/checkpoints/train_log.csv        one line per epoch
Copied at the end: reports/phase4/classifier_training_log.csv

Run from the project root (~2 h on the RTX 2050; run it as a separate process):
    python src/phase4/train_classifier.py
    python src/phase4/train_classifier.py --limit 2000   # quick test, separate folder
"""

import argparse
import math
import queue
import shutil
import threading
import time

import numpy as np
import pandas as pd
import torch

from build_image_cache import PACK, PACK_INDEX
from classifier import HEADS, DressMeNet, gpu_batch
from item_images import DATA, ROOT, picture_key

CKPT_DIR = ROOT / "models" / "checkpoints"
EPOCHS = 5
BATCH = 64
LR = 5e-4
WARMUP_STEPS = 500
SEED = 0


def load_table():
    """One row per cached picture, with the class number of each head (-1 = no label)."""
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=["id", "dataset", "image_group", "category", "sub_category",
                              "pattern", "duplicate", "split"])
    df = df[df["duplicate"] != "True"].copy()
    df["key"] = picture_key(df)
    df = df.drop_duplicates("key")
    index = pd.read_csv(PACK_INDEX, dtype={"key": str})
    df = df.merge(index, on="key")            # adds offset / length in the pack
    for head, classes in HEADS.items():
        index = {c: i for i, c in enumerate(classes)}
        df[head + "_y"] = df[head].map(index).fillna(-1).astype(int)
    return df


def batches(df, device, train, batch=BATCH):
    """Yield (pictures, labels) batches ready on the GPU.

    A background thread reads the JPEG bytes of the next batches from the pack
    while the GPU works on the current one. Train: shuffled, augmented, and the
    last incomplete batch is dropped.
    """
    pack = np.memmap(PACK, dtype=np.uint8, mode="r")
    offsets, lengths = df["offset"].to_numpy(), df["length"].to_numpy()
    labels = torch.from_numpy(df[[h + "_y" for h in HEADS]].to_numpy())
    order = np.random.permutation(len(df)) if train else np.arange(len(df))
    stops = range(batch, len(df) + 1, batch) if train else range(batch, len(df) + batch, batch)
    ready = queue.Queue(maxsize=4)

    def reader():
        for stop in stops:
            idx = order[stop - batch:stop]
            ready.put((idx, [np.array(pack[o:o + n]) for o, n in zip(offsets[idx], lengths[idx])]))
        ready.put(None)

    threading.Thread(target=reader, daemon=True).start()
    while (item := ready.get()) is not None:
        idx, blobs = item
        yield gpu_batch(blobs, device, train), labels[idx].to(device)


def steps_per_epoch(df, batch=BATCH):
    return len(df) // batch


def class_weights(labels, n_classes):
    """1/sqrt(frequency), scaled so an average picture has weight 1."""
    counts = np.bincount(labels[labels >= 0], minlength=n_classes).astype(float)
    w = np.where(counts > 0, 1 / np.sqrt(np.maximum(counts, 1)), 0.0)
    w *= counts.sum() / (w * counts).sum()
    return torch.tensor(w, dtype=torch.float32)


@torch.no_grad()
def evaluate(model, df, device):
    """Accuracy per head on pictures that have that label."""
    model.eval()
    right = {h: 0 for h in HEADS}
    total = {h: 0 for h in HEADS}
    for x, y in batches(df, device, train=False):
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            out = model(x)
        for j, h in enumerate(HEADS):
            has = y[:, j] >= 0
            right[h] += (out[h].argmax(1)[has] == y[has, j]).sum().item()
            total[h] += has.sum().item()
    model.train()
    return {h: right[h] / max(total[h], 1) for h in HEADS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="use only N train / N val pictures (test run)")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    args = ap.parse_args()
    out_dir = CKPT_DIR / "smoke" if args.limit else CKPT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(SEED)
    device = "cuda"

    df = load_table()
    train_df, val_df = df[df["split"] == "train"], df[df["split"] == "val"]
    if args.limit:
        train_df = train_df.sample(args.limit, random_state=SEED)
        val_df = val_df.sample(min(args.limit, len(val_df)), random_state=SEED)
    print(f"{len(train_df):,} train / {len(val_df):,} val pictures", flush=True)

    model = DressMeNet().to(device)
    losses = {h: torch.nn.CrossEntropyLoss(
                  weight=class_weights(train_df[h + "_y"].to_numpy(), len(c)).to(device),
                  ignore_index=-1)
              for h, c in HEADS.items()}
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    n_steps = steps_per_epoch(train_df)
    total_steps = args.epochs * n_steps
    # warm up (at most 10% of the run), then a cosine curve down to 0
    warmup = min(WARMUP_STEPS, total_steps // 10)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / max(warmup, 1))
                                              * 0.5 * (1 + math.cos(math.pi * s / total_steps)))
    scaler = torch.amp.GradScaler()

    # --- resume from the last checkpoint, if any ---------------------------
    start_epoch, history, best = 0, [], -1.0
    last = out_dir / "classifier_last.pt"
    if last.exists():
        ck = torch.load(last, map_location=device, weights_only=True)   # tensors and numbers only
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        scaler.load_state_dict(ck["scaler"])
        start_epoch, history, best = ck["epoch"] + 1, ck["history"], ck["best"]
        print(f"resumed after epoch {start_epoch}", flush=True)

    # --- training ------------------------------------------------------------
    model.train()
    for epoch in range(start_epoch, args.epochs):
        start, running = time.time(), 0.0
        np.random.seed(SEED + epoch)          # a different, reproducible order each epoch
        for step, (x, y) in enumerate(batches(train_df, device, train=True), 1):
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                out = model(x)
                # sum of the three head losses (a head with no label in the batch adds 0)
                loss = sum(losses[h](out[h].float(), y[:, j]) if (y[:, j] >= 0).any()
                           else out[h].sum() * 0 for j, h in enumerate(HEADS))
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            running += loss.item()
            if step % 200 == 0:
                print(f"  epoch {epoch + 1} step {step}/{n_steps} loss "
                      f"{running / 200:.3f} ({step * BATCH / (time.time() - start):.0f} img/s)",
                      flush=True)
                running = 0.0

        acc = evaluate(model, val_df, device)
        score = float(np.mean(list(acc.values())))
        history.append({"epoch": epoch + 1, "minutes": round((time.time() - start) / 60, 1),
                        **{f"val_{h}": round(a, 4) for h, a in acc.items()}})
        print(f"epoch {epoch + 1}: " + ", ".join(f"{h} {100 * a:.1f}%" for h, a in acc.items()),
              flush=True)
        if score > best:
            best = score
            torch.save({"model": model.state_dict(), "epoch": epoch + 1, "val": acc,
                        "heads": HEADS}, out_dir / "classifier_best.pt")
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                    "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                    "epoch": epoch, "history": history, "best": best}, last)
        pd.DataFrame(history).to_csv(out_dir / "train_log.csv", index=False)

    if not args.limit:
        shutil.copy(out_dir / "train_log.csv", ROOT / "reports" / "phase4" / "classifier_training_log.csv")
    print("done", flush=True)


if __name__ == "__main__":
    main()
