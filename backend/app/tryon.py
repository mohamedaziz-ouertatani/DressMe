"""
Virtual try-on: a photo of the user wearing one of their wardrobe items (or a
friperie scan), made by a diffusion model.

Realistic try-on models (CatVTON, IDM-VTON) need 8-16 GB of GPU memory, far
more than our RTX 2050 (4 GB), so the picture is made by a model hosted on a
Hugging Face Space and called through `gradio_client`. Chosen by TRYON_ENGINE
in backend/.env:

    space  (default) the CatVTON Space (zhengchong/CatVTON, TRYON_SPACE). It
           dresses one garment at a time: "upper" (top, jacket), "lower"
           (trousers, skirt) or "overall" (dress). A full outfit is made by
           chaining: the result of one garment is the person photo of the next.
    off    no try-on: /tryon answers 503 and the app shows its 2D overlay.

PRIVACY: the user's photo of themself is SENT TO THE SPACE (a third party).
The backend never saves it nor the result; the app tells the user before
they pick a photo.

Free Spaces run on shared GPUs ("ZeroGPU"): one garment takes ~20-60 s, the
anonymous quota is a few minutes of GPU a day, and a Space can be asleep or
down. HF_TOKEN (a free Hugging Face account token) raises the quota. Every
failure becomes TryOnBusy (HTTP 502), and the app falls back to the overlay.

The router only needs:

    engine.dress(person, garment, kind) -> PIL image   (kind: upper / lower / overall)

Tests use a fake engine with the same method. To check the real Space from
your machine: python -m app.tryon person.jpg garment.jpg upper
"""

import tempfile
from pathlib import Path

from PIL import Image

# which part of the body each category dresses; shoes, bags and accessories
# are not supported by the try-on models
KIND = {"top": "upper", "outerwear": "upper", "bottom": "lower",
        "dress": "overall", "traditional": "overall", "swimwear": "overall"}
# chaining order: a dress first, then trousers, then the top, the jacket last (on top)
ORDER = ["dress", "traditional", "swimwear", "bottom", "top", "outerwear"]


class TryOnUnavailable(Exception):
    """Try-on is switched off (HTTP 503)."""


class TryOnBusy(Exception):
    """The Space failed, is asleep, over quota or too slow (HTTP 502)."""


def make_tryon(settings):
    """The engine named by TRYON_ENGINE, or None when it is off."""
    if settings.tryon_engine == "off":
        return None
    return SpaceTryOn(settings)


def plan(docs):
    """Split wardrobe documents into (garments in dressing order, skipped ones).
    Skipped = [{"id", "reason"}]: a category the model can't put on."""
    garments = [d for d in docs if d["category"] in KIND]
    garments.sort(key=lambda d: ORDER.index(d["category"]))
    skipped = [{"id": str(d["_id"]), "reason": "unsupported"} for d in docs if d["category"] not in KIND]
    return garments, skipped


class SpaceTryOn:
    def __init__(self, settings):
        self.settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            from gradio_client import Client     # imported here: only needed when used
            try:
                self._client = Client(self.settings.tryon_space, token=self.settings.hf_token or None,
                                      verbose=False)
            except Exception as e:               # Space asleep, renamed, network down...
                raise TryOnBusy(f"Can't reach the try-on Space: {e}") from e
        return self._client

    def dress(self, person, garment, kind):
        from gradio_client import handle_file

        client = self._get_client()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            person.save(tmp / "person.png")
            garment.save(tmp / "garment.png")
            # the person input is an image editor: background = the photo, one
            # layer = a hand-drawn mask; an all-black layer means "find the mask yourself"
            Image.new("RGBA", person.size, (0, 0, 0, 0)).save(tmp / "mask.png")
            try:
                job = client.submit(
                    {"background": handle_file(tmp / "person.png"),
                     "layers": [handle_file(tmp / "mask.png")], "composite": None},
                    handle_file(tmp / "garment.png"),
                    kind,                               # cloth_type: upper / lower / overall
                    self.settings.tryon_steps,          # num_inference_steps (Space default 50)
                    2.5,                                # guidance_scale (Space default)
                    42,                                 # seed: the same photo gives the same result
                    "result only",                      # show_type
                    api_name=self.settings.tryon_api)
                out = job.result(timeout=self.settings.tryon_timeout)
            except Exception as e:                      # AppError, timeout, quota, network
                raise TryOnBusy(f"The try-on Space failed: {e}") from e
        path = out.get("path") if isinstance(out, dict) else out
        if isinstance(path, (list, tuple)):             # some versions answer [image, ...]
            path = path[0]
        img = Image.open(path)
        img.load()
        return img.convert("RGB")


if __name__ == "__main__":      # live check: python -m app.tryon person.jpg garment.jpg upper
    import sys

    from .config import Settings

    person_path, garment_path, kind = sys.argv[1:4]
    engine = SpaceTryOn(Settings())
    result = engine.dress(Image.open(person_path).convert("RGB"),
                          Image.open(garment_path).convert("RGB"), kind)
    result.save("tryon_result.jpg")
    print("saved tryon_result.jpg", result.size)
