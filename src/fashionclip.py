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

import numpy as np
import torch

# load_item_image lives in item_images.py (no PyTorch); re-exported here
from item_images import DATA, ROOT, load_item_image  # noqa: F401

MODEL_NAME = "patrickjohncyh/fashion-clip"


def load_model(device=None):
    """Load FashionCLIP: fp16 on the GPU when there is one, fp32 on the CPU."""
    from transformers import CLIPModel, CLIPProcessor   # slow import: only when needed

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = CLIPModel.from_pretrained(MODEL_NAME, dtype=dtype).to(device).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    return model, processor, device


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
