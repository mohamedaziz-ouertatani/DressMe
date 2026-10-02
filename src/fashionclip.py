"""
FashionCLIP helpers shared by every Phase 4 script (and later by the API).

FashionCLIP is a CLIP model fine-tuned on fashion products: it turns an image
(or a text such as "a red dress") into a vector of 512 numbers. Two similar
items get vectors pointing in a similar direction, so the similarity of two
items is simply the dot product of their (normalised) vectors.

    model, processor, device = load_model()
    vecs = embed_images([load_item_image(row)], model, processor, device)
    texts = embed_texts(["a photo of a sneaker"], model, processor, device)
    score = vecs @ texts.T          # cosine similarity, from -1 to 1

The model weights (~600 MB) are downloaded once into the Hugging Face cache
(outside the repo, never committed).
"""

from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL_NAME = "patrickjohncyh/fashion-clip"
CROP_PADDING = 0.05   # Fashionpedia crops get 5% extra margin around the bbox


def load_model(device=None):
    """Load FashionCLIP: fp16 on the GPU when there is one, fp32 on the CPU."""
    from transformers import CLIPModel, CLIPProcessor   # slow import: only when needed

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = CLIPModel.from_pretrained(MODEL_NAME, dtype=dtype).to(device).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    return model, processor, device


def load_item_image(row):
    """Open the picture of one dressme.csv row (a dict or a pandas row).

    Fashionpedia rows have a bbox: the item is cropped out of the street photo,
    with a small margin so the edges of the garment are not cut.
    """
    img = Image.open(DATA / row["image_path"]).convert("RGB")
    if str(row.get("bbox_w", "")) not in ("", "nan"):
        x, y, w, h = (float(row[k]) for k in ("bbox_x", "bbox_y", "bbox_w", "bbox_h"))
        pad_w, pad_h = w * CROP_PADDING, h * CROP_PADDING
        img = img.crop((max(0, x - pad_w), max(0, y - pad_h),
                        min(img.width, x + w + pad_w), min(img.height, y + h + pad_h)))
    return img


def _as_tensor(out):
    """Newer transformers versions wrap the features in an output object."""
    return out if isinstance(out, torch.Tensor) else out.pooler_output


def _normalise(features):
    """Unit length, so a dot product = cosine similarity. Returned as float16."""
    features = features.float()
    features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().astype(np.float16)


@torch.no_grad()
def embed_pixels(pixel_values, model, device):
    """Vectors for a batch already prepared by the processor (used by the DataLoader)."""
    pixel_values = pixel_values.to(device, dtype=model.dtype)
    return _normalise(_as_tensor(model.get_image_features(pixel_values=pixel_values)))


def embed_images(images, model, processor, device):
    """Vectors (N x 512, float16, unit length) for a list of PIL images."""
    pixels = processor(images=images, return_tensors="pt")["pixel_values"]
    return embed_pixels(pixels, model, device)


@torch.no_grad()
def embed_texts(texts, model, processor, device):
    """Vectors (N x 512, float16, unit length) for a list of texts."""
    tokens = processor(text=texts, return_tensors="pt", padding=True, truncation=True).to(device)
    return _normalise(_as_tensor(model.get_text_features(**tokens)))
