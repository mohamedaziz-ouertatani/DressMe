"""
The DressMe item classifier: EfficientNet-B0 with three output "heads".

One picture goes in; three answers come out:
    category      (top, bottom, dress, ...: 9 classes)
    sub_category  (t-shirt, jeans, sneakers, ...: the vocabulary file)
    pattern       (solid, striped, checked, floral, printed)

Usage (e.g. from the API):
    model, device = load_classifier()
    predict([pil_image], model, device)
    -> [{"category": "top", "category_conf": 0.97, "sub_category": "t-shirt", ...}]

The sub_category answer is always one that belongs to the predicted category
(e.g. never "jeans" for a "shoes" item), using mappings/sub_category_vocabulary.csv.

Pictures are letterboxed to a 224 px white square, exactly like the training
cache (src/build_image_cache.py), then normalised for ImageNet weights.
"""

import numpy as np
import pandas as pd
import torch
from torch import nn
from torchvision import transforms
from torchvision.io import decode_jpeg
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
from torchvision.transforms.v2 import functional as TF

from item_images import ROOT, letterbox

CHECKPOINT = ROOT / "models" / "checkpoints" / "classifier_best.pt"
SIZE = 224

# class lists: fixed order, so a saved model always means the same thing
CATEGORIES = ["top", "bottom", "dress", "outerwear", "shoes", "bag", "accessory",
              "traditional", "swimwear"]
_vocab = pd.read_csv(ROOT / "mappings" / "sub_category_vocabulary.csv")
SUB_CATEGORIES = _vocab["sub_category"].tolist()
SUB_PARENT = dict(zip(_vocab["sub_category"], _vocab["category"]))
PATTERNS = ["solid", "striped", "checked", "floral", "printed"]
HEADS = {"category": CATEGORIES, "sub_category": SUB_CATEGORIES, "pattern": PATTERNS}

# ImageNet colour normalisation (what the pretrained weights expect)
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
TO_TENSOR = transforms.Compose([transforms.ToTensor(), transforms.Normalize(MEAN, STD)])


def augment(x):
    """Light random changes, so the model does not learn the exact pictures by heart:
    a random crop of 75-100% of the picture, a left-right flip, and small brightness /
    contrast changes. No hue change, so colours stay true. x: N x 3 x 224 x 224, 0-1."""
    n, _, h, w = x.shape
    out = torch.empty_like(x)
    for i in range(n):
        area = h * w * float(torch.empty(1).uniform_(0.75, 1.0))
        ratio = float(torch.empty(1).uniform_(0.85, 1.18))
        ch, cw = min(h, round((area / ratio) ** 0.5)), min(w, round((area * ratio) ** 0.5))
        top, left = int(torch.randint(0, h - ch + 1, (1,))), int(torch.randint(0, w - cw + 1, (1,)))
        out[i] = TF.resized_crop(x[i], top, left, ch, cw, [h, w], antialias=True)
    flip = torch.rand(n, device=x.device) < 0.5
    out[flip] = out[flip].flip(-1)
    brightness = torch.empty(n, 1, 1, 1, device=x.device).uniform_(0.8, 1.2)
    contrast = torch.empty(n, 1, 1, 1, device=x.device).uniform_(0.8, 1.2)
    grey = out.mean(dim=(1, 2, 3), keepdim=True)
    return ((out - grey) * contrast + grey).mul(brightness).clamp(0, 1)


def gpu_batch(blobs, device, train=False):
    """JPEG bytes (all 224 x 224, from the image cache) -> a normalised batch.
    Decoding runs on the GPU, which is ~3x faster than PIL and frees the CPU."""
    imgs = decode_jpeg([torch.from_numpy(b) for b in blobs], device=device)
    x = torch.stack(imgs).float() / 255
    if train:
        x = augment(x)
    mean = torch.tensor(MEAN, device=device).view(1, 3, 1, 1)
    std = torch.tensor(STD, device=device).view(1, 3, 1, 1)
    return (x - mean) / std


class DressMeNet(nn.Module):
    """EfficientNet-B0 body (shared) + one small linear layer per head."""

    def __init__(self, pretrained=True):
        super().__init__()
        weights = EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        body = efficientnet_b0(weights=weights)
        self.features, self.pool = body.features, body.avgpool   # 1280 numbers per picture
        self.dropout = nn.Dropout(0.3)
        self.heads = nn.ModuleDict({h: nn.Linear(1280, len(c)) for h, c in HEADS.items()})

    def forward(self, x):
        x = self.dropout(torch.flatten(self.pool(self.features(x)), 1))
        return {h: layer(x) for h, layer in self.heads.items()}


def load_classifier(path=CHECKPOINT, device=None):
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = DressMeNet(pretrained=False)
    # weights_only: never run code from a checkpoint file, only read tensors
    model.load_state_dict(torch.load(path, map_location=device, weights_only=True)["model"])
    return model.to(device).eval(), device


@torch.no_grad()
def predict_tensors(x, model, device):
    """Probabilities per head for a batch of prepared pictures (N x 3 x 224 x 224)."""
    with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
        out = model(x.to(device))
    return {h: torch.softmax(v.float(), 1).cpu().numpy() for h, v in out.items()}


# for each category, which sub_category columns are allowed
_ALLOWED = np.array([[SUB_PARENT[s] == c for s in SUB_CATEGORIES] for c in CATEGORIES])


def decode(probs):
    """Turn the probabilities of one batch into readable answers."""
    results = []
    for i in range(len(probs["category"])):
        cat = int(probs["category"][i].argmax())
        sub_p = probs["sub_category"][i] * _ALLOWED[cat]        # only this category's children
        sub = int(sub_p.argmax())
        pat = int(probs["pattern"][i].argmax())
        results.append({
            "category": CATEGORIES[cat], "category_conf": float(probs["category"][i][cat]),
            "sub_category": SUB_CATEGORIES[sub],
            "sub_category_conf": float(sub_p[sub] / max(sub_p.sum(), 1e-9)),
            "pattern": PATTERNS[pat], "pattern_conf": float(probs["pattern"][i][pat]),
        })
    return results


def predict(images, model, device):
    """Answers for a list of PIL images (any size; letterboxed here)."""
    x = torch.stack([TO_TENSOR(letterbox(img.convert("RGB"), SIZE)) for img in images])
    return decode(predict_tensors(x, model, device))
